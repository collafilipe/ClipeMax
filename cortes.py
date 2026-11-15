"""
Cortes automaticos de lives (Twitch, Kick, YouTube) para TikTok e Shorts.

    cortes.bat LINK_DO_VOD              gera os cortes de uma live
    cortes.bat --canais canais.txt      pega o VOD mais recente de cada canal da lista
    cortes.bat --vigiar canais.txt      acompanha os canais e corta enquanto a live esta no ar
    cortes.bat --revisar                abre a tela de revisao dos cortes no navegador
    cortes.bat --titular                gera titulo e legendas pela IA para os cortes ja prontos
    cortes.bat --painel canais.txt      producao, aprovacao, views e receita estimada por canal
    cortes.bat --pedidos                atende os links que o CEO passou pelo escritorio e sai
    cortes.bat --esteira                passa os cortes prontos por revisor, gestor e lider ate a sua fila
    cortes.bat --avaliacao              desempenho de cada clipador e do gestor, medido pelas suas decisoes
    cortes.bat --conectar youtube       autoriza uma conta para postagem (uma vez por conta)
    cortes.bat --postar youtube         posta os cortes aprovados dos canais autorizados
    cortes.bat --atualizar-views        le as views dos Shorts postados para o painel
"""
import argparse
import datetime
import json
import math
import os
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

import agencia
import aviso
import esteira
import ia
import musica
import pedidos
import postagem
import video
from fontes import (RAIZ, analisar_audio, capitulos_de_jogo, hms, info_vod, ler_hls, limpar_nome, log, obter_chat,
                    obter_clipes, ultimo_vod, ultimos_vods)

ESTADO = RAIZ / "estado"
PROCESSADOS = RAIZ / "processados.txt"
FALHAS = ESTADO / "falhas.json"
BASES = [RAIZ / "prontos", RAIZ / "aprovados", RAIZ / "descartados"]
ATIVIDADE = ESTADO / "atividade.json"  # o que cada clipador esta fazendo; a pagina do escritorio le daqui
PASTAS = {"pendente": RAIZ / "prontos", "aprovado": RAIZ / "aprovados", "descartado": RAIZ / "descartados"}
SEGREDOS = RAIZ / "segredos"  # chaves dos apps e tokens das contas; fora do git
# Com varios canais em paralelo, transcrever e renderizar continuam um por vez (veja agencia.FilaPesada).
FILA = agencia.FilaPesada()
# processados.txt e falhas.json sao de todos os canais: sem a trava, dois fios gravando juntos perdem linhas.
_ARQUIVOS = threading.Lock()


def _diario(a, papel, texto):
    """Avisa o escritorio do que a pessoa daquele papel acabou de fazer. Fora da vigia (sem canal) nao faz nada."""
    chave = getattr(a, "canal_chave", "")
    if chave:
        try:
            esteira.registrar_evento(ESTADO, chave, papel, texto)
        except OSError:
            pass  # o diario e so para a tela: nunca pode parar a producao


# ------------------------------------------------------------- nota dos picos

def z_robusto(x):
    med = np.median(x)
    mad = np.median(np.abs(x - med)) * 1.4826
    if mad < 1e-6:
        mad = np.std(x) or 1.0
    return (x - med) / mad


def z_local(x, janela=900, passo=60):
    """
    Quanto cada segundo se destaca dos ~15 minutos em volta dele (mediana e desvio locais).
    Assim um trecho inteiro barulhento ou com chat agitado nao pontua so por ser agitado:
    pontua o que sobe em relacao ao que vinha acontecendo.
    """
    n = len(x)
    if n < janela * 2:
        return z_robusto(x)
    geral = np.median(np.abs(x - np.median(x))) * 1.4826
    piso = max(geral * 0.5, 1e-6) if geral > 1e-6 else (np.std(x) or 1.0)
    centros = np.arange(0, n, passo)
    med, mad = np.empty(len(centros)), np.empty(len(centros))
    for k, c in enumerate(centros):
        w = x[max(0, c - janela // 2): min(n, c + janela // 2)]
        med[k] = np.median(w)
        mad[k] = np.median(np.abs(w - med[k])) * 1.4826
    eixo = np.arange(n)
    return (x - np.interp(eixo, centros, med)) / np.maximum(np.interp(eixo, centros, mad), piso)


def suavizar(x, janela):
    return np.convolve(x, np.ones(janela) / janela, mode="same")


def raridade(z, teto=4.0):
    """
    Converte um sinal em "quao raro e este segundo nesta live": 1 = entre os 10% mais altos, 2 = 1%, 3 = 0,1%.
    Como a escala e a mesma para qualquer sinal, audio e chat passam a pesar igual, seja qual for o formato
    da distribuicao de cada um (o chat tem rajadas muito maiores que o audio).
    """
    n = len(z)
    posto = np.empty(n)
    posto[np.argsort(z, kind="stable")] = np.arange(n)
    return np.clip(-np.log10(1 - (posto + 0.5) / n), 0, teto)


def pontuar(rms, chat, clipes, atraso_chat=6):
    """
    Nota por segundo da live, juntando tres sinais, cada um limitado para nenhum dominar:
      audio  (0 a 4): volume acima do que vinha nos minutos anteriores, medido pela raridade na live
      chat   (0 a 4): ritmo de mensagens acima do normal recente, na mesma escala de raridade
      juntos (0 a 2): bonus quando audio e chat sobem ao mesmo tempo (reacao de verdade)
      clipes (0 a 3): espectadores criaram clipe ali, pesado pelas views absolutas
    """
    total = len(rms)
    za = raridade(z_local(suavizar(20 * np.log10(rms), 8)))
    nota = za.astype(np.float64)
    if chat is not None and len(chat) == total:
        ok = np.isfinite(chat)
        if ok.any() and float(np.nansum(chat)) > 0:
            c = np.where(ok, chat, float(np.median(chat[ok])))
            c = np.sqrt(np.maximum(suavizar(c, 15), 0))
            c = np.concatenate([c[atraso_chat:], np.full(atraso_chat, c[-1])])
            zc = raridade(z_local(c))
            zc[~np.concatenate([ok[atraso_chat:], np.zeros(atraso_chat, dtype=bool)])] = 0  # sem dado de chat
            nota += zc + 0.5 * np.minimum(za, zc)
    if clipes:
        bonus = np.zeros(total)
        for pos, dur, views, _ in clipes:
            a, b = max(0, pos - 10), min(total, pos + dur + 10)
            if a < b and views >= 5:
                bonus[a:b] = np.maximum(bonus[a:b], min(3.0, math.log10(1 + views)))
        nota += bonus
    return nota


def achar_picos(nota, n, espaco, pular=180, cauda=15, evitar=()):
    """Os n melhores momentos, com distancia minima entre eles e longe dos que ja viraram corte."""
    nota = nota.copy()
    total = len(nota)
    nota[:max(30, pular)] = -np.inf
    if cauda:
        nota[max(0, total - cauda):] = -np.inf
    for t in evitar:
        nota[max(0, int(t) - espaco): int(t) + espaco] = -np.inf
    picos = []
    while len(picos) < n:
        i = int(np.argmax(nota))
        if not np.isfinite(nota[i]):
            break
        picos.append((i, float(nota[i])))
        nota[max(0, i - espaco): i + espaco] = -np.inf
    return picos


def sinais_do_pico(pico, rms, chat, clipes):
    partes = []
    if chat is not None and len(chat) > pico:
        media = float(np.nanmean(chat))
        local = chat[max(0, pico - 10): pico + 20]
        if media > 0 and np.isfinite(local).any():
            partes.append(f"chat {float(np.nanmean(local)) / media:.1f}x a media da live")
    perto = [c for c in clipes if c[0] - 20 <= pico <= c[0] + c[1] + 20]
    if perto:
        melhor = max(perto, key=lambda c: c[2])
        partes.append(f'{len(perto)} clipe(s) de espectadores, o maior com {melhor[2]} views ("{melhor[3][:60]}")')
    if not partes:
        partes.append("pico de volume no audio")
    return "; ".join(partes)


def _norm(txt):
    return re.sub(r"[^a-z0-9]", "", txt.lower())


def termos_do_jogo(a):
    """
    --jogo "gta vi, grand theft auto vi" -> [(termo normalizado, tem_edicao)].
    Quando o termo termina em numero ou algarismo romano, a edicao precisa bater: "gta v" nao aceita "GTA VI".
    Sem edicao ("gta"), qualquer jogo da serie serve.
    """
    romanos = {"1": "i", "2": "ii", "3": "iii", "4": "iv", "5": "v", "6": "vi", "7": "vii", "8": "viii", "9": "ix",
               "10": "x"}
    arabicos = {v: k for k, v in romanos.items()}
    termos = set()
    for bruto in (getattr(a, "jogo", "") or "").split(","):
        palavras = bruto.strip().lower().split()
        if not palavras or not _norm(bruto):
            continue
        # variantes: "gta" por extenso e a edicao em algarismo romano ou arabico ("gta 6" = "Grand Theft Auto VI")
        nomes = [palavras] + ([["grand", "theft", "auto"] + palavras[1:]] if palavras[0] == "gta" else [])
        for nome in nomes:
            fim = nome[-1]
            for ultima in {fim, romanos.get(fim, fim), arabicos.get(fim, fim)}:
                variante = nome[:-1] + [ultima]
                termos.add((_norm(" ".join(variante)), bool(re.fullmatch(r"[ivx]+|\d+", ultima))))
    return sorted(termos)


def e_o_jogo(nome, termos):
    n = _norm(nome)
    return any(re.search(re.escape(t) + (r"(?![ivx0-9])" if edicao else ""), n) for t, edicao in termos)


def filtrar_por_jogo(nota, capitulos, termos):
    """Zera a nota fora dos trechos em que o jogo pedido estava na tela. Devolve (nota, segundos validos)."""
    valido = np.zeros(len(nota), dtype=bool)
    for ini, fim, nome in capitulos:
        if e_o_jogo(nome, termos):
            valido[int(ini):int(fim) if fim else len(nota)] = True
    nota = nota.copy()
    nota[~valido] = -np.inf
    return nota, int(valido.sum())


def momentos_existentes(info):
    """Segundos da live que ja viraram corte (pendente, aprovado ou descartado), para nao repetir."""
    nome = f"{limpar_nome(info['canal'])}_{limpar_nome(info['id'])}"
    segundos = []
    for base in BASES:
        pasta = base / nome
        if not pasta.exists():
            continue
        for mp4 in pasta.glob("*.mp4"):
            pico = None
            lado = mp4.with_suffix(".json")
            if lado.exists():
                try:
                    pico = json.loads(lado.read_text(encoding="utf-8")).get("pico")
                except ValueError:
                    pico = None
            if pico is None:  # cortes antigos: o nome do arquivo traz o inicio do trecho
                m = re.search(r"(\d+)h(\d\d)m(\d\d)s", mp4.stem)
                if m:
                    pico = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + 27
            if pico is not None:
                segundos.append(int(pico))
    # momentos que a IA ja avaliou e reprovou nesta live: nao vale baixar e avaliar de novo
    try:
        segundos += [int(s) for s in json.loads(_arq_reprovados(info).read_text(encoding="utf-8"))]
    except (OSError, ValueError):
        pass
    return segundos


def _arq_reprovados(info):
    return ESTADO / f"reprovados_{limpar_nome(info['id'])}.json"


def lembrar_reprovados(info, picos):
    if not picos:
        return
    ESTADO.mkdir(exist_ok=True)
    arq = _arq_reprovados(info)
    try:
        antigos = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        antigos = []
    arq.write_text(json.dumps(sorted(set(antigos) | {int(p) for p in picos})), encoding="utf-8")


# -------------------------------------------------------------- gerar cortes

def gerar_cortes(url, info, hls_video, picos, a, n_final, tmp, saida, total, rms, chat, clipes, jogo_pela_ia=False):
    """
    jogo_pela_ia: quando a plataforma nao informa o jogo por trecho, a IA diz qual jogo esta na tela
    e os cortes de outro jogo (ou sem jogo) sao descartados.

    Baixa, transcreve, avalia e renderiza os momentos escolhidos.
    Devolve {"feitos": [...], "descartados": [...]} com os segundos (pico) de cada grupo.
    Momentos que falharam por download ou render ficam de fora dos dois, para serem tentados de novo.
    """
    canal = limpar_nome(info["canal"])
    antes, depois = int(a.duracao * 0.6) + 12, int(a.duracao * 0.4) + 12
    cand = []
    alvos = [(pico, nota, max(0, pico - antes), min(int(total), pico + depois), tmp / f"{hms(pico)}_bruto.mp4")
             for pico, nota in picos]
    _diario(a, "edicao", f"baixando {len(alvos)} trecho(s) candidato(s)")
    # os trechos sao baixados em paralelo (rede); a transcricao, que usa todo o processador, vem depois, um a um
    with ThreadPoolExecutor(max_workers=4 if hls_video else 1) as pool:
        baixados = list(pool.map(lambda t: video.baixar_trecho(url, t[2], t[3], t[4], hls_video), alvos))
    for (pico, nota, j_ini, j_fim, bruto), (ok, erro, real) in zip(alvos, baixados):
        nome = hms(pico)
        janela = video.duracao_de(bruto) if ok else 0.0
        if not ok or janela < 0.8 * (j_fim - j_ini):
            log(f"   {nome}: trecho nao baixou inteiro, fica para a proxima ({erro.strip()[-120:]})")
            bruto.unlink(missing_ok=True)
            continue
        # triagem: transcricao rapida, suficiente para a IA avaliar e para achar as pausas da fala
        palavras = [] if a.sem_legenda else video.transcrever(bruto, a.modelo, a.idioma)
        idioma = getattr(video.transcrever, "idioma", None) or a.idioma
        ini, fim = video.limites_inteligentes(palavras, pico - real, a.duracao, janela)
        dentro = [(p[0] - ini, p[1] - ini, p[2]) for p in palavras if ini <= p[0] < fim]
        cand.append({"pico": pico, "nota": nota, "bruto": bruto, "ini": ini, "fim": fim, "abs": real + ini,
                     "palavras": dentro, "fala": " ".join(p[2] for p in dentro), "idioma": idioma,
                     "sinais": sinais_do_pico(pico, rms, chat, clipes)})
        log(f"   {nome}: trecho de {fim - ini:.0f}s separado")

    # nota, titulo, gancho e legendas pela IA (se houver chave); sem IA vale a ordem dos sinais.
    # A nota da IA serve de triagem: ordena os cortes e tira os claramente fracos.
    aval = None
    if cand and not a.sem_ia and ia.disponivel():
        aval = {}
        _diario(a, "redacao", f"avaliando {len(cand)} candidato(s) e escrevendo titulo e legendas")
        try:
            for i in range(0, len(cand), 10):
                parte = ia.avaliar([{"id": str(c["pico"]), "trecho": f"{hms(c['abs'])} da live", "sinais": c["sinais"],
                                     "fala": c["fala"], "quadros": video.quadros(c["bruto"], c["ini"], c["fim"])}
                                    for c in cand[i:i + 10]], info["canal"], info["titulo"])
                if parte is None:
                    aval = None
                    break
                aval.update(parte)
        except Exception as err:  # a IA nunca pode derrubar uma live ja baixada e transcrita
            log(f"   IA falhou ({str(err)[:120]}); sigo so com os sinais")
            aval = None
    descartados = []
    for c in cand:
        c["ia"] = (aval or {}).get(str(c["pico"]))
    if aval:
        cand.sort(key=lambda c: -(c["ia"]["nota"] if c["ia"] else -1))
        termos = termos_do_jogo(a) if jogo_pela_ia else []
        fracos = []
        for c in cand:
            if not c["ia"]:
                continue
            if termos and not e_o_jogo(c["ia"].get("jogo", ""), termos):
                log(f"   {hms(c['pico'])}: descartado, jogo na tela e \"{c['ia'].get('jogo', '?')}\"")
                fracos.append(c)
            elif c["ia"]["nota"] < a.nota_minima:
                log(f"   {hms(c['pico'])}: descartado pela IA (nota {c['ia']['nota']}: {c['ia']['motivo'][:90]})")
                _diario(a, "redacao", f"descartou {hms(c['pico'])} (nota {c['ia']['nota']}): {c['ia']['motivo'][:80]}")
                fracos.append(c)
        descartados += [c["pico"] for c in fracos]
        cand = [c for c in cand if c not in fracos]
    elif jogo_pela_ia:
        log("   aviso: sem IA nao da para conferir o jogo nesta plataforma; o filtro --jogo foi ignorado")
    escolhidos, sobra = cand[:max(0, n_final)], cand[max(0, n_final):]
    for c in sobra + [c for c in fracos] if aval else sobra:
        c["bruto"].unlink(missing_ok=True)

    # enquadramento: a webcam e procurada olhando todos os cortes da live juntos
    cams = {}
    if a.facecam == "auto" and escolhidos:
        det = {hms(c["pico"]): video.detectar_rostos(c["bruto"], c["ini"], c["fim"]) for c in escolhidos}
        cams = video.escolher_webcams(canal, det)
    feitos = []
    for ordem, c in enumerate(escolhidos, 1):
        nome = hms(c["pico"])  # nome pelo pico: nao muda entre uma execucao e outra
        cam = cams.get(nome) if a.facecam == "auto" else (a.facecam if isinstance(a.facecam, list) else None)
        dur = c["fim"] - c["ini"]
        # musica: o YouTube bloqueia Shorts de mais de 1 minuto com musica reivindicada
        som = musica.analisar(c["bruto"], c["ini"], c["fim"]) or {"musica_pct": None, "musica_forte_s": 0, "nivel": ""}
        if som["nivel"] == "destaque" and getattr(a, "sem_musica", False):
            log(f"   {nome}: descartado, musica em destaque em {som['musica_pct']}% do corte")
            descartados.append(c["pico"])
            c["bruto"].unlink(missing_ok=True)
            continue
        if som["nivel"] in ("fundo", "destaque") and dur > 59:
            log(f"   {nome}: tem musica, encurtado de {dur:.0f}s para 59s (limite seguro para Shorts)")
            dur = 59.0
            c["palavras"] = [p for p in c["palavras"] if p[0] < dur]
            c["fala"] = " ".join(p[2] for p in c["palavras"])
        if not a.sem_legenda and not getattr(a, "legenda_rapida", False):
            # legenda final: so os cortes escolhidos sao transcritos de novo, com a busca mais cuidadosa
            finas = video.transcrever(c["bruto"], a.modelo, c.get("idioma") or a.idioma, c["ini"], c["ini"] + dur,
                                      preciso=True)
            if finas:
                c["palavras"] = finas
                c["fala"] = " ".join(p[2] for p in finas)
        gancho = (c["ia"] or {}).get("gancho") or a.gancho
        mascara = not getattr(a, "sem_mascara", False)
        limpar = (lambda t: video.mascarar(t)[0]) if mascara else (lambda t: t)
        ofensas = video.mascarar(c["fala"])[1]  # contado mesmo sem mascara, para avisar na revisao
        if ofensas and mascara:
            log(f"   {nome}: {ofensas} xingamento(s) pesado(s) mascarado(s) na legenda (o audio continua igual)")
        # Formato pelo tipo de video. Com webcam (ou camera cheia) a tela ja esta ocupada e o gancho some aos 4 s.
        # Sem webcam sobra uma faixa em cima e outra embaixo do jogo: viram moldura, com a logo do canal e uma
        # frase sobre o assunto (o titulo da IA) o video inteiro. A legenda sobe para cima do jogo.
        logo = video.logo_do_canal()
        frase = (c["ia"] or {}).get("titulo") or gancho
        moldura = (not cam and a.layout == "blur" and not getattr(a, "sem_moldura", False) and bool(frase or logo)
                   and ("logo" if logo else "frase"))
        # Pessoa falando com a camera em tela cheia: se o dono pos videos na pasta fundos/, um deles entra
        # na metade de baixo (sem som) e a legenda sobe para a emenda.
        fundo = (video.escolher_fundo(c["pico"], dur)
                 if isinstance(cam, tuple) and not getattr(a, "sem_fundo", False) else None)
        legenda = tmp / f"{nome}.ass"
        video.escrever_ass(c["palavras"], legenda,
                           1170 if isinstance(cam, list) else 880 if fundo else (600 if moldura else a.margem_legenda),
                           gancho=frase if moldura else gancho,
                           credito=None if a.sem_credito else f"@{info['canal']}", duracao=dur,
                           estilo=video.estilo_do_corte(c["pico"], getattr(a, "estilo_fixo", False)), mascara=mascara,
                           moldura=moldura or None)
        _diario(a, "edicao", f"renderizando o corte {nome} ({dur:.0f}s)")
        # renderiza na pasta temporaria e so move quando esta pronto: a revisao nunca ve arquivo pela metade
        parcial = tmp / f"{nome}.mp4"
        ok, erro = video.renderizar(tmp, c["bruto"], legenda, a.layout, cam, parcial, a.zoom, c["ini"], dur,
                                    logo=logo if moldura else None, fundo=fundo)
        c["bruto"].unlink(missing_ok=True)
        if not ok:
            parcial.unlink(missing_ok=True)
            log(f"   {nome}: falhou ao renderizar ({erro.strip()[-200:]})")
            continue
        # Contexto no video: corte cru (so o trecho da live com legenda) e tratado como conteudo reutilizado.
        # A frase da IA entra por padrao depois do gancho; o video sem ela fica ao lado (.base), entao a
        # tela de aprovacao troca pela opiniao do dono do canal ou tira, como qualquer comentario.
        contexto = limpar((c["ia"] or {}).get("contexto", "")).strip()
        sem_contexto = None
        if contexto and not getattr(a, "sem_contexto", False):
            com_contexto = tmp / f"{nome}_contexto.mp4"
            ok, erro = video.queimar_comentario(parcial, com_contexto, contexto, 4.2 if gancho else 0.0,
                                                embaixo=bool(moldura))
            if ok:
                sem_contexto, parcial = parcial, com_contexto
            else:
                log(f"   {nome}: nao consegui escrever o contexto no video, segue sem ({erro.strip()[-120:]})")
        tags =" ".join(t for t in (a.tags.strip(), f"#{canal.lower()}", "#cortes", "#fyp") if t)
        dados = {
            "canal": info["canal"], "live": info["titulo"], "origem": url, "ordem": ordem, "pico": int(c["pico"]),
            # o painel da agencia agrupa por canal_chave e filtra o periodo por criado_em
            "canal_chave": getattr(a, "canal_chave", ""),
            "criado_em": datetime.datetime.now().isoformat(timespec="seconds"),
            "trecho": f"{hms(c['abs'])} a {hms(c['abs'] + dur)}", "duracao": round(dur, 1),
            "nota_sinais": round(c["nota"], 1), "sinais": c["sinais"],
            "nota_ia": (c["ia"] or {}).get("nota"), "motivo": (c["ia"] or {}).get("motivo", ""),
            "titulo": limpar((c["ia"] or {}).get("titulo", "")), "gancho": limpar(gancho or ""),
            "ofensas": ofensas,
            "jogo": (c["ia"] or {}).get("jogo", ""),
            "contexto": (c["ia"] or {}).get("contexto", ""),
            # comentario_auto: o texto no video e o contexto da IA, nao a opiniao do dono (o desempenho separa os dois)
            "comentario": contexto if sem_contexto else "", "comentario_auto": bool(sem_contexto),
            "cutscene": bool((c["ia"] or {}).get("cutscene", False)),
            "musica": som["nivel"], "musica_pct": som["musica_pct"], "musica_forte_s": som["musica_forte_s"],
            "tiktok": limpar((c["ia"] or {}).get("legenda_tiktok") or tags),
            "shorts": limpar((c["ia"] or {}).get("legenda_shorts") or tags + " #shorts"), "fala": c["fala"],
            "enquadramento": ("camera + video embaixo" if fundo else "camera cheia" if isinstance(cam, tuple)
                              else "webcam + jogo" if cam
                              else "moldura com logo e frase" if moldura == "logo" else "moldura com frase" if moldura
                              else "fundo desfocado"),
        }
        (saida / f"{nome}.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        if sem_contexto:
            os.replace(sem_contexto, saida / f"{nome}.base")
        os.replace(parcial, saida / f"{nome}.mp4")
        feitos.append(c["pico"])
        _diario(a, "edicao", f"corte {nome} pronto, entregue ao lider" + (f": {dados['titulo']}" if dados["titulo"] else ""))
        extra = f" | nota {dados['nota_ia']}: {dados['titulo']}" if dados["nota_ia"] is not None else ""
        avisos = ([f"musica em {som['nivel']} ({som['musica_pct']}%)"] if som["nivel"] in ("fundo", "destaque") else []) \
            + (["possivel cutscene"] if dados["cutscene"] else [])
        log(f"   {nome}: pronto ({dados['enquadramento']}, {dur:.0f}s){extra}"
            + (f" | ATENCAO: {', '.join(avisos)}" if avisos else ""))
    return {"feitos": feitos, "descartados": descartados}


def _pastas(info):
    saida = RAIZ / "prontos" / f"{limpar_nome(info['canal'])}_{limpar_nome(info['id'])}"
    tmp = RAIZ / "tmp" / limpar_nome(info["id"])
    saida.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    return saida, tmp


def _candidatos(a, n):
    """
    Com IA, os sinais so fazem a pre-selecao: separamos varios candidatos por corte desejado
    (--candidatos, padrao 2,5 vezes) e a IA, que le a fala e ve os quadros, fica com os melhores.
    """
    if a.sem_ia or not ia.disponivel():
        return n
    return max(n + 1, math.ceil(n * getattr(a, "candidatos", 2.5)))


def _filtro_de_jogo(url, a, nota):
    """Aplica --jogo. Devolve (nota, jogo_pela_ia, pode_continuar)."""
    termos = termos_do_jogo(a)
    if not termos:
        return nota, False, True
    caps = capitulos_de_jogo(url)
    if not caps:
        return nota, True, True  # Kick e YouTube: a IA confere o jogo corte a corte
    nota, segundos = filtrar_por_jogo(nota, caps, termos)
    nomes = ", ".join(sorted({c[2] for c in caps}))
    if not segundos:
        log(f"   filtro de jogo: nenhum trecho desta live e de \"{a.jogo}\" (a live tem: {nomes})")
        return nota, False, False
    log(f"   filtro de jogo: {hms(segundos)} da live sao de \"{a.jogo}\" (a live tem: {nomes})")
    return nota, False, True


# ------------------------------------------------------------ live finalizada

def processar(url, a):
    """Corta uma live inteira. Devolve quantos cortes novos sairam (0 e um resultado valido)."""
    t_ini = time.time()
    log(f"\n=== {url}")
    info = info_vod(url)
    _diario(a, "radar", f"analisando a live inteira: {info['titulo'][:60]}")
    log(f"   canal: {info['canal']} | duracao: {hms(info['duracao'])} | {info['titulo'][:70]}")
    saida, tmp = _pastas(info)
    try:
        hls_audio = ler_hls(url, "ba/w")
        hls_video = ler_hls(url, "b[height<=1080]/b") if hls_audio else None

        log("1/3 analisando o audio da live")
        limite = a.limite_min * 60
        rms = analisar_audio(url, hls_audio, 0, limite or None)
        total = len(rms)
        if total < 120:
            raise RuntimeError("Nao consegui analisar o audio (video curto demais ou download bloqueado).")
        if not hls_audio and not limite and info["duracao"] and total < 0.97 * info["duracao"]:
            raise RuntimeError(f"O download do audio parou em {hms(total)} de {hms(info['duracao'])}; tente de novo.")
        chat = None
        if not a.sem_chat:
            log("   lendo o replay do chat")
            chat = obter_chat(url, info, 0, total, tmp, 180 if limite else 900)
            if chat is not None and float(np.nansum(chat)) > 0:
                log(f"   chat lido: media de {float(np.nanmean(chat)) * 60:.0f} mensagens por minuto")
            else:
                chat = None
                log("   sem chat disponivel")
        clipes = [] if a.sem_clipes else [c for c in obter_clipes(url, info, total) if c[0] < total]
        if clipes:
            log(f"   clipes de espectadores nesta live: {len(clipes)} (o maior com {max(c[2] for c in clipes)} views)")

        ja = momentos_existentes(info)
        if ja:
            log(f"   {len(ja)} momento(s) desta live ja viraram corte antes e serao pulados")
        nota, jogo_ia, segue = _filtro_de_jogo(url, a, pontuar(rms, chat, clipes))
        picos = achar_picos(nota, _candidatos(a, a.cortes), max(90, a.duracao * 2), a.pular_inicio,
                            evitar=ja) if segue else []
        log(f"2/3 {len(picos)} momentos candidatos: " + ", ".join(hms(p) for p, _ in picos))
        log("3/3 gerando os cortes")
        with FILA.vez(getattr(a, "prioridade", 5)):
            r = gerar_cortes(url, info, hls_video, picos, a, a.cortes, tmp, saida, total, rms, chat, clipes, jogo_ia)
        lembrar_reprovados(info, r["descartados"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log(f"Concluido: {len(r['feitos'])} cortes em {saida} ({time.time() - t_ini:.0f}s)")
    return len(r["feitos"])


# ------------------------------------------------------- modo vigia (ao vivo)

def _carregar_estado(vid):
    vazio = {"rms": np.zeros(0, np.float32), "chat": np.zeros(0, np.float32), "cortados": [], "avaliados": [],
             "fim": False}
    arq = ESTADO / f"{vid}.npz"
    if not arq.exists():
        return vazio
    try:
        d = np.load(arq, allow_pickle=False)
        return {"rms": d["rms"], "chat": d["chat"], "cortados": [int(x) for x in d["cortados"]],
                "avaliados": [int(x) for x in d["avaliados"]] if "avaliados" in d else [], "fim": bool(d["fim"])}
    except Exception:
        return vazio


def _salvar_estado(vid, e):
    ESTADO.mkdir(exist_ok=True)
    parcial = ESTADO / f"{vid}.tmp.npz"
    np.savez(parcial, rms=e["rms"], chat=e["chat"], cortados=np.array(e["cortados"], dtype=np.int64),
             avaliados=np.array(e["avaliados"], dtype=np.int64), fim=np.array(e["fim"]))
    os.replace(parcial, ESTADO / f"{vid}.npz")


def _ja_processados():
    return set(PROCESSADOS.read_text(encoding="utf-8").split()) if PROCESSADOS.exists() else set()


def _marcar_processado(url):
    with _ARQUIVOS, open(PROCESSADOS, "a", encoding="utf-8") as f:
        f.write(url + "\n")


def _vid(vod):
    return limpar_nome(vod.rstrip("/").split("/")[-1].split("?v=")[-1])


def _contar_falha(vod):
    """Depois de 3 falhas seguidas o VOD e deixado de lado, para a vigia nao insistir para sempre."""
    ESTADO.mkdir(exist_ok=True)
    with _ARQUIVOS:
        try:
            falhas = json.loads(FALHAS.read_text(encoding="utf-8"))
        except Exception:
            falhas = {}
        falhas[vod] = falhas.get(vod, 0) + 1
        FALHAS.write_text(json.dumps(falhas, indent=1), encoding="utf-8")
    if falhas[vod] >= 3:
        _marcar_processado(vod)
        log(f"   {vod}: falhou 3 vezes, nao sera tentado de novo")


def cota_da_rodada(a, total, ja_feitos, primeira):
    """Quantos cortes novos esta rodada pode gerar. A cota por hora vale para a live inteira, nao por rodada."""
    cota_total = max(1, math.ceil(a.por_hora * total / 3600))
    if primeira:
        return cota_total, min(a.cortes, cota_total)
    return cota_total, max(0, cota_total - ja_feitos)


def _vigiar_vod(vod, a, estado_lista=""):
    hls_audio = ler_hls(vod, "ba/w")
    if not hls_audio:
        # YouTube: so da para cortar depois que a live termina
        info = info_vod(vod)
        if info["estado"] in ("is_live", "is_upcoming"):
            log(f"{info['canal']}: live em andamento em fonte sem leitura parcial; corto quando terminar")
            return
        # O YouTube nao informa o jogo da live. Para nao baixar horas de video de outro jogo,
        # com --jogo so entra a live cujo titulo cita o jogo; a IA ainda confere corte a corte.
        termos = termos_do_jogo(a)
        if termos and not e_o_jogo(info["titulo"], termos):
            log(f"{info['canal']}: live encerrada, mas o titulo nao cita \"{a.jogo}\" ({info['titulo'][:50]})")
            _marcar_processado(vod)
            return
        processar(vod, a)
        _marcar_processado(vod)  # mesmo com zero cortes: o trabalho foi feito, nao ha por que repetir
        return

    vid = _vid(vod)
    e = _carregar_estado(vid)
    feito, total = len(e["rms"]), int(hls_audio["total"])
    # A Kick marca a lista de segmentos como finalizada mesmo com a live no ar, entao a lista sozinha
    # nao basta: so vale "encerrada" se a plataforma tambem nao disser que esta ao vivo.
    no_ar = estado_lista == "is_live" or not hls_audio["fim"]
    if e["fim"] or (total - feito < 90 and no_ar):
        return
    info = info_vod(vod)
    encerrada = not no_ar and info["estado"] != "is_live"
    primeira = feito == 0 and not e["cortados"]

    # Com --jogo, confere o jogo antes de baixar qualquer coisa: enquanto o streamer nao esta no jogo
    # pedido, a rodada termina aqui e nao custa quase nada.
    termos = termos_do_jogo(a)
    if termos:
        situacao = "live encerrada" if encerrada else "no ar"
        caps = capitulos_de_jogo(vod)  # Twitch: jogo de cada trecho
        cats = info.get("categorias") or []  # Kick: categoria da live
        if caps:
            comecos = [c[0] for c in caps if e_o_jogo(c[2], termos)]
            sem_o_jogo, atual = not comecos, caps[-1][2]
        else:
            comecos = []
            sem_o_jogo, atual = bool(cats) and not any(e_o_jogo(c, termos) for c in cats), ", ".join(cats)
        if sem_o_jogo:
            log(f"{info['canal']}: {situacao}, mas sem \"{a.jogo}\" (jogo atual: {atual})")
            if encerrada:
                e["fim"] = True
                _marcar_processado(vod)
                _salvar_estado(vid, e)
            return
        if comecos:
            # nao ha por que analisar as horas anteriores ao jogo: comeca 15 minutos antes do primeiro trecho dele
            pular_ate = int(max(0, min(comecos) - 900))
            if feito < pular_ate <= total:
                n = pular_ate - feito
                e["rms"] = np.concatenate([e["rms"], np.full(n, 100.0, dtype=np.float32)])
                e["chat"] = np.concatenate([e["chat"], np.full(n, np.nan, dtype=np.float32)])
                feito = pular_ate
    log(f"\n=== {info['canal']}: {hms(feito)} -> {hms(total)}" + (" (live encerrada)" if encerrada else " (no ar)"))
    _diario(a, "radar", f"ouvindo a live de {hms(feito)} ate {hms(total)}" + (" (encerrada)" if encerrada else " (no ar)"))
    saida, tmp = _pastas(info)
    inicio_novo = feito  # daqui para frente e o que aconteceu desde a ultima rodada
    try:
        if total > feito:
            novo, ok = analisar_audio(vod, hls_audio, feito, total, com_mascara=True)
            validos = len(novo)
            if not encerrada and validos:
                # os ultimos segmentos podem ainda nao estar disponiveis: paro antes do primeiro buraco da cauda
                cauda_ok = ok[-60:]
                buracos = np.where(~cauda_ok)[0]
                if len(buracos):
                    validos = validos - len(cauda_ok) + int(buracos[0])
            if validos <= 0:
                log("   audio novo ainda indisponivel, tento na proxima rodada")
                return
            total = feito + validos
            chat_novo = None if a.sem_chat else obter_chat(vod, info, feito, total, tmp)
            if chat_novo is None or len(chat_novo) != validos:
                chat_novo = np.full(validos, np.nan, dtype=np.float32)  # sem dado: nao conta nem contra nem a favor
            e["rms"] = np.concatenate([e["rms"], novo[:validos]])
            e["chat"] = np.concatenate([e["chat"], chat_novo])
            _salvar_estado(vid, e)  # a analise fica guardada mesmo que o corte falhe adiante
        total = len(e["rms"])
        if total >= 240:
            chat = e["chat"] if (np.isfinite(e["chat"]).any() and float(np.nansum(e["chat"])) > 0) else None
            clipes = [] if a.sem_clipes else [c for c in obter_clipes(vod, info, total) if c[0] < total]
            nota, jogo_ia, segue = _filtro_de_jogo(vod, a, pontuar(e["rms"], chat, clipes))
            espaco = max(90, a.duracao * 2)
            cauda = 0 if encerrada else int(a.duracao * 0.4) + 15  # o fim do corte precisa ja existir
            cota_total, vaga = cota_da_rodada(a, total, len(e["cortados"]), primeira)
            picos = []
            if vaga > 0 and segue:
                # so entram momentos que estao entre os melhores da live inteira ate agora
                melhores = {p for p, _ in achar_picos(nota, _candidatos(a, cota_total), espaco, a.pular_inicio, cauda)}
                vistos = e["cortados"] + e["avaliados"] + momentos_existentes(info)
                quer = _candidatos(a, vaga)
                if primeira:
                    picos = [(p, n) for p, n in achar_picos(nota, quer, espaco, a.pular_inicio, cauda, evitar=vistos)
                             if p in melhores]
                else:
                    # Com a live no ar, so entra o que aconteceu nos ultimos ~20 minutos: postar rapido e o que
                    # importa. Se nada recente estiver entre os melhores, a vaga fica guardada para a proxima
                    # rodada. Os bons momentos antigos que sobraram entram quando a live termina.
                    recente = nota.copy()
                    recente[:max(0, inicio_novo - 1200)] = -np.inf
                    picos = [(p, n) for p, n in achar_picos(recente, quer, espaco, a.pular_inicio, cauda, evitar=vistos)
                             if p in melhores]
                    if encerrada and len(picos) < quer:
                        ja = vistos + [p for p, _ in picos]
                        picos += [(p, n) for p, n in achar_picos(nota, quer, espaco, a.pular_inicio, cauda, evitar=ja)
                                  if p in melhores][:quer - len(picos)]
            if picos:
                log(f"   {len(picos)} momento(s) novo(s): " + ", ".join(hms(p) for p, _ in picos))
                _diario(a, "radar", f"achou {len(picos)} momento(s): " + ", ".join(hms(p) for p, _ in picos))
                hls_video = ler_hls(vod, "b[height<=1080]/b")
                with FILA.vez(getattr(a, "prioridade", 5)):
                    r = gerar_cortes(vod, info, hls_video, picos, a, vaga, tmp, saida, total, e["rms"], chat, clipes,
                                     jogo_ia)
                e["cortados"] += r["feitos"]
                e["avaliados"] += r["descartados"]
                log(f"   {len(r['feitos'])} corte(s) novo(s) em {saida} "
                    f"({len(e['cortados'])} de {cota_total} da cota desta live)")
            else:
                log("   nenhum momento novo entre os melhores da live")
                _diario(a, "radar", "nada de novo entre os melhores momentos da live")
        if encerrada:
            e["fim"] = True
            _marcar_processado(vod)
        _salvar_estado(vid, e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def vigiar_canal(canal_url, a):
    vods = ultimos_vods(canal_url, 3)
    if not vods:
        log(f"{canal_url}: nenhum VOD encontrado")
        _diario(a, "radar", "canal sem live nem gravacao disponivel")
        return
    ja = _ja_processados()
    alvos, achou_atual = [], False
    for vod, estado in vods:
        if estado == "is_upcoming":
            continue  # live so agendada: olha a proxima da lista
        if not achou_atual:
            achou_atual = True
            if vod not in ja:
                alvos.append((vod, estado))
        elif vod not in ja and (ESTADO / f"{_vid(vod)}.npz").exists():
            alvos.append((vod, estado))  # live anterior que ficou pela metade (caiu e reiniciou, vigia desligada)
    for vod, estado in reversed(alvos):
        try:
            _vigiar_vod(vod, a, estado)
        except Exception as err:
            log(f"ERRO em {vod}: {err}")
            _diario(a, "lider", f"problema nesta live, tento de novo na proxima rodada: {str(err)[:90]}")
            _contar_falha(vod)


def _rodada_do_canal(canal, a, carteira):
    # o nome do fio vira prefixo no log: com varios canais ao mesmo tempo as linhas se misturam
    threading.current_thread().name = f"canal:{canal.nome}"
    esteira.marcar_atividade(ATIVIDADE, canal.chave, "olhando a live")
    try:
        vigiar_canal(canal.url, agencia.opcoes_do_canal(a, canal))
        esteira.marcar_atividade(ATIVIDADE, canal.chave, "esperando a proxima rodada")
        # o corte sobe para os gestores assim que o time termina, sem esperar os outros canais: numa rodada
        # com uma live de 30 horas na fila, esperar o fim deixaria o CEO sem nada por muito tempo
        rodar_esteira(carteira, a)
    except Exception as err:  # um canal com problema nunca pode parar a rodada dos outros
        log(f"ERRO em {canal.url}: {err}")
        esteira.marcar_atividade(ATIVIDADE, canal.chave, f"com problema: {str(err)[:80]}")


def rodada(carteira, a):
    """
    Uma passada por todos os canais, varios ao mesmo tempo. Em fila, uma live de 6 horas lida pela
    primeira vez segurava todos os outros canais por minutos; agora so a etapa pesada espera a vez.
    """
    ordem = sorted(carteira, key=lambda c: c.prioridade)
    with ThreadPoolExecutor(max_workers=max(1, min(a.paralelos, len(ordem)))) as pool:
        list(pool.map(lambda c: _rodada_do_canal(c, a, carteira), ordem))


def _time_do_pedido(pedido, arquivo, info):
    """
    O time que atende o pedido: o que o CEO escolheu, ou o do canal do video. Se o canal ainda nao tem
    time, cria um que so trabalha a pedido (vigiar=nao): passar uma live antiga nao e pedir para seguir o canal.
    """
    carteira = agencia.ler_carteira(arquivo) if Path(arquivo).exists() else []
    por_chave = {c.chave: c for c in carteira}
    if pedido.get("time") in por_chave:
        return por_chave[pedido["time"]]
    nome = (pedido.get("canal") or info["login"].lstrip("@") or limpar_nome(info["canal"])).lower()
    chave = f"{pedido['plataforma']}:{nome}"
    if chave in por_chave:
        return por_chave[chave]
    return agencia.adicionar_canal(arquivo, pedidos.link_do_canal(pedido["plataforma"], nome), cliente=info["canal"], vigiar=False)


def atender_pedidos(a, arquivo):
    """Corta as lives que o CEO passou pelo escritorio, uma por vez. Devolve quantos pedidos atendeu."""
    atendidos = 0
    while True:
        pedido = pedidos.reivindicar(ESTADO)
        if not pedido:
            return atendidos
        atendidos += 1
        try:
            canal = _time_do_pedido(pedido, arquivo, info_vod(pedido["url"]))
            opcoes = agencia.opcoes_do_canal(a, canal)
            opcoes.cortes = pedido.get("cortes") or opcoes.cortes
            opcoes.jogo = pedido.get("jogo") or opcoes.jogo
            threading.current_thread().name = f"canal:{canal.nome}"
            esteira.marcar_atividade(ATIVIDADE, canal.chave, "cortando uma live a pedido do CEO")
            _diario(opcoes, "lider", f"recebeu do CEO uma live para cortar: {pedido['url']}")
            feitos = processar(pedido["url"], opcoes)
            _marcar_processado(pedido["url"])  # a vigia nao precisa cortar de novo a mesma live
            pedidos.concluir(ESTADO, pedido["id"], "feito", f"{feitos} corte(s) para a esteira", time=canal.chave)
            esteira.marcar_atividade(ATIVIDADE, canal.chave, "pedido do CEO concluido")
        except Exception as err:  # um pedido com problema nao pode travar a fila nem derrubar a vigia
            log(f"ERRO no pedido {pedido['url']}: {err}")
            pedidos.concluir(ESTADO, pedido["id"], "erro", str(err)[:200])
        finally:
            threading.current_thread().name = "MainThread"
        try:
            rodar_esteira(agencia.ler_carteira(arquivo), a)
        except agencia.ErroDeCarteira as err:
            log(f"ERRO na carteira {arquivo}: {err}")


def vigiar(a):
    carteira = agencia.ler_carteira(a.vigiar)
    log(f"Vigiando {sum(c.vigiar for c in carteira)} canal(is), ate {a.paralelos} ao mesmo tempo, uma rodada a cada "
        f"{a.intervalo} min. Feche a janela ou Ctrl+C para parar.")
    while True:
        t_ini = time.time()
        try:
            # relida a cada rodada: canal que o CEO acrescentou pelo escritorio entra sem reiniciar a vigia
            carteira = agencia.ler_carteira(a.vigiar)
        except (OSError, agencia.ErroDeCarteira) as err:
            log(f"ERRO ao reler {a.vigiar} ({err}); sigo com a lista anterior")
        atender_pedidos(a, a.vigiar)
        seguidos = [c for c in carteira if c.vigiar]
        if seguidos:
            rodada(seguidos, a)
            log(f"Rodada completa em {time.time() - t_ini:.0f}s")
            rodar_esteira(carteira, a)
        if a.uma_rodada:
            return
        # O intervalo conta do comeco da rodada: rodada longa nao pode atrasar a seguinte e envelhecer os cortes.
        # A espera e em passos curtos para um pedido do CEO ser atendido em segundos, e nao so na proxima rodada.
        while time.time() - t_ini < a.intervalo * 60:
            if pedidos.ha_pendentes(ESTADO):
                atender_pedidos(a, a.vigiar)
            time.sleep(5)


def _todos_os_cortes():
    return agencia.ler_cortes(PASTAS)


def _quadros_do_corte(mp4, dados):
    dur = float(dados.get("duracao") or 0) or video.duracao_de(mp4)
    return video.quadros(mp4, 0, dur) if dur else []


def rodar_esteira(carteira, a):
    """Revisor, gestor e lider trabalham depois dos clipadores, fora da fila pesada: nao usam Whisper nem render."""
    try:
        empresa = esteira.carregar_empresa(RAIZ / "empresa.json")
        gestor = None if (a.sem_ia or ia.modo() != "assinatura") else ia.parecer_do_gestor
        with FILA.vez(1):  # os quadros usam ffmpeg; a esteira passa na frente porque e rapida e destrava o CEO
            resumo = esteira.rodar(PASTAS, carteira, empresa, gestor, _quadros_do_corte, log=log,
                                   evento=lambda chave, papel, texto: esteira.registrar_evento(ESTADO, chave, papel, texto))
        if resumo["subiram_ao_ceo"] and not getattr(a, "sem_aviso", False):
            aviso.avisar(*aviso.texto_dos_cortes(resumo["subiram_ao_ceo"], resumo["aguardando_ceo"]),
                         link=f"http://127.0.0.1:{getattr(a, 'porta', 8765)}/")
        return resumo
    except Exception as err:  # a esteira nunca pode derrubar a vigia
        log(f"ERRO na esteira: {err}")
        return None


def postar_aprovados(a):
    carteira = agencia.ler_carteira(a.carteira)
    plataformas = postagem.PLATAFORMAS if a.postar == "todas" else (a.postar,)
    for plataforma in plataformas:
        log(f"\n=== postagem: {plataforma}" + ("" if plataforma == "tiktok" else f" ({a.visibilidade})"))
        postagem.postar(_todos_os_cortes(), carteira, plataforma, SEGREDOS, a.visibilidade, a.limite, a.simular,
                        log=log)


def painel(arquivo, dias):
    carteira = agencia.ler_carteira(arquivo) if arquivo and Path(arquivo).exists() else []
    desde = datetime.datetime.now() - datetime.timedelta(days=dias) if dias else None
    log(agencia.texto_do_painel(agencia.resumo_por_canal(carteira, _todos_os_cortes(), desde), dias))


# ------------------------------------- titulo e legendas para cortes ja prontos

def titular(todos=False):
    """Gera titulo e legendas pela IA para os cortes de prontos/ que ainda nao tem (ou todos, com --refazer)."""
    if not ia.disponivel():
        log("A IA precisa do Claude Code instalado e logado, ou de uma chave em chave_api.txt (veja ia.py).")
        return
    base = RAIZ / "prontos"
    total = 0
    for pasta in sorted(p for p in base.iterdir() if p.is_dir()) if base.exists() else []:
        lote, canal, live = [], pasta.name.rsplit("_", 1)[0], ""
        for mp4 in sorted(pasta.glob("*.mp4")):
            lado, dados = mp4.with_suffix(".json"), {}
            if lado.exists():
                try:
                    dados = json.loads(lado.read_text(encoding="utf-8"))
                except ValueError:
                    dados = {}
            if dados.get("titulo") and not todos:
                continue
            fala = dados.get("fala", "")
            txt = mp4.with_suffix(".txt")
            if txt.exists():  # cortes antigos guardavam os dados em texto
                antigo = txt.read_text(encoding="utf-8", errors="replace")
                fala = fala or antigo.partition("Fala transcrita:")[2].strip()
                for linha in antigo.splitlines():
                    if linha.startswith("Canal: "):
                        dados.setdefault("canal", linha[7:].strip())
                    elif linha.startswith("Live: "):
                        dados.setdefault("live", linha[6:].strip())
                    elif linha.startswith("Origem: "):
                        dados.setdefault("origem", linha[8:].strip())
            canal, live = dados.get("canal", canal), dados.get("live", live)
            dur = video.duracao_de(mp4)
            lote.append((mp4, dados, {"id": mp4.stem, "trecho": dados.get("trecho", mp4.stem),
                                      "sinais": dados.get("sinais", ""), "fala": fala,
                                      "quadros": video.quadros(mp4, 0, dur) if dur else []}))
        for i in range(0, len(lote), 10):
            parte = lote[i:i + 10]
            log(f"{pasta.name}: avaliando {len(parte)} corte(s)")
            try:
                aval = ia.avaliar([c for _, _, c in parte], canal, live)
            except Exception as err:
                log(f"   IA falhou ({str(err)[:120]})")
                aval = None
            if not aval:
                return
            for mp4, dados, c in parte:
                r = aval.get(c["id"])
                if not r:
                    continue
                dados.update({"canal": canal, "live": live, "fala": c["fala"], "titulo": r["titulo"],
                              "tiktok": r["legenda_tiktok"], "shorts": r["legenda_shorts"],
                              "nota_ia": r["nota"], "motivo": r["motivo"], "jogo": r.get("jogo", ""),
                              "contexto": r.get("contexto", ""), "cutscene": r.get("cutscene", False)})
                dados.setdefault("gancho", "")
                if "musica" not in dados:  # cortes antigos: mede a musica no video ja pronto
                    som = musica.analisar(mp4.with_suffix(".base") if mp4.with_suffix(".base").exists() else mp4)
                    if som:
                        dados.update({"musica": som["nivel"], "musica_pct": som["musica_pct"],
                                      "musica_forte_s": som["musica_forte_s"]})
                mp4.with_suffix(".json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
                total += 1
                log(f"   {mp4.name}: nota {r['nota']} | {r['titulo']}")
    log(f"Titulo e legendas gerados para {total} corte(s).")


# --------------------------------------------------- desempenho dos cortes postados

def desempenho():
    """Resume as views anotadas na tela de revisao (aba Aprovados) por streamer, jogo, enquadramento etc."""
    cortes = []
    for lado in (RAIZ / "aprovados").rglob("*.json") if (RAIZ / "aprovados").exists() else []:
        try:
            d = json.loads(lado.read_text(encoding="utf-8"))
        except ValueError:
            continue
        views = (d.get("views_tiktok") or 0) + (d.get("views_shorts") or 0)
        if views:
            cortes.append((d, views))
    if not cortes:
        log("Nenhum corte aprovado tem views anotadas ainda. Depois de postar, abra a tela de revisao,\n"
            "va na aba Aprovados e preencha as views de cada corte.")
        return
    log(f"{len(cortes)} corte(s) com views anotadas, {sum(v for _, v in cortes):,} views no total".replace(",", "."))
    if len(cortes) < 10:
        log("Aviso: com menos de 10 cortes as medias abaixo ainda sao muito instaveis.")

    def faixa_nota(d):
        n = d.get("nota_ia")
        return "sem nota" if n is None else ("nota 8 a 10" if n >= 8 else "nota 6 a 7" if n >= 6 else "nota ate 5")

    def faixa_duracao(d):
        s = d.get("duracao") or 0
        return "ate 30 s" if s <= 30 else "31 a 45 s" if s <= 45 else "46 a 60 s"

    grupos = [("Streamer", lambda d: d.get("canal") or "?"), ("Jogo", lambda d: d.get("jogo") or "?"),
              ("Enquadramento", lambda d: d.get("enquadramento") or "?"), ("Nota da IA", faixa_nota),
              ("Musica", lambda d: d.get("musica") or "?"), ("Duracao", faixa_duracao),
              ("Texto no video", lambda d: "sem texto" if not d.get("comentario") else
               "contexto da IA" if d.get("comentario_auto") else "comentario seu")]
    for titulo, chave in grupos:
        tabela = {}
        for d, v in cortes:
            tabela.setdefault(chave(d), []).append(v)
        log(f"\n{titulo}")
        for nome, vs in sorted(tabela.items(), key=lambda kv: -sorted(kv[1])[len(kv[1]) // 2]):
            mediana = sorted(vs)[len(vs) // 2]
            log(f"   {str(nome)[:34]:<34} {len(vs):>3} corte(s) | mediana {mediana:>9,} | melhor {max(vs):>9,}".replace(",", "."))
    log("\nMelhores cortes:")
    for d, v in sorted(cortes, key=lambda x: -x[1])[:5]:
        log(f"   {v:>9,} views | {d.get('canal', '?')} | {d.get('titulo', '')[:60]}".replace(",", "."))


# ----------------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description="Gera cortes verticais de lives para TikTok e Shorts")
    p.add_argument("url", nargs="?", help="link do VOD (Twitch, Kick ou YouTube)")
    p.add_argument("--canais", help="arquivo com um link de canal por linha; usa o VOD mais recente de cada")
    p.add_argument("--vigiar", help="arquivo de canais para acompanhar: corta enquanto a live esta no ar")
    p.add_argument("--revisar", action="store_true", help="abre a tela de revisao dos cortes")
    p.add_argument("--titular", action="store_true",
                   help="gera titulo e legendas pela IA para os cortes prontos que ainda nao tem")
    p.add_argument("--refazer", action="store_true", help="com --titular: refaz tambem os que ja tem titulo")
    p.add_argument("--desempenho", action="store_true",
                   help="mostra o que rende mais, a partir das views anotadas nos cortes aprovados")
    p.add_argument("--painel", nargs="?", const="canais.txt", metavar="CANAIS",
                   help="mostra producao, aprovacao, views e receita estimada por canal da carteira")
    p.add_argument("--pedidos", action="store_true",
                   help="atende os links que o CEO passou pelo escritorio (fila em estado/pedidos.json) e sai")
    p.add_argument("--escritorio", action="store_true", help="com --revisar: abre direto no escritorio")
    p.add_argument("--esteira", action="store_true",
                   help="passa os cortes prontos por revisor, gestor e lider (a vigia ja faz isso a cada rodada)")
    p.add_argument("--avaliacao", action="store_true",
                   help="desempenho de cada clipador e do gestor, medido pelas suas decisoes")
    p.add_argument("--conectar", choices=postagem.PLATAFORMAS,
                   help="abre o navegador para autorizar uma conta de postagem (uma vez por conta)")
    p.add_argument("--conta", default="principal", help="com --conectar: nome da conta (o mesmo de conta= no canais.txt)")
    p.add_argument("--postar", choices=[*postagem.PLATAFORMAS, "todas"],
                   help="posta os cortes aprovados dos canais com autorizado=sim (TikTok: como rascunho)")
    p.add_argument("--visibilidade", choices=list(postagem.VISIBILIDADES), default="privado",
                   help="com --postar youtube: privado (padrao, para conferir antes), nao_listado ou publico")
    p.add_argument("--limite", type=int, default=0, help="com --postar: no maximo N cortes por plataforma nesta execucao")
    p.add_argument("--simular", action="store_true", help="com --postar: so lista o que seria postado")
    p.add_argument("--carteira", default="canais.txt", help="com --postar e --atualizar-views: arquivo de canais")
    p.add_argument("--atualizar-views", action="store_true", dest="atualizar_views",
                   help="le as views dos Shorts postados e grava nos cortes, para o painel")
    p.add_argument("--dias", type=int, default=30, help="com --painel: periodo considerado (0 = todo o historico)")
    p.add_argument("--paralelos", type=int, default=4,
                   help="modo vigia: quantos canais sao analisados ao mesmo tempo (transcricao e render seguem um por vez)")
    p.add_argument("--intervalo", type=int, default=10, help="modo vigia: minutos entre as rodadas")
    p.add_argument("--por-hora", type=float, default=3, dest="por_hora",
                   help="modo vigia: media de cortes por hora de live")
    p.add_argument("--uma-rodada", action="store_true", dest="uma_rodada", help="modo vigia: faz uma rodada e sai")
    p.add_argument("--cortes", type=int, default=8, help="quantos cortes por live")
    p.add_argument("--duracao", type=int, default=45, help="duracao alvo de cada corte, em segundos")
    p.add_argument("--layout", choices=["blur", "crop"], default="blur", help="usado quando nao ha webcam")
    p.add_argument("--facecam", default="auto",
                   help="'auto' (padrao) detecta a webcam; 'nao' desliga; ou a posicao em fracoes x,y,largura,altura")
    p.add_argument("--zoom", type=float, default=0.75,
                   help="layout blur: fracao da largura da tela que aparece (1.0 = tela inteira)")
    p.add_argument("--gancho", default="", help="texto fixo no topo nos primeiros segundos (a IA gera um por corte)")
    p.add_argument("--sem-fundo", action="store_true", dest="sem_fundo",
                   help="corte de pessoa falando sai com a camera em tela cheia, mesmo com videos na pasta fundos/")
    p.add_argument("--sem-moldura", action="store_true", dest="sem_moldura",
                   help="corte sem webcam sai so com o fundo desfocado, sem a logo e a frase fixa no topo")
    p.add_argument("--sem-contexto", action="store_true", dest="sem_contexto",
                   help="nao escreve no video a frase de contexto da IA (por padrao ela entra depois do gancho; "
                        "da para trocar pela sua opiniao ou tirar na tela de aprovacao)")
    p.add_argument("--sem-aviso", action="store_true", dest="sem_aviso",
                   help="nao mostra a notificacao do Windows quando um corte chega para a sua aprovacao")
    p.add_argument("--tags", default="", help='hashtags do jogo usadas quando nao ha IA, ex: "#gta6 #gtavi"')
    p.add_argument("--sem-credito", action="store_true", dest="sem_credito", help="nao escreve @canal no video")
    p.add_argument("--sem-mascara", action="store_true", dest="sem_mascara",
                   help="nao mascara xingamentos pesados na legenda (lista em palavras_mascaradas.txt)")
    p.add_argument("--sem-musica", action="store_true", dest="sem_musica",
                   help="descarta cortes com musica em destaque (radio do jogo, musica tocando na live)")
    p.add_argument("--estilo-fixo", action="store_true", dest="estilo_fixo",
                   help="usa sempre a mesma cor e fonte na legenda, em vez de variar entre os cortes")
    p.add_argument("--idioma", default="auto",
                   help="idioma da fala para a legenda: 'auto' (padrao) detecta por corte; ou pt, en, es...")
    # large-v3-turbo: medido em cortes de GTA RP, entende a fala bem melhor que o small por ~2x o tempo
    p.add_argument("--modelo", default="large-v3-turbo",
                   help="modelo do Whisper: large-v3-turbo (padrao), medium, small (mais rapido, erra mais)")
    p.add_argument("--margem-legenda", type=int, default=420, dest="margem_legenda")
    p.add_argument("--pular-inicio", type=int, default=180, dest="pular_inicio",
                   help="segundos do comeco da live ignorados na escolha")
    p.add_argument("--nota-minima", type=int, default=5, dest="nota_minima",
                   help="com IA: cortes com nota abaixo disso sao descartados (a nota e triagem, nao previsao)")
    p.add_argument("--candidatos", type=float, default=2.5,
                   help="com IA: quantos candidatos separar por corte desejado, para a IA escolher os melhores")
    p.add_argument("--jogo", default="",
                   help='so corta quando este jogo esta na tela; termos separados por virgula, '
                        'ex: "gta vi, grand theft auto vi, gta 6"')
    p.add_argument("--sem-ia", action="store_true", dest="sem_ia")
    p.add_argument("--sem-clipes", action="store_true", dest="sem_clipes")
    p.add_argument("--sem-legenda", action="store_true", dest="sem_legenda")
    p.add_argument("--legenda-rapida", action="store_true", dest="legenda_rapida",
                   help="nao refaz a transcricao dos cortes escolhidos (mais rapido, legenda um pouco menos precisa)")
    p.add_argument("--sem-chat", action="store_true", dest="sem_chat")
    p.add_argument("--limite-min", type=int, default=0, dest="limite_min",
                   help="analisa so os primeiros N minutos (para teste)")
    p.add_argument("--porta", type=int, default=8765, help="porta da tela de revisao")
    a = p.parse_args()
    a.zoom = min(1.0, max(0.3, a.zoom))
    if a.facecam in ("nao", "não", "off"):
        a.facecam = None
    elif a.facecam != "auto":
        a.facecam = [float(v) for v in a.facecam.split(",")]
        if len(a.facecam) != 4:
            p.error("--facecam precisa de 4 numeros: x,y,largura,altura")

    if a.revisar:
        import revisao
        revisao.servir(a.porta, "/escritorio" if a.escritorio else "/")
        return
    if a.titular:
        titular(a.refazer)
        return
    if a.desempenho:
        desempenho()
        return
    if a.esteira or a.avaliacao:
        try:
            carteira = agencia.ler_carteira(a.carteira) if Path(a.carteira).exists() else []
        except agencia.ErroDeCarteira as err:
            p.error(f"{a.carteira}: {err}")
        if a.esteira:
            rodar_esteira(carteira, a)
        else:
            log(esteira.texto_da_avaliacao(*esteira.avaliacao(_todos_os_cortes(), carteira)))
        return
    if a.conectar or a.postar or a.atualizar_views:
        try:
            if a.conectar:
                postagem.conectar(SEGREDOS, a.conectar, a.conta, log=log)
            elif a.postar:
                postar_aprovados(a)
            else:
                postagem.atualizar_views(_todos_os_cortes(), agencia.ler_carteira(a.carteira), SEGREDOS, log=log)
        except agencia.ErroDeCarteira as err:
            p.error(f"{a.carteira}: {err}")
        except postagem.ErroDePostagem as err:
            p.error(str(err))
        return
    if a.painel:
        try:
            painel(a.painel, a.dias)
        except agencia.ErroDeCarteira as err:
            p.error(f"{a.painel}: {err}")
        return
    if not a.sem_ia:
        log({"api": "IA: ativa pela API paga (nota, titulo, gancho e legendas por corte)",
             "assinatura": "IA: ativa pela sua assinatura do Claude (nota, titulo, gancho e legendas por corte)",
             "": "IA: indisponivel; cortes escolhidos so pelos sinais (veja ia.py)"}[ia.modo()])
    if a.pedidos:
        # so um atendente por vez: se sobrou pedido "em andamento" e porque o atendente anterior morreu
        pedidos.destravar(ESTADO)
        log(f"Pedidos atendidos: {atender_pedidos(a, a.carteira)}")
        return
    if a.vigiar:
        try:
            vigiar(a)
        except agencia.ErroDeCarteira as err:
            p.error(f"{a.vigiar}: {err}")
        except KeyboardInterrupt:
            log("Vigia encerrado.")
        return

    alvos = []  # (link do VOD, opcoes): com --canais cada canal leva as opcoes do proprio contrato
    if a.canais:
        ja = _ja_processados()
        try:
            carteira = agencia.ler_carteira(a.canais)
        except agencia.ErroDeCarteira as err:
            p.error(f"{a.canais}: {err}")
        for canal in carteira:
            vod = ultimo_vod(canal.url)
            if not vod:
                log(f"Sem VOD encontrado em {canal.url}")
            elif vod in ja:
                log(f"Ja processado: {vod}")
            else:
                alvos.append((vod, agencia.opcoes_do_canal(a, canal)))
    elif a.url:
        alvos.append((a.url, a))
    else:
        p.error("informe o link de um VOD, --canais, --vigiar, --revisar, --titular ou --painel")
    for u, opcoes in alvos:
        try:
            processar(u, opcoes)
            if a.canais:
                _marcar_processado(u)
        except Exception as err:
            log(f"ERRO em {u}: {err}")
    if alvos:
        try:
            carteira = agencia.ler_carteira(a.canais or a.carteira) if Path(a.canais or a.carteira).exists() else []
        except agencia.ErroDeCarteira:
            carteira = []
        rodar_esteira(carteira, a)


if __name__ == "__main__":
    main()
