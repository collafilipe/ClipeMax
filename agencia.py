"""
Camada de agencia: varios streamers ao mesmo tempo, cada um com contrato proprio.

    carteira   canais.txt com opcoes por canal (cliente, cota, prioridade, valores do contrato)
    fila       a parte pesada (transcrever e renderizar) roda um canal por vez, por prioridade
    painel     producao, aprovacao, views e receita estimada por canal

So usa a biblioteca padrao de proposito: os testes rodam sem instalar numpy, ffmpeg ou Whisper.
"""
import argparse
import datetime
import heapq
import itertools
import json
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

SIM = {"sim", "s", "true", "1", "yes"}
NAO = {"nao", "não", "n", "false", "0", "no"}


class ErroDeCarteira(ValueError):
    """Linha invalida no arquivo de canais. A mensagem traz o numero da linha para o dono corrigir."""


@dataclass(frozen=True)
class Canal:
    url: str
    cliente: str = ""
    # Sem autorizacao do streamer o corte pode derrubar a conta que posta. A vigia corta mesmo assim
    # (serve para teste), mas o painel marca o canal para ninguem postar por engano.
    autorizado: bool = False
    prioridade: int = 5  # 1 = fura a fila da parte pesada; 9 = so quando sobrar maquina
    por_hora: float | None = None
    cortes: int | None = None
    jogo: str | None = None
    tags: str | None = None
    mensalidade: float = 0.0
    valor_mil_views: float = 0.0
    # vigiar=nao: o time existe, mas so trabalha nos links que o CEO passar; a vigia nao acompanha o canal
    vigiar: bool = True
    funcionario: str = ""  # nome do clipador deste canal no escritorio e na avaliacao
    conta: str = "principal"  # em qual conta conectada (YouTube/TikTok) os cortes deste canal sao postados

    @property
    def chave(self):
        return chave_do_canal(self.url)

    @property
    def nome(self):
        return self.cliente or self.chave


def chave_do_canal(url):
    """
    Identidade estavel do canal a partir do link ("kick.com/coringa/videos" -> "kick:coringa").
    Fica gravada em cada corte: o nome de exibicao que a plataforma devolve muda com emoji, maiuscula
    ou troca de nome, e ai o painel deixaria de achar os cortes do cliente.
    """
    m = re.search(r"(twitch\.tv|kick\.com|youtube\.com)/+@?([^/?#\s]+)", url.strip(), flags=re.IGNORECASE)
    if not m:
        return url.strip().lower()
    return f"{m.group(1).split('.')[0].lower()}:{m.group(2).lower()}"


def _bool(valor, n):
    v = valor.strip().lower()
    if v in SIM:
        return True
    if v in NAO:
        return False
    raise ErroDeCarteira(f"linha {n}: esperava sim ou nao, veio \"{valor}\"")


def _numero(valor, n, tipo=float, minimo=0):
    try:
        x = tipo(valor.strip().replace(",", "."))
    except ValueError:
        raise ErroDeCarteira(f"linha {n}: esperava um numero, veio \"{valor}\"") from None
    if x < minimo:
        raise ErroDeCarteira(f"linha {n}: o valor minimo e {minimo}, veio \"{valor}\"")
    return x


def _conta(valor, n):
    v = valor.strip().lower()
    # vira parte do nome do arquivo de token em segredos/: nada de barra, ponto ou espaco
    if not re.fullmatch(r"[a-z0-9_-]{1,30}", v):
        raise ErroDeCarteira(f"linha {n}: conta aceita so letras, numeros, - e _, veio \"{valor}\"")
    return v


_CAMPOS = {
    "cliente": lambda v, n: v.strip(),
    "autorizado": _bool,
    "prioridade": lambda v, n: min(9, _numero(v, n, int, 1)),
    "por_hora": lambda v, n: _numero(v, n, float, 0.1),
    "cortes": lambda v, n: _numero(v, n, int, 1),
    "jogo": lambda v, n: v.strip(),
    "tags": lambda v, n: v.strip(),
    "mensalidade": _numero,
    "valor_mil_views": _numero,
    "conta": _conta,
    "funcionario": lambda v, n: v.strip(),
    "vigiar": _bool,
}


def interpretar_carteira(texto):
    """
    Um canal por linha; opcoes depois do link, separadas por barra vertical:

        https://kick.com/coringa/videos | cliente=Coringa | autorizado=sim | por_hora=2 | prioridade=1

    Linha so com o link continua valendo (formato antigo do canais.txt).
    """
    canais, vistos = [], {}
    for n, bruta in enumerate(texto.splitlines(), 1):
        linha = bruta.strip()
        if not linha or linha.startswith("#"):
            continue
        url, *opcoes = [p.strip() for p in linha.split("|")]
        if not url.lower().startswith("http"):
            raise ErroDeCarteira(f"linha {n}: a linha precisa comecar com o link do canal")
        campos = {}
        for opcao in opcoes:
            if not opcao:
                continue
            nome, sep, valor = opcao.partition("=")
            nome = nome.strip().lower()
            if not sep or nome not in _CAMPOS:
                raise ErroDeCarteira(f"linha {n}: opcao desconhecida \"{opcao}\" (validas: {', '.join(_CAMPOS)})")
            campos[nome] = _CAMPOS[nome](valor, n)
        canal = Canal(url=url, **campos)
        # dois fios no mesmo canal apagariam a pasta temporaria um do outro e cortariam o mesmo momento em dobro
        if canal.chave in vistos:
            raise ErroDeCarteira(f"linha {n}: canal repetido (ja esta na linha {vistos[canal.chave]})")
        vistos[canal.chave] = n
        canais.append(canal)
    return canais


def ler_carteira(arquivo):
    # utf-8-sig: o Bloco de Notas pode gravar uma marca invisivel no comeco do arquivo
    return interpretar_carteira(Path(arquivo).read_text(encoding="utf-8-sig"))


def adicionar_canal(arquivo, url, **opcoes):
    """
    Acrescenta um canal no fim do arquivo de canais e devolve o Canal. Recusa canal repetido.
    Usado quando o CEO passa um link pelo escritorio, para ele nao precisar editar o arquivo na mao.
    """
    arquivo = Path(arquivo)
    atual = arquivo.read_text(encoding="utf-8-sig") if arquivo.exists() else ""
    def texto(valor):
        return "sim" if valor is True else "nao" if valor is False else str(valor).replace("|", " ").strip()
    linha = " | ".join([url.strip(), *(f"{k}={texto(v)}" for k, v in opcoes.items() if v not in (None, ""))])
    # valida a carteira inteira ja com a linha nova: se der erro (canal repetido, opcao invalida) nada e gravado
    canal = interpretar_carteira(atual.rstrip("\n") + "\n" + linha + "\n")[-1]
    arquivo.write_text(atual.rstrip("\n") + "\n" + linha + "\n", encoding="utf-8")
    return canal


def opcoes_do_canal(a, canal):
    """Copia das opcoes da linha de comando com o que o contrato deste canal troca. A original nao muda."""
    proprias = {k: getattr(canal, k) for k in ("por_hora", "cortes", "jogo", "tags") if getattr(canal, k) is not None}
    return argparse.Namespace(**{**vars(a), **proprias, "prioridade": canal.prioridade, "canal_chave": canal.chave})


# ------------------------------------------------------------------ fila pesada

class FilaPesada:
    """
    Trava com prioridade para a etapa que usa o processador inteiro (Whisper e ffmpeg).

    A analise de audio e chat e quase toda rede e roda em paralelo entre os canais. Transcrever e
    renderizar dois cortes ao mesmo tempo, ao contrario, so divide o processador: os dois demoram o
    dobro e nenhum sai antes. Por isso entra um por vez, e quem espera e atendido por prioridade
    (empate: ordem de chegada), para o cliente que paga mais nao ficar atras de um canal de teste.
    """

    def __init__(self):
        self._cond = threading.Condition()
        self._espera = []
        self._ordem = itertools.count()
        self._ocupada = False

    @contextmanager
    def vez(self, prioridade=5):
        senha = (prioridade, next(self._ordem))
        with self._cond:
            heapq.heappush(self._espera, senha)
            self._cond.wait_for(lambda: not self._ocupada and self._espera[0] == senha)
            heapq.heappop(self._espera)
            self._ocupada = True
        try:
            yield
        finally:
            with self._cond:
                self._ocupada = False
                self._cond.notify_all()

    def esperando(self):
        with self._cond:
            return len(self._espera)


# ----------------------------------------------------------------------- painel

def _data_do_corte(dados, arquivo):
    try:
        return datetime.datetime.fromisoformat(dados["criado_em"])
    except (KeyError, TypeError, ValueError):
        # cortes feitos antes de existir o campo: a data do video e a melhor pista
        return datetime.datetime.fromtimestamp(arquivo.with_suffix(".mp4").stat().st_mtime)


def ler_cortes(pastas):
    """pastas: {"pendente": Path, "aprovado": Path, "descartado": Path} -> lista de cortes com situacao e data."""
    cortes = []
    for situacao, base in pastas.items():
        if not base.exists():
            continue
        for lado in base.rglob("*.json"):
            try:
                dados = json.loads(lado.read_text(encoding="utf-8"))
                quando = _data_do_corte(dados, lado)
            except (OSError, ValueError):
                continue
            cortes.append({**dados, "situacao": situacao, "quando": quando, "arquivo": lado})
    return cortes


def _dono(corte, por_chave, por_nome):
    canal = por_chave.get(corte.get("canal_chave") or "")
    if canal:
        return canal.chave
    # cortes antigos nao tem canal_chave: tenta casar o nome de exibicao com o apelido do link
    nome = re.sub(r"[^a-z0-9]", "", str(corte.get("canal", "")).lower())
    return por_nome.get(nome) or f"fora da carteira: {corte.get('canal') or '?'}"


def resumo_por_canal(carteira, cortes, desde=None):
    """
    Uma linha por canal da carteira (mesmo sem cortes) mais uma por canal que tem cortes e saiu da carteira.
    Receita estimada = mensalidade + views x valor por mil views. E estimativa do contrato, nao extrato.
    """
    por_chave = {c.chave: c for c in carteira}
    por_nome = {re.sub(r"[^a-z0-9]", "", c.chave.split(":", 1)[-1]): c.chave for c in carteira}
    linhas = {c.chave: {"canal": c.nome, "autorizado": c.autorizado, "prioridade": c.prioridade,
                        "pendentes": 0, "aprovados": 0, "descartados": 0, "views": 0, "ultimo": None,
                        "mensalidade": c.mensalidade, "valor_mil_views": c.valor_mil_views} for c in carteira}
    for corte in cortes:
        if desde and corte["quando"] < desde:
            continue
        chave = _dono(corte, por_chave, por_nome)
        linha = linhas.setdefault(chave, {"canal": chave, "autorizado": False, "prioridade": 9, "pendentes": 0,
                                          "aprovados": 0, "descartados": 0, "views": 0, "ultimo": None,
                                          "mensalidade": 0.0, "valor_mil_views": 0.0})
        linha[{"pendente": "pendentes", "aprovado": "aprovados", "descartado": "descartados"}[corte["situacao"]]] += 1
        if corte["situacao"] == "aprovado":
            linha["views"] += int(corte.get("views_tiktok") or 0) + int(corte.get("views_shorts") or 0)
        if linha["ultimo"] is None or corte["quando"] > linha["ultimo"]:
            linha["ultimo"] = corte["quando"]
    for linha in linhas.values():
        revisados = linha["aprovados"] + linha["descartados"]
        # None quando nada foi revisado: 0% diria que o canal so gera corte ruim, o que ninguem mediu
        linha["aprovacao"] = linha["aprovados"] / revisados if revisados else None
        linha["receita"] = linha["mensalidade"] + linha["views"] / 1000 * linha["valor_mil_views"]
    return sorted(linhas.values(), key=lambda l: (-l["receita"], -l["views"], l["canal"].lower()))


def _milhar(n):
    return f"{n:,.0f}".replace(",", ".")


def _reais(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def texto_do_painel(linhas, dias):
    saida = [f"Painel da agencia, ultimos {dias} dias" if dias else "Painel da agencia, todo o historico",
             f"{'canal':<24} {'pend':>4} {'aprov':>5} {'desc':>4} {'aprovacao':>9} {'views':>11} {'receita est.':>14}  ultimo corte"]
    for l in linhas:
        aprovacao = "-" if l["aprovacao"] is None else f"{l['aprovacao']:.0%}"
        ultimo = l["ultimo"].strftime("%d/%m %H:%M") if l["ultimo"] else "nunca"
        aviso = "" if l["autorizado"] else "  SEM AUTORIZACAO"
        saida.append(f"{l['canal'][:24]:<24} {l['pendentes']:>4} {l['aprovados']:>5} {l['descartados']:>4} "
                     f"{aprovacao:>9} {_milhar(l['views']):>11} {_reais(l['receita']):>14}  {ultimo}{aviso}")
    saida.append(f"{'total':<24} {sum(l['pendentes'] for l in linhas):>4} {sum(l['aprovados'] for l in linhas):>5} "
                 f"{sum(l['descartados'] for l in linhas):>4} {'':>9} {_milhar(sum(l['views'] for l in linhas)):>11} "
                 f"{_reais(sum(l['receita'] for l in linhas)):>14}")
    if any(not l["autorizado"] for l in linhas):
        saida.append("SEM AUTORIZACAO: nao poste cortes desse canal antes de ter o aceite do streamer "
                     "(autorizado=sim no arquivo de canais).")
    return "\n".join(saida)
