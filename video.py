"""Tudo que mexe no video: trecho bruto, legenda, limites do corte, webcam e renderizacao."""
import json
import re
import subprocess
import unicodedata

import numpy as np

from fontes import HLS_IN, RAIZ, escrever_hls, log, ytdlp

ROSTO_GRANDE = 0.1025  # rosto acima dessa fracao da largura = camera ocupando quase a tela toda
AMOSTRAS = 16
ARQ_WEBCAMS = RAIZ / "webcams.json"
MODELO_ROSTO = RAIZ / "modelos" / "yunet.onnx"
PASTA_FUNDOS = RAIZ / "fundos"  # videos do dono do canal para a metade de baixo dos cortes de pessoa falando
ARQ_LOGO = RAIZ / "logo.png"  # logo do canal de cortes; se existir, entra no topo dos cortes em moldura

# ------------------------------------------------------------- trecho bruto


def baixar_trecho(url, ini, fim, destino, hls=None):
    """
    Baixa o trecho bruto. Devolve (ok, erro, inicio_real): o segundo da live em que o arquivo comeca.
    Em HLS os segmentos sao copiados sem recodificar (10 vezes mais rapido), entao o arquivo comeca
    no inicio do primeiro segmento, um pouco antes de `ini`.
    """
    if hls:
        usar = [s for s in hls["segs"] if s[0] + s[1] > ini and s[0] < fim]
        if not usar:
            return False, "trecho fora da live", float(ini)
        lista = destino.with_suffix(".m3u8")
        escrever_hls(lista, hls["mapa"], usar)
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *HLS_IN, "-i", lista.name, "-c", "copy",
                            destino.name], cwd=destino.parent, capture_output=True, text=True, errors="replace")
        return destino.exists() and destino.stat().st_size > 10000, (r.stderr or "")[-300:], float(usar[0][0])
    # YouTube: --force-keyframes-at-cuts faz o arquivo comecar exatamente em `ini` (sem ele, comeca
    # no quadro-chave anterior e o corte desloca alguns segundos)
    r = ytdlp("-q", "--download-sections", f"*{ini}-{fim}", "--force-keyframes-at-cuts",
              "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--merge-output-format", "mp4",
              "--force-overwrites", "-o", str(destino), url,
              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors="replace")
    return destino.exists() and destino.stat().st_size > 10000, (r.stderr or "")[-300:], float(ini)


def duracao_de(arquivo):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arquivo)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def quadros(arquivo, ini, fim, quantos=3, largura=512):
    """Alguns quadros do trecho, em JPEG, para a IA ver o que esta na tela."""
    saida = []
    for k in range(quantos):
        t = ini + (fim - ini) * (k + 0.5) / quantos
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(arquivo), "-frames:v", "1",
                            "-vf", f"scale={largura}:-2", "-q:v", "5", "-f", "image2pipe", "-c:v", "mjpeg", "pipe:1"],
                           capture_output=True)
        if r.stdout:
            saida.append(r.stdout)
    return saida


# ------------------------------------------------------------------- legendas

_modelo = None


def transcrever(arquivo, modelo, idioma, ini=0.0, fim=None, preciso=False):
    """
    Devolve [(inicio, fim, palavra)] do pedaco [ini, fim) do arquivo, com tempos a partir de `ini`.
    preciso=False usa busca simples (metade do tempo, texto quase igual): serve para a triagem dos
    candidatos. preciso=True e usado so na legenda final dos cortes escolhidos.
    """
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel
        log(f"   carregando modelo de legenda '{modelo}'")
        _modelo = WhisperModel(modelo, device="cpu", compute_type="int8")
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{ini:.3f}"]
    if fim is not None:
        cmd += ["-t", f"{fim - ini:.3f}"]
    cmd += ["-i", str(arquivo), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"]
    bruto = subprocess.run(cmd, capture_output=True).stdout
    audio = np.frombuffer(bruto[:len(bruto) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
    if len(audio) < 16000:
        return []
    # idioma "auto": o Whisper identifica a lingua de cada corte (lista com streamers brasileiros e de fora)
    segs, dados = _modelo.transcribe(audio, language=None if idioma in ("auto", "", None) else idioma,
                                     word_timestamps=True, vad_filter=True, beam_size=5 if preciso else 1)
    transcrever.idioma = getattr(dados, "language", None)  # lingua detectada, reaproveitada na legenda final
    palavras = []
    for s in segs:
        for w in (s.words or []):
            txt = w.word.strip()
            if txt:
                palavras.append((float(w.start), float(w.end), txt))
    return palavras


def limites_inteligentes(palavras, pico, alvo, total, pausa=0.35, folga=8.0):
    """Escolhe inicio e fim do corte em pausas da fala, perto da duracao alvo e contendo o pico."""
    ini_alvo = max(0.0, min(pico - alvo * 0.6, total - alvo))
    if not palavras:
        return ini_alvo, min(total, ini_alvo + alvo)
    n = len(palavras)
    inicios = [p[0] for i, p in enumerate(palavras) if i == 0 or p[0] - palavras[i - 1][1] >= pausa]
    fins = [p[1] for i, p in enumerate(palavras) if i == n - 1 or palavras[i + 1][0] - p[1] >= pausa]
    perto = [t for t in inicios if abs(t - ini_alvo) <= folga and t < pico - 5]
    ini = max(0.0, min(perto, key=lambda t: abs(t - ini_alvo)) - 0.15) if perto else ini_alvo
    fim_alvo = min(total, ini + alvo)
    perto = [t for t in fins if abs(t - fim_alvo) <= folga and t > pico + 3 and t - ini >= 15]
    fim = min(total, min(perto, key=lambda t: abs(t - fim_alvo)) + 0.3) if perto else fim_alvo
    return ini, fim


def t_ass(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _limpo(txt):
    return txt.replace("{", "").replace("}", "").replace("\n", " ").strip()


# Xingamentos pesados (racismo, homofobia, capacitismo) que fazem TikTok e YouTube restringirem o video.
# Palavrao comum fica de fora de proposito. A lista vale no arquivo abaixo, uma palavra por linha, e pode ser editada.
ARQ_MASCARA = RAIZ / "palavras_mascaradas.txt"
_MASCARA_PADRAO = ("nigga niggas nigger niggers faggot faggots fag fags retard retards retarded tranny trannies "
                   "kike spic chink viado viados viadinho viadinhos boiola boiolas traveco travecos "
                   "retardado retardada retardados mongoloide mongol crioulo crioula").split()
_mascara = None


def _sem_acento(txt):
    return "".join(ch for ch in unicodedata.normalize("NFD", txt.lower()) if unicodedata.category(ch) != "Mn")


def _palavras_mascaradas():
    global _mascara
    if _mascara is None:
        if not ARQ_MASCARA.exists():
            ARQ_MASCARA.write_text("# Palavras que saem mascaradas na legenda e nos textos (uma por linha).\n"
                                   + "\n".join(_MASCARA_PADRAO) + "\n", encoding="utf-8")
        linhas = ARQ_MASCARA.read_text(encoding="utf-8-sig").splitlines()
        _mascara = {_sem_acento(x.strip()) for x in linhas if x.strip() and not x.lstrip().startswith("#")}
    return _mascara


def mascarar(txt):
    """Troca xingamentos pesados por inicial + asteriscos. Devolve (texto, quantas palavras foram mascaradas)."""
    lista, n = _palavras_mascaradas(), 0

    def troca(m):
        nonlocal n
        p = m.group(0)
        if _sem_acento(p) not in lista:
            return p
        n += 1
        return p[0] + "*" * (len(p) - 1)

    return re.sub(r"[^\W\d_]+", troca, txt or ""), n


# Variacoes de visual: cor de destaque da legenda (formato do ASS, &HAABBGGRR), fonte e jeito do gancho.
# Cada corte usa uma combinacao diferente para os videos do canal nao sairem todos com a mesma cara.
CORES = ["&H0000E6FF", "&H0066FF7A", "&H00FFE14D", "&H00338CFF", "&H00B469FF"]  # amarelo, verde, ciano, laranja, rosa
FONTES = ["Arial Black", "Impact", "Segoe UI Black"]


def estilo_do_corte(semente, fixo=False):
    """Escolhe (cor, fonte, gancho_em_caixa) de forma estavel a partir de um numero do corte."""
    if fixo:
        return CORES[0], FONTES[0], False
    s = int(semente)
    return CORES[s % len(CORES)], FONTES[(s // 7) % len(FONTES)], (s // 3) % 2 == 1


def logo_do_canal():
    """Caminho da logo do canal de cortes, ou None se o dono ainda nao pos o arquivo logo.png na pasta."""
    return ARQ_LOGO if ARQ_LOGO.exists() and ARQ_LOGO.stat().st_size > 100 else None


def escolher_fundo(semente, dur, pasta=None, duracao=None):
    """
    Video de fundo para um corte de `dur` segundos: (arquivo, inicio em segundos), ou None se a pasta esta vazia.
    A escolha sai do numero do corte, entao refazer o mesmo corte da o mesmo fundo no mesmo ponto.
    """
    import random
    pasta = PASTA_FUNDOS if pasta is None else pasta
    arquivos = sorted(f for f in pasta.iterdir() if f.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")) \
        if pasta.exists() else []
    if not arquivos:
        return None
    sorteio = random.Random(int(semente))
    arquivo = arquivos[sorteio.randrange(len(arquivos))]
    total = (duracao or duracao_de)(arquivo)
    if not total:
        return None
    return arquivo, round(sorteio.uniform(0, max(0.0, total - dur)), 2)


def escrever_ass(palavras, destino, margem_v, gancho=None, credito=None, duracao=0.0, estilo=None, mascara=True,
                 moldura=None):
    """
    Legenda palavra a palavra, gancho no topo nos primeiros segundos e credito discreto.
    `moldura` e para o corte sem webcam (jogo no meio, faixas livres em cima e embaixo): a frase fica no topo
    o video inteiro, em vez de sumir aos 4 s. Vale "logo" (a frase desce para caber a logo acima) ou "frase".
    """
    if mascara:
        palavras = [(i, f, mascarar(t)[0]) for i, f, t in palavras]
        gancho = mascarar(gancho)[0] if gancho else gancho
    cor, fonte, gancho_caixa = estilo or (CORES[0], FONTES[0], False)
    tam = 96 if fonte == "Impact" else 82  # a Impact e mais estreita; maior para manter o peso na tela
    grupos, atual = [], []
    for ini, fim, txt in palavras:
        letras = sum(len(w[2]) for w in atual) + len(atual) + len(txt)  # linha nao pode passar da largura da tela
        if atual and (len(atual) >= 3 or letras > 18 or ini - atual[-1][1] > 0.6 or fim - atual[0][0] > 1.6):
            grupos.append(atual)
            atual = []
        atual.append((ini, fim, txt))
    if atual:
        grupos.append(atual)
    fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
           "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding")
    linhas = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 2", "",
        "[V4+ Styles]", fmt,
        # efeito karaoke: a palavra nasce branca (cor secundaria) e ganha a cor de destaque (primaria) quando e falada
        f"Style: Leg,{fonte},{tam},{cor},&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,2,2,"
        f"60,60,{margem_v},1",
        # gancho: texto branco com contorno, ou texto preto dentro de uma caixa na cor de destaque
        (f"Style: Gancho,{fonte},{tam - 14},&H00000000,&H000000FF,{cor},&H00000000,-1,0,0,0,100,100,0,0,3,12,0,8,"
         "80,80,130,1") if gancho_caixa else
        (f"Style: Gancho,{fonte},{tam - 8},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,8,3,8,"
         "70,70,130,1"),
        "Style: Cred,Arial,34,&H50FFFFFF,&H000000FF,&H80000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,7,36,36,36,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if credito and duracao:
        linhas.append(f"Dialogue: 0,{t_ass(0)},{t_ass(duracao)},Cred,,0,0,0,,{_limpo(credito)}")
    if gancho and moldura:
        # frase fixa da moldura: menor que o gancho comum porque e uma frase inteira, nao duas palavras
        topo = 335 if moldura == "logo" else 170
        linhas.insert(linhas.index("") + 3, f"Style: Frase,{fonte},{tam - 24},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
                      f"-1,0,0,0,100,100,0,0,1,6,2,8,70,70,{topo},1")
        linhas.append(f"Dialogue: 2,{t_ass(0)},{t_ass(duracao or 4.0)},Frase,,0,0,0,,{{\\q0}}{_limpo(gancho).upper()}")
    elif gancho:
        linhas.append(f"Dialogue: 2,{t_ass(0)},{t_ass(min(4.0, duracao or 4.0))},Gancho,,0,0,0,,"
                      f"{{\\q0\\fad(0,250)}}{_limpo(gancho).upper()}")
    for k, g in enumerate(grupos):
        ini = g[0][0]
        fim = g[-1][1] + 0.15
        if k + 1 < len(grupos):
            fim = min(fim, grupos[k + 1][0][0])
        if fim - ini < 0.2:
            fim = ini + 0.2
        partes = []
        for j, w in enumerate(g):
            ate = g[j + 1][0] if j + 1 < len(g) else w[1]
            partes.append(f"{{\\k{max(1, int(round((ate - w[0]) * 100)))}}}{_limpo(w[2]).upper()}")
        linhas.append(f"Dialogue: 1,{t_ass(ini)},{t_ass(fim)},Leg,,0,0,0,,{' '.join(partes)}")
    destino.write_text("\n".join(linhas), encoding="utf-8")


def queimar_comentario(base, destino, texto, inicio=0.0, voz=None, embaixo=False):
    """
    Escreve o comentario do dono do canal no topo do video, numa caixa branca, de `inicio` ate o fim.
    `base` e o video sem comentario; `destino` e gravado so se tudo der certo. Devolve (ok, erro).
    Com `voz` (arquivo de audio com o comentario falado), a fala entra junto com a caixa e o som do corte
    abaixa enquanto ela dura. `embaixo` poe a caixa na faixa de baixo: e o lugar dela nos cortes em moldura,
    em que o topo ja tem a logo e a frase.
    """
    import tempfile
    from pathlib import Path
    dur = duracao_de(base)
    if not dur:
        return False, "nao consegui ler o video"
    fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
           "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding")
    ass = "\n".join([
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 0", "",
        "[V4+ Styles]", fmt,
        "Style: Coment,Arial,48,&H00101010,&H000000FF,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,3,14,0,"
        + ("2,90,90,330,1" if embaixo else "8,90,90,110,1"),
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 3,{t_ass(min(inicio, max(0.0, dur - 1)))},{t_ass(dur)},Coment,,0,0,0,,{{\\fad(200,0)}}{_limpo(texto)}",
    ])
    destino = Path(destino)
    with tempfile.TemporaryDirectory(prefix="cortes_coment_") as pasta:
        (Path(pasta) / "c.ass").write_text(ass, encoding="utf-8")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(Path(base).resolve())]
        fala = duracao_de(voz) if voz else 0.0
        if fala:
            # a fala comeca um instante depois da caixa aparecer; o corte fica a 30% do volume enquanto ela dura
            a, b = inicio + 0.3, inicio + 0.3 + fala + 0.2
            cmd += ["-i", str(Path(voz).resolve()), "-filter_complex",
                    f"[0:v]ass=c.ass[v];[0:a]volume='if(between(t,{a:.2f},{b:.2f}),0.3,1)':eval=frame[a0];"
                    f"[1:a]aresample=48000,adelay={int(a * 1000)}:all=1,volume=1.5[a1];"
                    "[a0][a1]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
                    "-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
        else:
            cmd += ["-vf", "ass=c.ass", "-c:a", "copy"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-maxrate", "8M", "-bufsize", "16M",
                "-movflags", "+faststart", "-f", "mp4", str(destino.resolve())]
        r = subprocess.run(cmd, cwd=pasta, capture_output=True, text=True, errors="replace")
    ok = r.returncode == 0 and destino.exists() and destino.stat().st_size > 10000
    if not ok:
        destino.unlink(missing_ok=True)
    return ok, (r.stderr or "")[-300:]


# Enquadramentos de pessoa falando, e o pedaco do corte pronto que vira a metade de cima quando entra uma
# imagem embaixo: (y do recorte, altura do recorte). O que sobra ate 1920 e a altura da imagem.
RECORTE_DA_IMAGEM = {"camera cheia": (380, 1200), "camera + video embaixo": (0, 1080)}


def por_imagem(base, destino, imagem, titulo, enquadramento):
    """
    Troca a metade de baixo do corte por uma imagem do assunto (escolhida pelo dono do canal) e poe uma faixa
    com o titulo na emenda. So vale para corte de pessoa falando: nos outros a metade de baixo e o jogo.
    A imagem se aproxima devagar, para a tela nao ficar parada. `destino` so e gravado se der certo.
    Devolve (ok, erro).
    """
    import tempfile
    from pathlib import Path
    if enquadramento not in RECORTE_DA_IMAGEM:
        return False, "imagem embaixo so vale para corte de pessoa falando (camera em tela cheia)"
    y, alto = RECORTE_DA_IMAGEM[enquadramento]
    baixo, dur = 1920 - alto, duracao_de(base)
    if not dur:
        return False, "nao consegui ler o video"
    fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
           "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding")
    ass = "\n".join([
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 0", "",
        "[V4+ Styles]", fmt,
        # faixa vermelha com letra branca, logo abaixo da emenda: em cima dela taparia a legenda do corte
        "Style: Faixa,Impact,62,&H00FFFFFF,&H000000FF,&H001A1AC8,&H00000000,-1,0,0,0,100,100,1,0,3,16,0,5,110,110,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 5,{t_ass(0)},{t_ass(dur)},Faixa,,0,0,0,,{{\\pos(540,{alto + 100})}}{_limpo(titulo).upper()}",
    ])
    destino = Path(destino)
    zoom = f"(1+0.10*t/{dur:.2f})"
    filtro = (f"[0:v]crop=1080:{alto}:0:{y},setsar=1[cima];"
              f"[1:v]scale=1080:{baixo}:force_original_aspect_ratio=increase,crop=1080:{baixo},"
              f"scale=w='trunc(1080*{zoom}/2)*2':h='trunc({baixo}*{zoom}/2)*2':eval=frame,crop=1080:{baixo},"
              f"setsar=1,fps=60[baixo];[cima][baixo]vstack=shortest=1,fps=60"
              + (",ass=f.ass" if titulo.strip() else "") + ",format=yuv420p[v]")
    with tempfile.TemporaryDirectory(prefix="cortes_imagem_") as pasta:
        (Path(pasta) / "f.ass").write_text(ass, encoding="utf-8")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(Path(base).resolve()),
               "-loop", "1", "-framerate", "60", "-i", str(Path(imagem).resolve()),
               "-filter_complex", filtro, "-map", "[v]", "-map", "0:a?", "-t", f"{dur:.3f}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-maxrate", "8M", "-bufsize", "16M",
               "-c:a", "copy", "-movflags", "+faststart", "-f", "mp4", str(destino.resolve())]
        r = subprocess.run(cmd, cwd=pasta, capture_output=True, text=True, errors="replace")
    ok = r.returncode == 0 and destino.exists() and destino.stat().st_size > 10000
    if not ok:
        destino.unlink(missing_ok=True)
    return ok, (r.stderr or "")[-300:]


# --------------------------------------------------------------------- webcam

def detectar_rostos(video, ini=0.0, fim=None):
    """Amostra quadros do trecho e devolve (largura/altura, [(quadro, cx, cy, tamanho)]) em fracoes da tela."""
    try:
        import cv2
    except ImportError:
        return 16 / 9, []
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W, H = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    if total < 10 or not W or not H:
        return 16 / 9, []
    a, b = int(ini * fps), int(min(total, (fim * fps) if fim else total))
    # YuNet (rede neural do projeto OpenCV) e o detector principal. O antigo, por cascata, confundia
    # icones do jogo com rostos (um coracao partido num botao virou "webcam" num corte de Free Fire);
    # fica so como reserva, caso o arquivo do modelo nao esteja na pasta modelos/.
    yunet = None
    if MODELO_ROSTO.exists() and hasattr(cv2, "FaceDetectorYN"):
        lw = 960
        lh = int(round(H * lw / W))
        try:
            yunet = cv2.FaceDetectorYN.create(str(MODELO_ROSTO), "", (lw, lh), 0.8, 0.3, 50)
        except Exception:
            yunet = None
    cascata = None if yunet else cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    rostos = []
    for i in range(AMOSTRAS):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(a + (b - a) * (i + 0.5) / AMOSTRAS))
        ok, quadro = cap.read()
        if not ok:
            continue
        if yunet:
            _, achados = yunet.detect(cv2.resize(quadro, (lw, lh)))
            for f in (achados if achados is not None else []):
                rostos.append((i, float(f[0] + f[2] / 2) / lw, float(f[1] + f[3] / 2) / lh, float(f[2]) / lw))
        else:
            cinza = cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY)
            m = int(H // 28)
            for (x, y, w, h) in cascata.detectMultiScale(cinza, 1.1, 6, minSize=(m, m)):
                rostos.append((i, (x + w / 2) / W, (y + h / 2) / H, w / W))
    cap.release()
    return W / H, rostos


def _caixa(cx, cy, s, aspecto):
    """Regiao da webcam em volta de um rosto: x, y, largura, altura (fracoes da tela)."""
    a = min(1.0, 2.6 * s * aspecto)
    l = min(1.0, a / aspecto * 1080 / 640)
    x = min(max(0.0, cx - l / 2), 1 - l)
    y = min(max(0.0, cy - a * 0.45), 1 - a)
    return [round(v, 4) for v in (x, y, l, a)]


def _maior_grupo(pontos):
    """pontos: [(chave, cx, cy, s)]. Devolve o grupo de rostos proximos presente em mais quadros distintos."""
    melhor = []
    for (_, cx, cy, _) in pontos:
        perto = [p for p in pontos if abs(p[1] - cx) < 0.05 and abs(p[2] - cy) < 0.07]
        if len({p[0] for p in perto}) > len({p[0] for p in melhor}):
            melhor = perto
    return melhor


def carregar_webcams():
    try:
        return json.loads(ARQ_WEBCAMS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def escolher_webcams(canal, deteccoes):
    """
    deteccoes: {nome_do_corte: (aspecto, rostos)}. Acha a posicao fixa da webcam olhando todos os cortes
    da live juntos (e o que ja foi salvo para o canal) e decide o enquadramento de cada corte:
      [x, y, l, a] -> webcam em cima e jogo embaixo
      ("cheia", cx) -> camera ocupa a tela: recorte vertical centrado no rosto
      None          -> layout de fundo desfocado
    """
    salvas = carregar_webcams()
    pequenos, aspecto = [], 16 / 9
    for nome, (asp, rostos) in deteccoes.items():
        aspecto = asp
        pequenos += [((nome, q), cx, cy, s) for (q, cx, cy, s) in rostos if s <= ROSTO_GRANDE]
    grupo = _maior_grupo(pequenos)
    quadros = max(1, len(deteccoes) * AMOSTRAS)
    fixa = None
    if len({p[0] for p in grupo}) >= max(4, quadros * 0.12):
        fixa = (float(np.median([p[1] for p in grupo])), float(np.median([p[2] for p in grupo])),
                float(np.median([p[3] for p in grupo])))
        salvas[canal] = list(fixa)
        try:
            ARQ_WEBCAMS.write_text(json.dumps(salvas, indent=1), encoding="utf-8")
        except Exception:
            pass
    elif canal in salvas:
        fixa = tuple(salvas[canal])

    decisoes = {}
    for nome, (asp, rostos) in deteccoes.items():
        grandes = [r for r in rostos if r[3] > ROSTO_GRANDE]
        n_cheia = len({r[0] for r in grandes})
        n_fixa = 0
        if fixa:
            n_fixa = len({r[0] for r in rostos if r[3] <= ROSTO_GRANDE
                          and abs(r[1] - fixa[0]) < 0.06 and abs(r[2] - fixa[1]) < 0.08})
        if n_cheia >= AMOSTRAS * 0.4 and n_cheia > n_fixa:
            decisoes[nome] = ("cheia", round(float(np.median([r[1] for r in grandes])), 4))
        elif fixa and (n_fixa >= 1 or n_cheia == 0):
            # Webcam conhecida para o canal. Se neste corte o rosto quase nao foi detectado (cabeca baixa,
            # mao na frente, pouca luz) mas tambem nao ha rosto grande indicando camera em tela cheia,
            # o mais provavel e que a webcam continue no lugar de sempre: usa a posicao aprendida.
            decisoes[nome] = _caixa(fixa[0], fixa[1], fixa[2], asp)
        else:
            decisoes[nome] = None  # sinais contraditorios: fundo desfocado, que nunca corta nada errado
    return decisoes


# ----------------------------------------------------------------- renderizar

def filtro_video(layout, cam, legenda, zoom=0.75, logo=False, fundo=False):
    if isinstance(cam, tuple) and fundo:
        # pessoa falando com video embaixo: quadrado em volta do rosto em cima, o fundo (segunda entrada) embaixo
        f = (f"[0:v]crop=ih:ih:min(max(iw*{cam[1]}-ih/2\\,0)\\,iw-ih):0,scale=1080:1080,setsar=1[topo];"
             "[1:v]scale=1080:840:force_original_aspect_ratio=increase,crop=1080:840,setsar=1[baixo];"
             "[topo][baixo]vstack=shortest=1,fps=60")  # sem o fps a mistura de duas taxas sai a 120
    elif isinstance(cam, tuple):
        f = f"[0:v]crop=ih*9/16:ih:min(max(iw*{cam[1]}-ih*9/32\\,0)\\,iw-ih*9/16):0,scale=1080:1920"
    elif cam:
        x, y, l, a = cam
        f = (f"[0:v]split[c][g];"
             f"[c]crop=iw*{l}:ih*{a}:iw*{x}:ih*{y},scale=1080:640:force_original_aspect_ratio=increase,"
             f"crop=1080:640[topo];"
             f"[g]crop=ih*1080/1280:ih,scale=1080:1280[jogo];"
             f"[topo][jogo]vstack")
    elif layout == "crop":
        f = "[0:v]crop=ih*9/16:ih,scale=1080:1920"
    else:
        f = ("[0:v]split[a][b];"
             # o fundo e desfocado em resolucao baixa e depois ampliado: mesmo visual, uma fracao do custo
             "[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:3,"
             "scale=1080:1920:flags=bilinear[fundo];"
             f"[b]crop=iw*{zoom}:ih,scale=1080:-2[frente];"
             "[fundo][frente]overlay=(W-w)/2:(H-h)/2")
        if logo:  # a logo e a segunda entrada do ffmpeg; cabe numa caixa de 640x240 no topo, centralizada
            f += ("[semlogo];[1:v]scale=640:240:force_original_aspect_ratio=decrease[logo];"
                  "[semlogo][logo]overlay=(W-w)/2:80+(240-h)/2")
    if legenda:
        f += f",ass={legenda}"
    return f + ",format=yuv420p[v]"


def renderizar(pasta_tmp, bruto, legenda, layout, cam, saida, zoom, ini, dur, logo=None, fundo=None):
    """
    `logo` (arquivo de imagem) so e usada no enquadramento de fundo desfocado, que e o da moldura.
    `fundo` (arquivo, inicio) so e usado na camera cheia: vira a metade de baixo, sem som, repetindo se acabar.
    """
    logo = logo if not cam and layout != "crop" else None
    fundo = fundo if isinstance(cam, tuple) else None
    extra = ["-i", str(logo)] if logo else []
    if fundo:
        extra = ["-stream_loop", "-1", "-ss", f"{fundo[1]:.2f}", "-t", f"{dur:.3f}", "-i", str(fundo[0])]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{ini:.3f}", "-t", f"{dur:.3f}", "-i", bruto.name, *extra,
           "-filter_complex", filtro_video(layout, cam, legenda.name if legenda else None, zoom, logo=bool(logo),
                                           fundo=bool(fundo)),
           "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-maxrate", "8M", "-bufsize", "16M",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(saida)]
    r = subprocess.run(cmd, cwd=pasta_tmp, capture_output=True, text=True, errors="replace")
    return r.returncode == 0 and saida.exists(), (r.stderr or "")[-400:]
