"""
Esteira da empresa: o caminho de um corte do time ate o CEO.

Segue o desenho de aprovacao em etapas usado por empresas de midia: cada revisor olha so o proprio
dominio, o corte nao avanca sem passar pela etapa atual, ha um unico aprovador final e tudo fica
registrado com data (trilha de auditoria).

    time (um por streamer)   radar acha o momento, edicao corta e legenda, redacao escreve titulo e legendas
    lider do time            gestor direto: a entrega esta completa e na nota que o time se propoe?
    qualidade                o video esta tecnicamente certo? (arquivo, duracao, enquadramento, fala)
    compliance               pode ser publicado? (musica protegida, spoiler, ofensa, autorizacao do streamer)
    gerente de conteudo      IA com rubrica de editor: o corte se sustenta sozinho? Ajusta titulo e legendas
    diretor editorial        pauta do dia: so os melhores de cada canal sobem para o CEO
    ceo                      voce, na tela de aprovacao

Cada etapa grava veredito, parecer e o que melhorar no .json do corte (campo "trilha") e aponta a proxima
("etapa"). Reprovado vai para descartados/ com o motivo, e o CEO pode resgatar: nada some sem rastro.

So ha uma chamada de IA na esteira (o gerente). As outras etapas sao regras: cinco IAs em fila custariam
cinco vezes mais e tenderiam a concordar entre si, sem pegar mais erro.

So usa a biblioteca padrao. A IA e os quadros do video entram como funcoes, para os testes rodarem sem
Claude e sem ffmpeg.
"""
import datetime
import hashlib
import json
import os
import threading
from pathlib import Path

ETAPAS = ("lider_time", "qualidade", "compliance", "gerente", "diretor", "ceo")
ROTULOS = {"lider_time": "Líder do time", "qualidade": "Qualidade", "compliance": "Compliance",
           "gerente": "Gerência de conteúdo", "diretor": "Diretoria editorial", "ceo": "CEO"}
# nomes das etapas da primeira versao da esteira, para cortes que ja estavam no meio do caminho
_ANTIGAS = {"revisor": "lider_time", "gestor": "gerente", "lider": "diretor"}

EMPRESA_PADRAO = {
    "nome": "ClipeMax",
    # nomes que aparecem na tela do CEO e no escritorio; troque em empresa.json para batizar a equipe
    "qualidade": "Analista de qualidade",
    "compliance": "Analista de compliance",
    "gerente": "Gerente de conteúdo",
    "diretor": "Diretor editorial",
    "ceo": "CEO",
    # quantos cortes de cada canal chegam ao CEO por dia; o que passa disso espera na reserva
    "cota_ceo_por_canal": 5,
    "nota_minima_time": 5,
    "nota_minima_gerente": 6,
    "duracao_minima": 12,
    "duracao_maxima": 60,
    # opcoes extras do cortes.py quando o expediente e aberto pelo escritorio, ex: "--jogo \"gta 6\" --por-hora 2"
    "opcoes_da_vigia": "",
}

# Humor do time: sai da taxa de aprovacao do CEO nas ultimas decisoes daquele canal e muda a regra de
# verdade. Time que erra muito passa a ser mais exigente consigo mesmo e manda menos coisa para cima;
# time que acerta ganha mais espaco na pauta. (nota a mais exigida pelo lider, vagas a mais na cota do diretor)
HUMORES = {
    "animado": {"rotulo": "animado", "nota": 0, "cota": 1, "efeito": "ganha 1 vaga a mais na pauta do CEO"},
    "normal": {"rotulo": "normal", "nota": 0, "cota": 0, "efeito": "regras padrão"},
    "cauteloso": {"rotulo": "cauteloso", "nota": 1, "cota": 0, "efeito": "o líder exige 1 ponto a mais de nota"},
    "pressao": {"rotulo": "sob pressão", "nota": 2, "cota": -1,
                "efeito": "o líder exige 2 pontos a mais e o time perde 1 vaga na pauta"},
}
DECISOES_DO_HUMOR = 10  # janela curta: o humor tem de reagir ao que o CEO decidiu esta semana, nao ao mes passado
MINIMO_PARA_HUMOR = 5   # com menos decisoes que isso a taxa e ruido; o time fica em "normal"

_NOMES = ("Ariel", "Bia", "Caio", "Dani", "Edu", "Fabi", "Gabi", "Hugo", "Iara", "Joca", "Kai", "Lia", "Malu", "Nico",
          "Olga", "Pedro", "Quim", "Rafa", "Sol", "Teo", "Uli", "Val", "Wes", "Xande", "Yara", "Zeca", "Alex", "Bruna",
          "Cris", "Davi", "Elis", "Fred", "Gui", "Helo", "Igor", "Jade", "Leo", "Mila", "Noa", "Otto")
PAPEIS_DO_TIME = (("radar", "Radar", "acha o momento na live"), ("edicao", "Edição", "corta, enquadra e legenda"),
                  ("redacao", "Redação", "escreve título, gancho e legendas"),
                  ("lider", "Líder do time", "valida a entrega do time"))
_ATIVIDADE = threading.Lock()
# Aviso do compliance sobre autorizacao. Fica na trilha para o CEO, mas nao e repassado ao gerente:
# autorizacao trava a postagem, nao a qualidade do corte, e a IA do gerente barrava corte bom por causa dela.
AVISO_SEM_AUTORIZACAO = "canal sem autorização do streamer, a postagem fica bloqueada"


def carregar_empresa(arquivo):
    """empresa.json e opcional: so precisa trazer o que muda em relacao ao padrao."""
    empresa = dict(EMPRESA_PADRAO)
    try:
        proprio = json.loads(Path(arquivo).read_text(encoding="utf-8-sig"))
    except OSError:
        return empresa
    except ValueError as err:
        raise ValueError(f"{Path(arquivo).name} nao e um JSON valido: {err}") from None
    desconhecidas = set(proprio) - set(EMPRESA_PADRAO)
    if desconhecidas:
        raise ValueError(f"{Path(arquivo).name}: opcao desconhecida {sorted(desconhecidas)} (validas: {sorted(EMPRESA_PADRAO)})")
    empresa.update(proprio)
    return empresa


def nome_de_pessoa(chave, papel):
    """Nome estavel para cada pessoa de cada time: o mesmo canal tem sempre a mesma equipe no escritorio."""
    resumo = hashlib.sha256(f"{chave}/{papel}".encode()).digest()
    return _NOMES[int.from_bytes(resumo[:4], "big") % len(_NOMES)]


def pessoas_do_time(chave, nome_do_lider=""):
    return [{"id": f"{chave}/{papel}", "papel": papel, "cargo": cargo, "faz": faz,
             "nome": (nome_do_lider if papel == "lider" else "") or nome_de_pessoa(chave, papel)}
            for papel, cargo, faz in PAPEIS_DO_TIME]


# ------------------------------------------------------------------- arquivos

def _ler(lado):
    try:
        return json.loads(lado.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _gravar(lado, dados):
    # grava ao lado e troca: a tela do CEO le estes arquivos a qualquer momento e nao pode pegar um pela metade
    parcial = lado.with_suffix(".tmp")
    parcial.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(parcial, lado)


def etapa_de(dados):
    """Etapa atual do corte. Sem etapa (ou vazia) e corte novo: entra pelo lider do time."""
    etapa = dados.get("etapa") or ETAPAS[0]
    return _ANTIGAS.get(etapa, etapa)


def registrar(dados, etapa, quem, veredito, parecer, proxima, agora, melhoria=""):
    """Acrescenta o parecer na trilha e aponta a proxima etapa. A trilha so cresce: e o historico do corte."""
    dados.setdefault("trilha", []).append({"etapa": etapa, "quem": quem, "veredito": veredito, "parecer": parecer,
                                           "melhoria": melhoria, "quando": agora.isoformat(timespec="seconds")})
    dados["etapa"] = proxima
    return dados


def _descartar(lado, dados, pastas, log):
    """
    Move o corte inteiro (video, dados e copia sem comentario) para descartados/ e so entao grava o parecer.
    Se algum arquivo nao puder ser movido (video aberto num player, caminho longo demais no Windows), desfaz
    o que ja foi e devolve False: o corte fica como estava e a etapa tenta de novo na proxima rodada.
    Sem isso o video ia para uma pasta e os dados ficavam na outra.
    """
    destino = pastas["descartado"] / lado.parent.relative_to(pastas["pendente"])
    movidos = []
    try:
        destino.mkdir(parents=True, exist_ok=True)
        # o video vai primeiro: e o unico que pode estar aberto num player, e se ele nao sair nada sai
        for f in (lado.with_suffix(".mp4"), lado, lado.with_suffix(".txt"), lado.with_suffix(".base")):
            if f.exists():
                os.replace(f, destino / f.name)
                movidos.append(f)
        _gravar(destino / lado.name, dados)
        return True
    except OSError as err:
        for f in movidos:
            try:
                os.replace(destino / f.name, f)
            except OSError:
                pass
        log(f"   nao consegui mover {lado.parent.name}/{lado.stem} para descartados ({str(err)[:100]}); tento de novo depois")
        return False


def _chave(dados, lado=None):
    return dados.get("canal_chave") or dados.get("canal") or (lado.parent.name if lado else "?")


def _na_etapa(pendentes, etapa):
    achados = []
    for lado in sorted(pendentes.rglob("*.json")) if pendentes.exists() else []:
        dados = _ler(lado)
        if dados is not None and etapa_de(dados) == etapa:
            achados.append((lado, dados))
    return achados


def _todos(pastas):
    for base in pastas.values():
        for lado in base.rglob("*.json") if base.exists() else []:
            dados = _ler(lado)
            if dados is not None:
                yield lado, dados


# ---------------------------------------------------------------------- humor

def _decisao_do_ceo(corte):
    """(veredito, quando) da ultima decisao do CEO sobre o corte, ou None se ele ainda nao decidiu."""
    for passo in reversed(corte.get("trilha", [])):
        if passo.get("etapa") == "ceo" and passo.get("veredito") in ("aprovado", "reprovado"):
            return passo["veredito"], str(passo.get("quando", ""))
    return None


def humor_do_time(cortes_do_canal):
    """
    Humor a partir das ultimas decisoes do CEO sobre os cortes do canal.
    -> {"nivel", "rotulo", "taxa", "decisoes", "efeito", "nota", "cota"}
    """
    decisoes = sorted((d for d in map(_decisao_do_ceo, cortes_do_canal) if d), key=lambda d: d[1])[-DECISOES_DO_HUMOR:]
    taxa = sum(v == "aprovado" for v, _ in decisoes) / len(decisoes) if decisoes else None
    if len(decisoes) < MINIMO_PARA_HUMOR:
        nivel = "normal"
    else:
        nivel = "animado" if taxa >= 0.7 else "normal" if taxa >= 0.4 else "cauteloso" if taxa >= 0.2 else "pressao"
    return {"nivel": nivel, "taxa": taxa, "decisoes": len(decisoes), **HUMORES[nivel]}


def humores(pastas):
    por_canal = {}
    for lado, dados in _todos(pastas):
        por_canal.setdefault(_chave(dados, lado), []).append(dados)
    return {chave: humor_do_time(cortes) for chave, cortes in por_canal.items()}


# ------------------------------------------------------------ regras por etapa
# Cada funcao devolve (reprovado?, parecer, o que melhorar) e olha so o proprio dominio.

def checar_entrega(dados, tamanho_do_video, empresa, humor):
    """Lider do time: o time entregou tudo, e na nota que ele se propoe a mandar para cima?"""
    if not tamanho_do_video:
        return True, "o arquivo de vídeo não existe ou está vazio", "Edição: gerar o vídeo de novo"
    minima = empresa["nota_minima_time"] + humor["nota"]
    nota = dados.get("nota_ia")
    if nota is not None and nota < minima:
        motivo = f" (time {humor['rotulo']})" if humor["nota"] else ""
        return True, f"nota {nota} do próprio time, abaixo da mínima de {minima}{motivo}", \
            "Radar: escolher momentos com reação mais clara"
    faltas = []
    if not str(dados.get("titulo") or "").strip():
        faltas.append("Redação: o corte subiu sem título")
    if not str(dados.get("fala") or "").strip():
        faltas.append("Edição: o corte subiu sem legenda")
    parecer = "entrega completa" if not faltas else "entrega incompleta, segue para a gerência completar"
    return False, parecer + (f" (nota {nota} do time)" if nota is not None else ""), "; ".join(faltas)


def checar_qualidade(dados, tamanho_do_video, empresa):
    """Qualidade: o video esta tecnicamente certo?"""
    dur = float(dados.get("duracao") or 0)
    if dur and dur < empresa["duracao_minima"]:
        return True, f"corte de {dur:.0f}s, abaixo do mínimo de {empresa['duracao_minima']}s", "Edição: abrir mais a janela do corte"
    if dur > empresa["duracao_maxima"] + 1:
        return True, f"corte de {dur:.0f}s, acima do máximo de {empresa['duracao_maxima']}s para Shorts", \
            "Edição: fechar o corte na pausa da fala"
    # menos de ~8 KB por segundo nao e video de verdade: o render parou no meio ou saiu so com audio
    if dur and tamanho_do_video and tamanho_do_video < dur * 8_000:
        return True, "arquivo pequeno demais para a duração: o render falhou", "Edição: renderizar de novo"
    avisos, melhorias = [], []
    if dados.get("enquadramento") == "fundo desfocado":
        avisos.append("sem webcam detectada, saiu com fundo desfocado")
        melhorias.append("Edição: conferir a posição da webcam deste canal")
    if not str(dados.get("fala") or "").strip():
        avisos.append("sem fala reconhecida")
    return False, "vídeo dentro do padrão" + (f"; atenção: {', '.join(avisos)}" if avisos else ""), "; ".join(melhorias)


def checar_compliance(dados, autorizado):
    """Compliance: isto pode ser publicado sem derrubar a conta ou expor a empresa?"""
    if dados.get("musica") == "destaque":
        return True, f"música em destaque em {dados.get('musica_pct')}% do corte: risco de bloqueio por direitos autorais", \
            "Radar: evitar trechos com rádio ou música tocando"
    if dados.get("cutscene"):
        return True, "cena de história do jogo (spoiler): as produtoras pedem a remoção", "Radar: evitar cutscenes"
    avisos = []
    if not autorizado:
        avisos.append(AVISO_SEM_AUTORIZACAO)
    if dados.get("musica") == "fundo":
        avisos.append("música de fundo, pode gerar reivindicação")
    if dados.get("ofensas"):
        avisos.append("xingamento pesado no áudio, a plataforma pode restringir")
    return False, "liberado" + (f"; atenção: {', '.join(avisos)}" if avisos else ""), ""


def _etapa_de_regra(pastas, etapa, proxima, quem_de, checar, agora, log, avisar):
    """Roda uma etapa de regra fixa em todos os cortes que estao nela."""
    passou = barrou = 0
    for lado, dados in _na_etapa(pastas["pendente"], etapa):
        mp4 = lado.with_suffix(".mp4")
        quem = quem_de(dados, lado)
        reprovado, parecer, melhoria = checar(dados, mp4.stat().st_size if mp4.exists() else 0, lado)
        registrar(dados, etapa, quem, "reprovado" if reprovado else "aprovado", parecer,
                  "descartado" if reprovado else proxima, agora, melhoria)
        if not reprovado:
            _gravar(lado, dados)
            passou += 1
            avisar(etapa, dados, lado, f"aprovou {lado.stem}: {parecer}")
        elif _descartar(lado, dados, pastas, log):
            barrou += 1
            log(f"   {ROTULOS[etapa].lower()} barrou {lado.parent.name}/{lado.stem}: {parecer}")
            avisar(etapa, dados, lado, f"barrou {lado.stem}: {parecer}")
    return passou, barrou


def _registrar_producao(dados, time, agora):
    """
    O que cada pessoa do time fez entra na trilha uma vez, quando o corte chega ao lider.
    Sao os dados que a producao ja gravou; aqui so ganham dono, para o CEO ver quem fez o que.
    """
    if any(p.get("etapa") == "producao" for p in dados.get("trilha", [])):
        return
    nomes = {p["papel"]: f"{p['nome']} ({p['cargo']})" for p in time}
    entregas = [
        ("radar", dados.get("sinais") or "momento escolhido pelos sinais da live"),
        ("edicao", ", ".join(str(x) for x in (dados.get("enquadramento"), f"{float(dados.get('duracao') or 0):.0f}s",
                                             "com legenda" if dados.get("fala") else "sem legenda") if x)),
        ("redacao", (f"nota {dados['nota_ia']}: {dados.get('motivo', '')}" if dados.get("nota_ia") is not None
                     else "sem IA nesta produção: título e legendas ficaram por fazer")),
    ]
    trilha = dados.setdefault("trilha", [])
    for papel, feito in entregas:
        trilha.append({"etapa": "producao", "quem": nomes[papel], "veredito": "entregue", "parecer": feito,
                       "melhoria": "", "quando": dados.get("criado_em") or agora.isoformat(timespec="seconds")})


# -------------------------------------------------------------------- gerente

def _sem_autorizacao(parecer):
    """O parecer sem o aviso de autorizacao, que nao e assunto do gerente (veja AVISO_SEM_AUTORIZACAO)."""
    limpo = parecer.replace(AVISO_SEM_AUTORIZACAO, "").replace("; atenção: , ", "; atenção: ").replace(", , ", ", ")
    return limpo.removesuffix("; atenção: ").removesuffix(", ")


def etapa_gerente(pastas, empresa, parecer_ia, quadros, agora, log, avisar=lambda *a: None):
    """
    parecer_ia(itens, canal) -> {id: {"nota", "veredito", "parecer", "melhoria", "titulo", "legenda_tiktok",
    "legenda_shorts"}}, None quando a IA falhou agora (os cortes esperam a proxima rodada), ou a propria
    funcao e None quando nao ha IA instalada (os cortes sobem direto, marcados, para a empresa nao parar).
    """
    por_canal = {}
    for lado, dados in _na_etapa(pastas["pendente"], "gerente"):
        por_canal.setdefault(_chave(dados, lado), []).append((lado, dados))
    passou = barrou = 0
    for canal, cortes in por_canal.items():
        if parecer_ia is None:
            for lado, dados in cortes:
                registrar(dados, "gerente", empresa["gerente"], "ausente", "sem IA instalada: subiu sem parecer da gerência",
                          "diretor", agora)
                _gravar(lado, dados)
                passou += 1
            continue
        for i in range(0, len(cortes), 10):  # lotes de 10: o mesmo limite que a producao usa com a IA
            lote = cortes[i:i + 10]
            itens = [{"id": f"{lado.parent.name}/{lado.stem}", "titulo": d.get("titulo", ""), "gancho": d.get("gancho", ""),
                      "legenda_tiktok": d.get("tiktok", ""), "legenda_shorts": d.get("shorts", ""),
                      "fala": d.get("fala", ""), "sinais": d.get("sinais", ""), "duracao": d.get("duracao"),
                      "nota_do_clipador": d.get("nota_ia"), "motivo_do_clipador": d.get("motivo", ""),
                      "avisos_do_revisor": "; ".join(_sem_autorizacao(p.get("parecer", "")) for p in d.get("trilha", [])
                                                     if p.get("etapa") in ("qualidade", "compliance")),
                      "quadros": quadros(lado.with_suffix(".mp4"), d) if quadros else []} for lado, d in lote]
            try:
                respostas = parecer_ia(itens, lote[0][1].get("canal") or canal)
            except Exception as err:  # a IA nunca pode derrubar a esteira dos outros canais
                log(f"   gerência: a IA falhou em {canal} ({str(err)[:120]}); tento na proxima rodada")
                respostas = None
            if not respostas:
                continue
            for (lado, dados), item in zip(lote, itens):
                r = respostas.get(item["id"])
                if not r:
                    continue  # a IA pulou este: fica na etapa e entra no proximo lote
                nota = max(0, min(10, int(r.get("nota", 0))))
                reprovado = r.get("veredito") == "reprovar" or nota < empresa["nota_minima_gerente"]
                dados["nota_gestor"] = nota
                if not reprovado:
                    # a gerencia so mexe no texto do que vai subir; o original fica guardado para o CEO comparar
                    for campo, novo in (("titulo", r.get("titulo")), ("tiktok", r.get("legenda_tiktok")),
                                        ("shorts", r.get("legenda_shorts"))):
                        novo = str(novo or "").strip()
                        if novo and novo != str(dados.get(campo) or "").strip():
                            dados.setdefault("antes_do_gestor", {})[campo] = dados.get(campo, "")
                            dados[campo] = novo
                registrar(dados, "gerente", empresa["gerente"], "reprovado" if reprovado else "aprovado",
                          f"nota {nota}: {str(r.get('parecer', '')).strip()[:300]}", "descartado" if reprovado else "diretor",
                          agora, str(r.get("melhoria", "")).strip()[:200])
                if not reprovado:
                    _gravar(lado, dados)
                    passou += 1
                    avisar("gerente", dados, lado, f"aprovou {lado.stem} com nota {nota}")
                elif _descartar(lado, dados, pastas, log):
                    barrou += 1
                    log(f"   gerência barrou {item['id']} (nota {nota})")
                    avisar("gerente", dados, lado, f"barrou {lado.stem} (nota {nota}): {str(r.get('parecer', ''))[:90]}")
    return passou, barrou


# -------------------------------------------------------------------- diretor

def _promovidos_hoje(pastas, agora):
    """Quantos cortes de cada canal o diretor ja mandou ao CEO hoje, inclusive os que o CEO ja decidiu."""
    hoje, contagem = agora.date().isoformat(), {}
    for lado, dados in _todos(pastas):
        for passo in dados.get("trilha", []):
            if passo.get("etapa") in ("diretor", "lider") and passo.get("veredito") == "promovido" \
                    and str(passo.get("quando", "")).startswith(hoje):
                chave = _chave(dados, lado)
                contagem[chave] = contagem.get(chave, 0) + 1
    return contagem


def etapa_diretor(pastas, empresa, humor_de, agora, log, avisar=lambda *a: None):
    """
    A atencao do CEO e o recurso mais caro da empresa: de cada canal sobem so os melhores do dia, pela nota
    da gerencia. O que sobra fica na reserva (etapa "diretor") e concorre de novo na proxima rodada e no dia
    seguinte. O humor do time muda a cota: time animado ganha uma vaga, time sob pressao perde uma.
    """
    ja = _promovidos_hoje(pastas, agora)
    por_canal = {}
    for lado, dados in _na_etapa(pastas["pendente"], "diretor"):
        por_canal.setdefault(_chave(dados, lado), []).append((lado, dados))
    subiram = reserva = 0
    for canal, cortes in por_canal.items():
        cota = max(1, empresa["cota_ceo_por_canal"] + humor_de(canal)["cota"])
        vagas = max(0, cota - ja.get(canal, 0))
        cortes.sort(key=lambda par: -(par[1].get("nota_gestor") if par[1].get("nota_gestor") is not None
                                      else par[1].get("nota_ia") or 0))
        for posicao, (lado, dados) in enumerate(cortes, 1):
            if posicao > vagas:
                reserva += 1
                continue
            registrar(dados, "diretor", empresa["diretor"], "promovido",
                      f"{posicao}º melhor do canal hoje ({ja.get(canal, 0) + posicao} de {cota} da cota)", "ceo", agora)
            _gravar(lado, dados)
            subiram += 1
            avisar("diretor", dados, lado, f"mandou {lado.stem} para o CEO ({posicao}º do canal hoje)")
    if reserva:
        log(f"   diretoria: {reserva} corte(s) na reserva (cota de {empresa['cota_ceo_por_canal']} por canal por dia)")
    return subiram, reserva


# ----------------------------------------------------------------------- rodar

def rodar(pastas, carteira, empresa, parecer_ia=None, quadros=None, agora=None, log=print, evento=None):
    """
    Passa todos os cortes pendentes pela cadeia inteira. Devolve o resumo da rodada.
    evento(chave, papel, texto) recebe cada decisao, para o diario do escritorio; o lider fala pelo time
    dele (chave do canal), os demais pela empresa.
    """
    agora = agora or datetime.datetime.now()

    def avisar(etapa, dados, lado, texto):
        if evento:
            canal = dados.get("canal") or _chave(dados, lado)
            if etapa == "lider_time":
                evento(_chave(dados, lado), "lider", texto)
            else:
                evento("empresa", etapa, f"{canal}: {texto}")

    por_chave = {c.chave: c for c in carteira}
    humor_por_canal = humores(pastas)  # medido antes da rodada: as decisoes desta rodada nao mudam a regra no meio

    def humor_de(chave):
        return humor_por_canal.get(chave) or humor_do_time([])

    def lider(dados, lado):
        chave = _chave(dados, lado)
        time = pessoas_do_time(chave, por_chave[chave].funcionario if chave in por_chave else "")
        _registrar_producao(dados, time, agora)
        return f"{time[-1]['nome']} (Líder do time)"

    def autorizado(dados, lado):
        canal = por_chave.get(_chave(dados, lado))
        return bool(canal and canal.autorizado)

    resumo = {}
    etapas_de_regra = [
        ("lider_time", "qualidade", lider, lambda d, tam, lado: checar_entrega(d, tam, empresa, humor_de(_chave(d, lado)))),
        ("qualidade", "compliance", lambda d, lado: empresa["qualidade"], lambda d, tam, lado: checar_qualidade(d, tam, empresa)),
        ("compliance", "gerente", lambda d, lado: empresa["compliance"],
         lambda d, tam, lado: checar_compliance(d, autorizado(d, lado))),
    ]
    for etapa, proxima, quem_de, checar in etapas_de_regra:
        resumo[f"{etapa}_aprovou"], resumo[f"{etapa}_barrou"] = _etapa_de_regra(pastas, etapa, proxima, quem_de, checar, agora,
                                                                                    log, avisar)
    resumo["gerente_aprovou"], resumo["gerente_barrou"] = etapa_gerente(pastas, empresa, parecer_ia, quadros, agora, log, avisar)
    resumo["subiram_ao_ceo"], resumo["na_reserva"] = etapa_diretor(pastas, empresa, humor_de, agora, log, avisar)
    resumo["aguardando_ceo"] = len(_na_etapa(pastas["pendente"], "ceo"))
    if resumo["subiram_ao_ceo"] or any(v for k, v in resumo.items() if k.endswith(("_barrou", "_aprovou"))):
        partes = [f"{ROTULOS[e].lower()} barrou {resumo[f'{e}_barrou']}" for e in ETAPAS[:4] if resumo[f"{e}_barrou"]]
        log(f"Esteira: {resumo['subiram_ao_ceo']} corte(s) subiram para voce ({resumo['aguardando_ceo']} aguardando sua decisao)"
            + (f"; {', '.join(partes)}" if partes else ""))
    return resumo


def decisao_do_ceo(dados, acao, empresa=EMPRESA_PADRAO, agora=None):
    """Chamado pela tela de aprovacao. A decisao entra na trilha: e ela que mede a equipe e define o humor dos times."""
    agora = agora or datetime.datetime.now()
    veredito, proxima = {"aprovar": ("aprovado", "aprovado"), "descartar": ("reprovado", "descartado"),
                         # restaurar ou puxar: o CEO passa por cima da esteira e o corte vai direto para ele
                         "restaurar": ("resgatado", "ceo"), "puxar": ("puxado", "ceo")}[acao]
    return registrar(dados, "ceo", empresa["ceo"], veredito, "", proxima, agora)


# ------------------------------------------------------- avaliacao de desempenho

def _veredito(corte, etapa):
    etapas = {etapa, *(antiga for antiga, nova in _ANTIGAS.items() if nova == etapa)}
    return next((p.get("veredito") for p in reversed(corte.get("trilha", [])) if p.get("etapa") in etapas), None)


def avaliacao(cortes, carteira):
    """
    Uma linha por time e uma para a gerencia. O numero que importa e a aprovacao do CEO: time bom e o que
    tem corte aprovado, e gerente bom e o que so deixa subir o que o CEO aprova.
    """
    nomes = {c.chave: c.nome for c in carteira}
    linhas, por_canal = {}, {}
    for corte in cortes:
        chave = _chave(corte)
        por_canal.setdefault(chave, []).append(corte)
        l = linhas.setdefault(chave, {"time": nomes.get(chave, chave), "produzidos": 0, "aprovados_ceo": 0,
                                      "reprovados_ceo": 0, **{f"barrados_{e}": 0 for e in ETAPAS[:4]}})
        l["produzidos"] += 1
        for etapa in ETAPAS[:4]:
            l[f"barrados_{etapa}"] += _veredito(corte, etapa) == "reprovado"
        l["aprovados_ceo"] += _veredito(corte, "ceo") == "aprovado"
        l["reprovados_ceo"] += _veredito(corte, "ceo") == "reprovado"
    for chave, l in linhas.items():
        decididos = l["aprovados_ceo"] + l["reprovados_ceo"]
        l["aprovacao_ceo"] = l["aprovados_ceo"] / decididos if decididos else None
        l["humor"] = humor_do_time(por_canal[chave])["rotulo"]
    # gerencia: do que ela aprovou e o CEO ja decidiu, quanto o CEO tambem aprovou
    julgados = [c for c in cortes if _veredito(c, "gerente") == "aprovado" and _veredito(c, "ceo") in ("aprovado", "reprovado")]
    resgatados = sum(1 for c in cortes if _veredito(c, "gerente") == "reprovado"
                     and any(p.get("veredito") == "resgatado" for p in c.get("trilha", [])))
    gerente = {"julgados_pelo_ceo": len(julgados),
               "acerto": sum(_veredito(c, "ceo") == "aprovado" for c in julgados) / len(julgados) if julgados else None,
               "barrados_que_o_ceo_resgatou": resgatados}
    return sorted(linhas.values(), key=lambda l: (-(l["aprovacao_ceo"] or 0), -l["produzidos"])), gerente


def texto_da_avaliacao(linhas, gerente, empresa=EMPRESA_PADRAO):
    def pct(v):
        return "-" if v is None else f"{v:.0%}"
    saida = ["Avaliacao de desempenho (barrados por etapa: lider, qualidade, compliance, gerencia)",
             f"{'time':<24} {'feitos':>6} {'lider':>5} {'qual.':>5} {'compl.':>6} {'ger.':>5} {'CEO sim':>7} {'CEO nao':>7} {'aprovacao':>9}  humor"]
    for l in linhas:
        saida.append(f"{l['time'][:24]:<24} {l['produzidos']:>6} {l['barrados_lider_time']:>5} {l['barrados_qualidade']:>5} "
                     f"{l['barrados_compliance']:>6} {l['barrados_gerente']:>5} {l['aprovados_ceo']:>7} {l['reprovados_ceo']:>7} "
                     f"{pct(l['aprovacao_ceo']):>9}  {l['humor']}")
    saida.append(f"\n{empresa['gerente']}: de {gerente['julgados_pelo_ceo']} corte(s) que aprovou e voce ja decidiu, "
                 f"voce aprovou {pct(gerente['acerto'])}. Barrados pela gerencia que voce resgatou: {gerente['barrados_que_o_ceo_resgatou']}.")
    if gerente["julgados_pelo_ceo"] < 20:
        saida.append("Aviso: com menos de 20 decisoes suas, estes percentuais ainda nao dizem muita coisa.")
    return "\n".join(saida)


# ----------------------------------------------------------------- escritorio

def marcar_atividade(arquivo, chave, situacao, agora=None):
    """A vigia avisa o que cada time esta fazendo; a pagina do escritorio le este arquivo."""
    agora = agora or datetime.datetime.now()
    with _ATIVIDADE:  # varios times gravam no mesmo arquivo
        dados = _ler(arquivo) or {}
        # mantem o que cada pessoa do time esta fazendo ("papeis"), gravado por registrar_evento
        dados[chave] = {**(dados.get(chave) or {}), "situacao": situacao, "desde": agora.isoformat(timespec="seconds")}
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        _gravar(arquivo, dados)


def registrar_evento(pasta, chave, papel, texto, agora=None):
    """
    Diario do escritorio: o que cada pessoa acabou de fazer de verdade (a producao e a esteira chamam isto).
    Grava uma linha em eventos.jsonl e atualiza o "fazendo agora" da pessoa em atividade.json.
    chave e a do canal para quem e de um time, ou "empresa" para qualidade, compliance, gerente, diretor e ceo.
    """
    agora = agora or datetime.datetime.now()
    quando = agora.isoformat(timespec="seconds")
    with _ATIVIDADE:
        pasta.mkdir(parents=True, exist_ok=True)
        diario = pasta / "eventos.jsonl"
        with open(diario, "a", encoding="utf-8") as f:
            f.write(json.dumps({"quando": quando, "chave": chave, "papel": papel, "texto": texto}, ensure_ascii=False) + "\n")
        # o diario e so para a tela: quando passa de ~300 KB ficam as ultimas 300 linhas
        if diario.stat().st_size > 300_000:
            linhas = diario.read_text(encoding="utf-8").splitlines()[-300:]
            diario.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        arquivo = pasta / "atividade.json"
        dados = _ler(arquivo) or {}
        do_canal = dados.setdefault(chave, {})
        do_canal.setdefault("papeis", {})[papel] = {"texto": texto, "desde": quando}
        _gravar(arquivo, dados)


def ler_eventos(pasta, quantos=40):
    try:
        linhas = (pasta / "eventos.jsonl").read_text(encoding="utf-8").splitlines()[-quantos:]
    except OSError:
        return []
    eventos = []
    for linha in linhas:
        try:
            eventos.append(json.loads(linha))
        except ValueError:
            continue  # linha cortada por uma queda no meio da escrita
    return eventos


def _fazendo(do_canal, papel, agora):
    """O ultimo aviso da pessoa, se for recente. Aviso de horas atras nao e "fazendo agora"."""
    aviso = ((do_canal or {}).get("papeis") or {}).get(papel) or {}
    try:
        recente = (agora - datetime.datetime.fromisoformat(aviso["desde"])).total_seconds() <= 1800
    except (KeyError, ValueError, TypeError):
        return ""
    return aviso.get("texto", "") if recente else ""


def quadro_do_escritorio(cortes, carteira, empresa, atividade, agora=None, eventos=(), vigia=None):
    """
    Dados do escritorio: os times, a cadeia de gestao, a fila de cada mesa, o humor, o placar do dia,
    o que cada pessoa esta fazendo e o diario dos ultimos acontecimentos.
    """
    agora = agora or datetime.datetime.now()
    hoje = agora.date().isoformat()
    pendentes = [c for c in cortes if c["situacao"] == "pendente"]

    def hoje_com(etapa, veredito, chave=None):
        return sum(1 for c in cortes if chave is None or _chave(c) == chave for p in c.get("trilha", [])
                   if p.get("etapa") == etapa and p.get("veredito") == veredito and str(p.get("quando", "")).startswith(hoje))

    times, ticker = [], []
    nomes_dos_times = {c.chave: (c.nome, c.funcionario) for c in carteira}
    for canal in carteira:
        dele = [c for c in cortes if _chave(c) == canal.chave]
        estado = atividade.get(canal.chave) or {}
        # sem sinal ha mais de 30 minutos a vigia esta desligada, mesmo que o ultimo aviso diga "trabalhando"
        try:
            ligado = (agora - datetime.datetime.fromisoformat(estado["desde"])).total_seconds() <= 1800
        except (KeyError, ValueError):
            ligado = False
        humor = humor_do_time(dele)
        melhorias = [{"de": p.get("quem", ""), "texto": p["melhoria"]} for c in sorted(dele, key=lambda c: c["quando"])
                     for p in c.get("trilha", []) if p.get("melhoria")][-3:]
        times.append({
            "chave": canal.chave, "canal": canal.nome, "autorizado": canal.autorizado, "ligado": ligado,
            "vigiar": canal.vigiar,
            "situacao": (estado.get("situacao", "") if ligado else
                         "vigia desligada" if canal.vigiar else "atende só os links que você passar"),
            "humor": {k: humor[k] for k in ("nivel", "rotulo", "taxa", "decisoes", "efeito")},
            "feitos_hoje": sum(1 for c in dele if c["quando"].date().isoformat() == hoje),
            "aprovados_hoje": hoje_com("ceo", "aprovado", canal.chave),
            "aprovados_ceo": sum(1 for c in dele if c["situacao"] == "aprovado"),
            "fila": sum(1 for c in pendentes if _chave(c) == canal.chave and etapa_de(c) == "lider_time"),
            "pessoas": [{**pessoa, "fazendo": _fazendo(estado, pessoa["papel"], agora)}
                        for pessoa in pessoas_do_time(canal.chave, canal.funcionario)],
            "feedback": melhorias})
        if humor["decisoes"]:
            ticker.append({"texto": f"{canal.nome.upper()} {humor['taxa']:.0%} aprovado · {humor['rotulo']}",
                           "tom": "alta" if humor["nivel"] == "animado" else "baixa" if humor["nivel"] in ("cauteloso", "pressao") else "neutro"})
    gestao = [{"id": e, "nome": empresa[e], "cargo": ROTULOS[e], "fazendo": _fazendo(atividade.get("empresa"), e, agora),
               "fila": sum(1 for c in pendentes if etapa_de(c) == e),
               "hoje": (f"mandou {hoje_com(e, 'promovido')} para você" if e == "diretor"
                        else f"aprovou {hoje_com(e, 'aprovado')}, barrou {hoje_com(e, 'reprovado')}")}
              for e in ("qualidade", "compliance", "gerente", "diretor")]
    fila_ceo = sum(1 for c in pendentes if etapa_de(c) == "ceo")
    ticker = [{"texto": f"{fila_ceo} NA MESA DO CEO", "tom": "baixa" if fila_ceo else "neutro"},
              {"texto": f"HOJE {sum(t['feitos_hoje'] for t in times)} PRODUZIDOS · {hoje_com('ceo', 'aprovado')} APROVADOS", "tom": "alta"},
              *ticker]
    return {
        "agora": agora.isoformat(timespec="seconds"), "empresa": empresa["nome"],
        "etapas": [{"id": e, "rotulo": ROTULOS[e]} for e in ETAPAS],
        "times": times, "gestao": gestao,
        "ceo": {"nome": empresa["ceo"], "fila": fila_ceo,
                "hoje": f"aprovou {hoje_com('ceo', 'aprovado')}, reprovou {hoje_com('ceo', 'reprovado')}"},
        # um registro por corte ainda em jogo ou decidido hoje: o escritorio compara com a leitura anterior
        # para saber quem levou o que para quem
        "cortes": [{"id": f"{c['arquivo'].parent.name}/{c['arquivo'].stem}", "canal_chave": _chave(c),
                    "etapa": etapa_de(c) if c["situacao"] == "pendente" else c["situacao"], "titulo": c.get("titulo", "")}
                   for c in cortes if c["situacao"] == "pendente"
                   or any(str(p.get("quando", "")).startswith(hoje) for p in c.get("trilha", [])[-1:])],
        "ticker": ticker,
        "vigia": vigia or {"rodando": False, "desde": None},
        "eventos": [{**e, "quem": _quem(e, nomes_dos_times, empresa)} for e in eventos],
    }


def _quem(evento, nomes_dos_times, empresa):
    """Nome de exibicao de quem gerou o evento: "Bia · Edição · Coringa" ou "Gerente de conteúdo"."""
    chave, papel = evento.get("chave", ""), evento.get("papel", "")
    if chave == "empresa":
        return empresa.get(papel, papel)
    cargo = next((c for p, c, _ in PAPEIS_DO_TIME if p == papel), papel)
    canal, lider = nomes_dos_times.get(chave, (chave, ""))
    nome = (lider if papel == "lider" else "") or nome_de_pessoa(chave, papel)
    return f"{nome} · {cargo} · {canal}"
