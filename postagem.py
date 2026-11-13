"""
Postagem dos cortes aprovados pelas APIs oficiais.

    YouTube   envia o video pronto (Data API v3). Limite da API: 100 envios por dia por projeto.
    TikTok    envia como rascunho para a caixa de entrada da conta; a legenda e o toque final sao
              no aplicativo. Limite da API: 5 rascunhos pendentes a cada 24 horas por conta.
              Postar direto exige o app auditado pelo TikTok; sem auditoria tudo sai privado.

So entra corte aprovado na revisao, de canal com autorizado=sim na carteira, e que ainda nao foi
postado naquela plataforma. O resultado fica gravado no .json do corte, entao rodar de novo nao duplica.

Usa so a biblioteca padrao: as duas APIs sao HTTP simples e o TikTok nao tem SDK oficial em Python.
Todas as funcoes recebem `http`, para os testes rodarem sem rede.
"""
import base64
import datetime
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PLATAFORMAS = ("youtube", "tiktok")
VISIBILIDADES = {"privado": "private", "nao_listado": "unlisted", "publico": "public"}
YT_TITULO_MAX, YT_DESCRICAO_MAX = 100, 5000
YT_CATEGORIA_JOGOS = "20"
TIKTOK_PORTA = 8766  # o TikTok exige o endereco de retorno cadastrado no app, entao a porta e fixa
TIKTOK_PEDACO_MAX = 64 * 1024 * 1024  # acima disso o TikTok exige envio em pedacos
TIKTOK_PEDACO = 10 * 1024 * 1024

OAUTH = {
    "youtube": {
        "autorizar": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        # upload para enviar; readonly para ler as views dos videos ainda privados
        "escopo": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
    },
    "tiktok": {
        "autorizar": "https://www.tiktok.com/v2/auth/authorize/",
        "token": "https://open.tiktokapis.com/v2/oauth/token/",
        "escopo": "video.upload",
    },
}


class ErroDePostagem(RuntimeError):
    """Falha de um corte: registra e segue para o proximo."""


class LimiteAtingido(ErroDePostagem):
    """A plataforma fechou a cota do dia: insistir so gasta chamadas e pode marcar a conta como spam."""


class SemConexao(ErroDePostagem):
    """Falta conectar a conta (ou a autorizacao foi revogada)."""


# ------------------------------------------------------------------------- http

def http_real(metodo, url, cabecalhos=None, corpo=None, timeout=300):
    """-> (status, cabecalhos, corpo em bytes). Erro HTTP volta como resposta, nao como excecao."""
    req = urllib.request.Request(url, data=corpo, method=metodo, headers=cabecalhos or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read()


def _json(corpo):
    try:
        return json.loads(corpo.decode("utf-8")) if corpo else {}
    except (UnicodeDecodeError, ValueError):
        return {}


def _cabecalho(cabecalhos, nome):
    return next((v for k, v in cabecalhos.items() if k.lower() == nome.lower()), "")


# ----------------------------------------------------------------------- contas

def _arq(segredos, plataforma, tipo, conta="principal"):
    sufixo = "" if tipo == "app" or conta == "principal" else f"_{conta}"
    return Path(segredos) / f"{plataforma}_{tipo}{sufixo}.json"


def ler_app(segredos, plataforma):
    """Credenciais do app (nao da conta): o arquivo baixado do Google Cloud ou as chaves do portal do TikTok."""
    arq = _arq(segredos, plataforma, "app")
    try:
        dados = json.loads(arq.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise SemConexao(f"falta o arquivo {arq.name} na pasta segredos (veja o README, secao Postagem)") from None
    dados = dados.get("installed") or dados.get("web") or dados  # formato do arquivo do Google Cloud
    chave = dados.get("client_id") or dados.get("client_key")
    if not chave or not dados.get("client_secret"):
        raise SemConexao(f"{arq.name} nao tem a chave do app e o client_secret")
    return {"id": chave, "segredo": dados["client_secret"]}


def _gravar(arq, dados):
    # grava ao lado e troca: se o programa cair no meio, o token antigo continua inteiro
    arq.parent.mkdir(parents=True, exist_ok=True)
    parcial = arq.with_suffix(".tmp")
    parcial.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(parcial, arq)


def _pedir_token(plataforma, app, campos, http):
    nome_da_chave = "client_key" if plataforma == "tiktok" else "client_id"
    corpo = urllib.parse.urlencode({nome_da_chave: app["id"], "client_secret": app["segredo"], **campos}).encode()
    status, _, resposta = http("POST", OAUTH[plataforma]["token"],
                               {"Content-Type": "application/x-www-form-urlencoded"}, corpo)
    r = _json(resposta)
    if status != 200 or not r.get("access_token"):
        motivo = r.get("error_description") or r.get("error") or f"HTTP {status}"
        raise SemConexao(f"{plataforma}: nao consegui o token ({motivo}); conecte a conta de novo")
    return r


def token_de_acesso(segredos, plataforma, conta="principal", http=http_real, agora=time.time):
    """Token valido da conta, renovado quando falta menos de 2 minutos para vencer."""
    arq = _arq(segredos, plataforma, "token", conta)
    try:
        guardado = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SemConexao(f"{plataforma}: conta \"{conta}\" nao conectada "
                         f"(rode cortes.bat --conectar {plataforma} --conta {conta})") from None
    if guardado.get("expira_em", 0) - agora() > 120:
        return guardado["access_token"]
    r = _pedir_token(plataforma, ler_app(segredos, plataforma),
                     {"grant_type": "refresh_token", "refresh_token": guardado.get("refresh_token", "")}, http)
    # o Google nao devolve o refresh_token na renovacao; o TikTok devolve um novo e invalida o antigo
    guardado.update({"access_token": r["access_token"], "expira_em": agora() + int(r.get("expires_in", 3600)),
                     "refresh_token": r.get("refresh_token") or guardado.get("refresh_token", "")})
    _gravar(arq, guardado)
    return guardado["access_token"]


def desafio_pkce(plataforma, verificador):
    resumo = hashlib.sha256(verificador.encode("ascii"))
    if plataforma == "tiktok":
        return resumo.hexdigest()  # o TikTok para desktop pede o resumo em hexadecimal, fora do padrao
    return base64.urlsafe_b64encode(resumo.digest()).rstrip(b"=").decode("ascii")


def link_de_autorizacao(plataforma, app, retorno, estado, verificador):
    nome_da_chave = "client_key" if plataforma == "tiktok" else "client_id"
    campos = {nome_da_chave: app["id"], "redirect_uri": retorno, "response_type": "code",
              "scope": OAUTH[plataforma]["escopo"].replace(" ", "," if plataforma == "tiktok" else " "),
              "state": estado, "code_challenge": desafio_pkce(plataforma, verificador),
              "code_challenge_method": "S256"}
    if plataforma == "youtube":
        # offline + consent: sem isso o Google nao entrega o refresh_token e a conexao morre em 1 hora
        campos.update({"access_type": "offline", "prompt": "consent"})
    return OAUTH[plataforma]["autorizar"] + "?" + urllib.parse.urlencode(campos)


def conectar(segredos, plataforma, conta="principal", http=http_real, abrir=webbrowser.open, log=print):
    """Abre o navegador para o dono da conta autorizar e guarda o token em segredos/. O login e sempre dele."""
    app = ler_app(segredos, plataforma)
    estado, verificador, recebido = secrets.token_urlsafe(16), secrets.token_urlsafe(48), {}

    class Retorno(BaseHTTPRequestHandler):
        def do_GET(self):
            recebido.update({k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("Conta conectada. Pode fechar esta aba e voltar para a janela dos cortes.".encode())

        def log_message(self, *args):
            pass

    servidor = HTTPServer(("127.0.0.1", TIKTOK_PORTA if plataforma == "tiktok" else 0), Retorno)
    servidor.timeout = 300
    host = "localhost" if plataforma == "tiktok" else "127.0.0.1"
    retorno = f"http://{host}:{servidor.server_port}/callback/"
    link = link_de_autorizacao(plataforma, app, retorno, estado, verificador)
    log(f"Abrindo o navegador para autorizar a conta \"{conta}\" no {plataforma}. Se nao abrir, use este link:\n{link}")
    abrir(link)
    try:
        servidor.handle_request()
    finally:
        servidor.server_close()
    # o estado prova que a resposta veio do pedido que este programa fez, e nao de outra pagina aberta
    if recebido.get("state") != estado or not recebido.get("code"):
        raise SemConexao(f"{plataforma}: autorizacao nao concluida ({recebido.get('error', 'sem resposta em 5 minutos')})")
    r = _pedir_token(plataforma, app, {"grant_type": "authorization_code", "code": recebido["code"],
                                       "redirect_uri": retorno, "code_verifier": verificador}, http)
    if not r.get("refresh_token"):
        raise SemConexao(f"{plataforma}: a autorizacao veio sem refresh_token; remova o acesso do app na conta e tente de novo")
    _gravar(_arq(segredos, plataforma, "token", conta),
            {"access_token": r["access_token"], "refresh_token": r["refresh_token"],
             "expira_em": time.time() + int(r.get("expires_in", 3600))})
    log(f"Conta \"{conta}\" conectada ao {plataforma}.")


# ---------------------------------------------------------------------- youtube

def texto_youtube(corte):
    """Titulo e descricao dentro dos limites do YouTube. #shorts na descricao ajuda a entrar na prateleira de Shorts."""
    titulo = " ".join(str(corte.get("titulo") or "").replace("<", "").replace(">", "").split())
    descricao = str(corte.get("shorts") or "").replace("<", "").replace(">", "").strip()
    if not titulo:
        raise ErroDePostagem("corte sem titulo; preencha na tela de revisao")
    if "#shorts" not in descricao.lower():
        descricao = (descricao + " #shorts").strip()
    credito = f"Corte da live de {corte.get('canal')}: {corte.get('origem')}" if corte.get("origem") else ""
    descricao = (descricao + ("\n\n" + credito if credito else ""))[:YT_DESCRICAO_MAX]
    return titulo[:YT_TITULO_MAX], descricao


def _erro_youtube(status, corpo):
    erro = (_json(corpo).get("error") or {})
    motivos = {e.get("reason", "") for e in erro.get("errors", [])}
    mensagem = f"YouTube recusou (HTTP {status}): {erro.get('message') or 'sem detalhe'}"
    if motivos & {"quotaExceeded", "uploadLimitExceeded", "dailyLimitExceeded", "rateLimitExceeded"}:
        return LimiteAtingido(mensagem)
    if status == 401:
        return SemConexao(mensagem)
    return ErroDePostagem(mensagem)


def postar_youtube(mp4, corte, visibilidade, token, http=http_real):
    """Envio em duas chamadas (resumable): primeiro os dados, depois o arquivo. Devolve o id do video."""
    titulo, descricao = texto_youtube(corte)
    video = Path(mp4).read_bytes()
    dados = {"snippet": {"title": titulo, "description": descricao, "categoryId": YT_CATEGORIA_JOGOS},
             # selfDeclaredMadeForKids: sem declarar, o YouTube segura o video ate o dono responder no Studio
             "status": {"privacyStatus": VISIBILIDADES[visibilidade], "selfDeclaredMadeForKids": False}}
    status, cabecalhos, corpo = http(
        "POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
         "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(video))},
        json.dumps(dados).encode("utf-8"))
    destino = _cabecalho(cabecalhos, "Location")
    if status != 200 or not destino:
        raise _erro_youtube(status, corpo)
    status, _, corpo = http("PUT", destino, {"Content-Type": "video/mp4", "Content-Length": str(len(video))}, video)
    video_id = _json(corpo).get("id")
    if status not in (200, 201) or not video_id:
        raise _erro_youtube(status, corpo)
    return {"id": video_id, "url": f"https://www.youtube.com/shorts/{video_id}", "visibilidade": visibilidade}


def views_youtube(ids, token, http=http_real):
    """{id: views}. Custa 1 unidade de cota a cada 50 videos."""
    views = {}
    ids = list(ids)
    for i in range(0, len(ids), 50):
        lote = ",".join(ids[i:i + 50])
        status, _, corpo = http("GET", f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={lote}",
                                {"Authorization": f"Bearer {token}"}, None)
        if status != 200:
            raise _erro_youtube(status, corpo)
        for item in _json(corpo).get("items", []):
            views[item["id"]] = int((item.get("statistics") or {}).get("viewCount") or 0)
    return views


# ----------------------------------------------------------------------- tiktok

def pedacos_tiktok(tamanho):
    """
    (tamanho do pedaco, quantos pedacos). Ate 64 MB vai inteiro; acima disso, pedacos de 10 MB e o
    ultimo leva o resto, porque o TikTok conta os pedacos arredondando para baixo.
    """
    if tamanho <= TIKTOK_PEDACO_MAX:
        return tamanho, 1
    return TIKTOK_PEDACO, tamanho // TIKTOK_PEDACO


def _erro_tiktok(status, corpo):
    erro = _json(corpo).get("error") or {}
    codigo = erro.get("code") or f"HTTP {status}"
    mensagem = f"TikTok recusou ({codigo}): {erro.get('message') or 'sem detalhe'}"
    if codigo in ("spam_risk_too_many_pending_share", "rate_limit_exceeded", "spam_risk_too_many_posts"):
        return LimiteAtingido(mensagem)
    if codigo in ("access_token_invalid", "scope_not_authorized"):
        return SemConexao(mensagem)
    return ErroDePostagem(mensagem)


def postar_tiktok_rascunho(mp4, token, http=http_real):
    """
    Manda o video para a caixa de entrada da conta. A API de rascunho nao aceita legenda: o dono abre a
    notificacao no aplicativo, cola a legenda (campo "tiktok" do corte) e publica.
    """
    video = Path(mp4).read_bytes()
    pedaco, quantos = pedacos_tiktok(len(video))
    status, _, corpo = http(
        "POST", "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
        {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
        json.dumps({"source_info": {"source": "FILE_UPLOAD", "video_size": len(video), "chunk_size": pedaco,
                                    "total_chunk_count": quantos}}).encode("utf-8"))
    dados = _json(corpo).get("data") or {}
    if status != 200 or not dados.get("upload_url"):
        raise _erro_tiktok(status, corpo)
    for k in range(quantos):
        ini = k * pedaco
        fim = len(video) if k == quantos - 1 else ini + pedaco
        status, _, corpo = http("PUT", dados["upload_url"],
                                {"Content-Type": "video/mp4", "Content-Length": str(fim - ini),
                                 "Content-Range": f"bytes {ini}-{fim - 1}/{len(video)}"}, video[ini:fim])
        if status not in (200, 201, 206):
            raise _erro_tiktok(status, corpo)
    return {"id": dados.get("publish_id", ""), "rascunho": True}


# ------------------------------------------------------------------ orquestracao

def separar_pendentes(cortes, carteira, plataforma):
    """
    -> (para postar, [(corte, motivo do bloqueio)]). So passa corte aprovado, ainda nao postado nesta
    plataforma e de canal com autorizado=sim: postar corte de quem nao autorizou derruba a conta.
    """
    por_chave = {c.chave: c for c in carteira}
    liberados, bloqueados = [], []
    for corte in sorted((c for c in cortes if c["situacao"] == "aprovado"), key=lambda c: c["quando"]):
        if corte.get(f"postado_{plataforma}"):
            continue
        canal = por_chave.get(corte.get("canal_chave") or "")
        if canal is None:
            bloqueados.append((corte, "canal fora da carteira (corte antigo ou canal removido do arquivo)"))
        elif not canal.autorizado:
            bloqueados.append((corte, f"{canal.nome} esta sem autorizado=sim na carteira"))
        else:
            liberados.append({**corte, "conta": canal.conta})
    return liberados, bloqueados


def _atualizar_json(arquivo, campos):
    # le de novo antes de gravar: a tela de revisao pode ter mudado titulo ou views enquanto o video subia
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    dados.update(campos)
    _gravar(arquivo, dados)


def postar(cortes, carteira, plataforma, segredos, visibilidade="privado", limite=0, simular=False,
           http=http_real, log=print):
    """Posta os cortes liberados, do mais antigo para o mais novo. Devolve quantos foram postados."""
    liberados, bloqueados = separar_pendentes(cortes, carteira, plataforma)
    for corte, motivo in bloqueados:
        log(f"   bloqueado: {corte['arquivo'].stem} de {corte.get('canal', '?')} ({motivo})")
    if limite:
        liberados = liberados[:limite]
    if not liberados:
        log(f"{plataforma}: nenhum corte aprovado e liberado para postar")
        return 0
    feitos = 0
    for corte in liberados:
        mp4, rotulo = corte["arquivo"].with_suffix(".mp4"), f"{corte.get('canal', '?')} {corte['arquivo'].stem}"
        if simular:
            log(f"   postaria: {rotulo} | {corte.get('titulo', '')[:60]} (conta {corte['conta']})")
            continue
        try:
            if not mp4.exists():
                raise ErroDePostagem("o video nao esta mais na pasta")
            token = token_de_acesso(segredos, plataforma, corte["conta"], http)
            if plataforma == "youtube":
                resultado = postar_youtube(mp4, corte, visibilidade, token, http)
            else:
                resultado = postar_tiktok_rascunho(mp4, token, http)
        except (LimiteAtingido, SemConexao) as err:
            log(f"   parei em {rotulo}: {err}")
            break
        except (ErroDePostagem, OSError) as err:
            log(f"   falhou: {rotulo}: {err}")
            continue
        resultado["quando"] = datetime.datetime.now().isoformat(timespec="seconds")
        _atualizar_json(corte["arquivo"], {f"postado_{plataforma}": resultado})
        feitos += 1
        log(f"   postado: {rotulo} -> {resultado.get('url') or 'rascunho na caixa de entrada do TikTok'}")
    log(f"{plataforma}: {feitos} corte(s) postado(s)" + (" (simulacao: nada foi enviado)" if simular else ""))
    return feitos


def atualizar_views(cortes, carteira, segredos, http=http_real, log=print):
    """Le as views dos Shorts ja postados e grava em views_shorts, o campo que o painel usa."""
    por_chave = {c.chave: c.conta for c in carteira}
    por_conta = {}
    for corte in cortes:
        video_id = (corte.get("postado_youtube") or {}).get("id")
        if video_id:
            por_conta.setdefault(por_chave.get(corte.get("canal_chave") or "", "principal"), {})[video_id] = corte
    total = 0
    for conta, videos in por_conta.items():
        try:
            views = views_youtube(videos, token_de_acesso(segredos, "youtube", conta, http), http)
        except ErroDePostagem as err:
            log(f"   conta {conta}: {err}")
            continue
        for video_id, n in views.items():
            _atualizar_json(videos[video_id]["arquivo"], {"views_shorts": n})
            total += 1
    log(f"Views atualizadas em {total} corte(s) do YouTube. As do TikTok continuam anotadas na mao.")
    return total
