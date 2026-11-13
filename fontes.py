"""Acesso as plataformas: dados do VOD, playlist HLS, audio, chat e clipes dos espectadores."""
import datetime
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin

import numpy as np

RAIZ = Path(__file__).parent
PY = sys.executable
SR = 4000  # taxa de amostragem usada so para medir volume
TWITCH_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # client-id publico do site da Twitch
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(msg):
    # na vigia cada canal roda num fio chamado "canal:NOME"; o prefixo diz de quem e cada linha
    fio = threading.current_thread().name
    if fio.startswith("canal:"):
        msg = "\n".join(f"[{fio[6:]}] {linha}" if linha else linha for linha in str(msg).split("\n"))
    print(msg, flush=True)


def ytdlp(*args, **kw):
    # --encoding utf-8: sem isso o yt-dlp escreve na codificacao do Windows e acentos/emojis somem
    return subprocess.run([PY, "-m", "yt_dlp", "--no-warnings", "--encoding", "utf-8", *args], **kw)


def hms(s):
    s = int(s)
    return f"{s // 3600}h{(s % 3600) // 60:02d}m{s % 60:02d}s"


def limpar_nome(txt):
    return re.sub(r"[^\w\-]+", "_", txt, flags=re.UNICODE).strip("_")[:40] or "live"


def _baixar(link, tentativas=3):
    for k in range(tentativas):
        try:
            req = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(req, timeout=40).read()
        except Exception:
            time.sleep(1 + k)
    return None


# ---------------------------------------------------------------- informacoes

def info_vod(url):
    campos = "%(uploader,channel)s\t%(id)s\t%(duration)s\t%(timestamp)s\t%(channel_id)s\t%(uploader_id)s\t" \
             "%(live_status)s\t%(categories)j\t%(title)s"
    r = ytdlp("--skip-download", "--print", campos, url,
              capture_output=True, text=True, encoding="utf-8", errors="replace")
    linha = (r.stdout or "").strip().splitlines()
    if r.returncode != 0 or not linha:
        raise RuntimeError(f"Nao consegui ler o video: {(r.stderr or '').strip()[-400:]}")
    canal, vid, dur, inicio, canal_id, login, estado, cats, titulo = (linha[-1].split("\t", 8) + [""] * 9)[:9]
    try:
        categorias = [str(c) for c in (json.loads(cats) or [])]
    except ValueError:
        categorias = []

    def num(v):
        try:
            return float(v)
        except ValueError:
            return 0.0

    def txt(v):
        return "" if v in ("", "NA") else v
    return {"canal": canal or "streamer", "id": vid or "video", "duracao": num(dur), "titulo": titulo,
            "inicio": num(inicio), "canal_id": txt(canal_id), "login": txt(login), "estado": txt(estado),
            "categorias": categorias}


def capitulos_de_jogo(url):
    """
    Trechos da live por jogo: [(inicio, fim, nome_do_jogo)]. So a Twitch informa isso
    (os capitulos do YouTube sao texto livre do criador e a Kick da uma categoria so para a live toda).
    """
    if "twitch.tv" not in url:
        return []
    r = ytdlp("--skip-download", "--print", "%(chapters)j", url,
              capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        caps = json.loads((r.stdout or "").strip().splitlines()[-1]) or []
    except (ValueError, IndexError):
        return []
    return [(float(c.get("start_time") or 0), float(c.get("end_time") or 0), str(c.get("title") or "")) for c in caps]


def ultimos_vods(canal_url, n=3):
    """Os n VODs mais recentes do canal: [(link, estado)], estado como 'is_live', 'was_live', 'is_upcoming' ou ''."""
    r = ytdlp("--flat-playlist", "--playlist-end", str(n), "--print", "%(url)s\t%(live_status)s", canal_url,
              capture_output=True, text=True, encoding="utf-8", errors="replace")
    saida = []
    for l in (r.stdout or "").splitlines():
        link, _, estado = l.partition("\t")
        if link.startswith("http"):
            saida.append((link.split("#__youtubedl_smuggle")[0], "" if estado in ("NA", "None") else estado))
    return saida


def ultimo_vod(canal_url):
    """O VOD mais recente que ja existe (pula lives apenas agendadas)."""
    for link, estado in ultimos_vods(canal_url, 3):
        if estado != "is_upcoming":
            return link
    return None


# ------------------------------------------------- listas HLS (Twitch e Kick)
# Lives ainda no ar tem playlist "ao vivo": o ffmpeg leria em tempo real. Por isso
# montamos uma playlist local, finalizada, so com os segmentos que interessam.

HLS_IN = ["-protocol_whitelist", "file,http,https,tcp,tls,crypto", "-allowed_extensions", "ALL"]


def ler_hls(url, formato):
    """Devolve {'mapa', 'segs': [(inicio, duracao, link)], 'total', 'fim'} ou None se a fonte nao for HLS simples."""
    if "youtube.com" in url or "youtu.be" in url:
        return None
    r = ytdlp("-g", "-f", formato, url, capture_output=True, text=True, encoding="utf-8", errors="replace")
    links = [l for l in (r.stdout or "").splitlines() if l.startswith("http")]
    if len(links) != 1 or ".m3u8" not in links[0]:
        return None
    dados = _baixar(links[0])
    if not dados:
        return None
    txt = dados.decode("utf-8", "replace")
    if "#EXT-X-STREAM-INF" in txt or "#EXT-X-KEY" in txt:
        return None
    mapa, segs, pos, dur = None, [], 0.0, None
    for l in txt.splitlines():
        l = l.strip()
        if l.startswith("#EXT-X-MAP"):
            mapa = re.sub(r'URI="([^"]+)"', lambda m: f'URI="{urljoin(links[0], m.group(1))}"', l)
        elif l.startswith("#EXTINF:"):
            try:
                dur = float(l[8:].split(",")[0])
            except ValueError:
                dur = None
        elif l and not l.startswith("#") and dur is not None:
            segs.append((pos, dur, urljoin(links[0], l)))
            pos += dur
            dur = None
    if not segs:
        return None
    return {"mapa": mapa, "segs": segs, "total": pos, "fim": "#EXT-X-ENDLIST" in txt}


def escrever_hls(destino, mapa, segs):
    alvo = int(max(d for _, d, _ in segs)) + 1
    linhas = ["#EXTM3U", f"#EXT-X-VERSION:{6 if mapa else 3}", f"#EXT-X-TARGETDURATION:{alvo}",
              "#EXT-X-MEDIA-SEQUENCE:0", "#EXT-X-PLAYLIST-TYPE:VOD"]
    if mapa:
        linhas.append(mapa)
    for _, d, link in segs:
        linhas += [f"#EXTINF:{d:.3f},", link]
    linhas.append("#EXT-X-ENDLIST")
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------- audio

_FF_PCM = ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1"]


def _audio_hls(hls, ini, fim):
    """Volume por segundo de [ini, fim), baixando os segmentos em paralelo."""
    segs = [s for s in hls["segs"] if s[0] + s[1] > ini and s[0] < fim]
    n = int(fim - ini)
    somas, cont = np.zeros(n + 2), np.zeros(n + 2)
    inicial = b""
    if hls["mapa"]:
        m = re.search(r'URI="([^"]+)"', hls["mapa"])
        inicial = (_baixar(m.group(1)) if m else None) or b""

    def decodificar(dados, t0):
        """Bytes de um ou mais segmentos -> (segundo inicial, soma dos quadrados, contagem, duracao decodificada)."""
        p = subprocess.run(_FF_PCM, input=inicial + dados, capture_output=True)
        bruto = p.stdout[:len(p.stdout) // 2 * 2]
        if not bruto:
            return None
        x = np.frombuffer(bruto, dtype=np.int16).astype(np.float64)
        idx = np.floor(t0 + np.arange(len(x)) / SR).astype(np.int64) - int(ini)
        ok = (idx >= 0) & (idx < n)
        if not ok.any():
            return None
        dur = len(x) / SR
        idx, x = idx[ok], x[ok]
        b = int(idx[0])
        return b, np.bincount(idx - b, weights=x * x), np.bincount(idx - b), dur

    baixador = ThreadPoolExecutor(max_workers=24)

    def um_grupo(grupo):
        """
        Baixa varios segmentos seguidos em paralelo e decodifica todos numa unica chamada do ffmpeg
        (segmentos de video podem ser simplesmente emendados). Um processo por grupo, em vez de um por
        segmento, e o que deixa a analise de lives longas rapida.
        """
        partes = list(baixador.map(lambda s: _baixar(s[2]), grupo))
        if all(partes):
            r = decodificar(b"".join(partes), grupo[0][0])
            esperado = sum(s[1] for s in grupo)
            if r and abs(r[3] - esperado) < 2.0:
                return [r]
        # algum segmento falhou ou a emenda nao bateu com a duracao: decodifica um por um, cada qual no seu tempo
        return [r for r in (decodificar(p, s[0]) for s, p in zip(grupo, partes) if p) if r]

    grupos = [segs[i:i + 12] for i in range(0, len(segs), 12)]
    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for k, lista in enumerate(pool.map(um_grupo, grupos), 1):
                for b, s, c, _ in lista:
                    somas[b:b + len(s)] += s
                    cont[b:b + len(c)] += c
                if k % 30 == 0:
                    log(f"   audio analisado: {hms(grupos[k - 1][-1][0] + grupos[k - 1][-1][1])}")
    finally:
        baixador.shutdown(wait=False)
    rms = np.sqrt(somas / np.maximum(cont, 1)) + 1.0
    vazio = cont == 0
    if vazio[:n].all():
        return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=bool)
    rms[vazio] = np.median(rms[~vazio])
    return rms[:n].astype(np.float32), ~vazio[:n]


def _audio_pipe(url, limite_s):
    """Fontes sem HLS (YouTube): yt-dlp entrega o audio e o ffmpeg converte, em sequencia."""
    baixa = subprocess.Popen([PY, "-m", "yt_dlp", "-q", "--no-warnings", "-f", "ba/w", "-o", "-", url],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    conv = subprocess.Popen(_FF_PCM, stdin=baixa.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    baixa.stdout.close()
    rms, bloco = [], SR * 2
    try:
        while True:
            buf = conv.stdout.read(bloco)
            if len(buf) < bloco:
                break
            x = np.frombuffer(buf, dtype=np.int16).astype(np.float32)
            rms.append(float(np.sqrt(np.mean(x * x))) + 1.0)
            if len(rms) % 1800 == 0:
                log(f"   audio analisado: {hms(len(rms))}")
            if limite_s and len(rms) >= limite_s:
                break
    finally:
        for p in (conv, baixa):
            try:
                p.kill()
            except Exception:
                pass
    return np.array(rms, dtype=np.float32)


def analisar_audio(url, hls, ini=0, fim=None, com_mascara=False):
    """
    Volume (RMS) de cada segundo entre ini e fim. Sem HLS so funciona a partir do zero.
    Com com_mascara=True devolve tambem quais segundos foram de fato lidos (os outros recebem a mediana).
    """
    if hls:
        fim = int(min(fim or hls["total"], hls["total"]))
        rms, ok = _audio_hls(hls, int(ini), fim)
    else:
        rms = _audio_pipe(url, int(fim or 0))
        ok = np.ones(len(rms), dtype=bool)
    return (rms, ok) if com_mascara else rms


# ----------------------------------------------------------------------- chat

def _amostrar(funcao, instantes, t0, t1, nome, paralelas=8):
    """Roda funcao(t) -> (instante, mensagens_por_segundo) em paralelo e interpola para cada segundo."""
    if not instantes:
        return None
    # sonda: se uma unica consulta ja falha (VOD so para inscritos, API mudou), desiste na hora
    if funcao(instantes[len(instantes) // 2]) is None:
        return None
    pontos, falhas = [], 0
    with ThreadPoolExecutor(max_workers=paralelas) as pool:
        for k, r in enumerate(pool.map(funcao, instantes), 1):
            if r is None:
                falhas += 1
            else:
                pontos.append(r)
            if k % 800 == 0:
                log(f"   chat {nome}: {k}/{len(instantes)} amostras")
    if len(pontos) < 2 or falhas > len(instantes) * 0.3:
        return None
    pontos.sort()
    return np.interp(np.arange(t0, t1), [p[0] for p in pontos], [p[1] for p in pontos]).astype(np.float32)


def _twitch_gql(corpo):
    req = urllib.request.Request("https://gql.twitch.tv/gql", data=json.dumps(corpo).encode(), headers={
        "Client-ID": TWITCH_ID, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def chat_twitch(video_id, t0, t1, passo=20):  # 20 s: num chat movimentado uma pagina cobre ~17 s, quase sem buracos
    """
    Ritmo do chat de um VOD da Twitch: uma pagina de comentarios a cada `passo` segundos.
    A API aceita varias consultas no mesmo pedido, entao as amostras vao em lotes de 15.
    """
    def consulta(t):
        return {"operationName": "VideoCommentsByOffsetOrCursor",
                "variables": {"videoID": video_id, "contentOffsetSeconds": int(t)},
                "extensions": {"persistedQuery": {
                    "version": 1, "sha256Hash": "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"}}}

    def lote(instantes):
        for tentativa in range(3):
            try:
                respostas = _twitch_gql([consulta(t) for t in instantes])
                pontos = []
                for t, r in zip(instantes, respostas):
                    offs = [e["node"]["contentOffsetSeconds"] for e in r["data"]["video"]["comments"]["edges"]]
                    if not offs:
                        pontos.append((float(t), 0.0))
                    elif len(offs) < 5 or offs[-1] - offs[0] < 1:
                        # pagina quase vazia (chat parado, fim do VOD): nao da para medir pelo intervalo
                        pontos.append((float(t), len(offs) / passo))
                    else:
                        pontos.append(((offs[0] + offs[-1]) / 2, len(offs) / (offs[-1] - offs[0])))
                return pontos
            except Exception:
                time.sleep(1 + tentativa)
        return None

    instantes = list(range(int(t0), int(t1), passo))
    lotes = [instantes[i:i + 15] for i in range(0, len(instantes), 15)]
    # sonda: se um unico lote ja falha (VOD so para inscritos, API mudou), desiste na hora
    if not lotes or lote(lotes[len(lotes) // 2]) is None:
        return None
    pontos, falhas = [], 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for r in pool.map(lote, lotes):
            if r is None:
                falhas += 1
            else:
                pontos += r
    if len(pontos) < 2 or falhas > len(lotes) * 0.3:
        return None
    pontos.sort()
    return np.interp(np.arange(t0, t1), [p[0] for p in pontos], [p[1] for p in pontos]).astype(np.float32)


_local = threading.local()


def _kick_json(link):
    """A Kick fica atras de protecao; a rede do yt-dlp passa por ela."""
    import yt_dlp
    if not hasattr(_local, "ydl"):
        _local.ydl = yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True})
    req = yt_dlp.networking.Request(link, headers={"Accept": "application/json"})
    return json.loads(_local.ydl.urlopen(req).read())


def chat_kick(canal_id, inicio_ts, t0, t1, passo=20):
    """Ritmo do chat de um VOD da Kick: cada consulta devolve ~5 segundos de mensagens."""
    def uma(t):
        quando = datetime.datetime.fromtimestamp(inicio_ts + t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        link = f"https://kick.com/api/v2/channels/{canal_id}/messages?start_time={quando}"
        for tentativa in range(3):
            try:
                return (t + 2.5, len(_kick_json(link)["data"]["messages"]) / 5.0)
            except Exception:
                time.sleep(1 + tentativa)
        return None
    return _amostrar(uma, list(range(int(t0), int(t1), passo)), t0, t1, "Kick", paralelas=12)


def _chat_ytdlp(url, pasta, timeout):
    """Replay do chat pelo yt-dlp (YouTube). Devolve o segundo de cada mensagem."""
    try:
        ytdlp("-q", "--skip-download", "--write-subs", "--sub-langs", "rechat,live_chat",
              "-o", str(pasta / "chat"), url, timeout=timeout,
              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        log("   chat demorou demais, sigo sem ele")
    tempos = []
    for f in pasta.glob("chat*"):
        if f.suffix not in (".json", ".part"):
            continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        tempos += [int(float(m)) for m in re.findall(r'"contentOffsetSeconds":\s*([\d.]+)', t)]
        tempos += [int(m) // 1000 for m in re.findall(r'"videoOffsetTimeMsec":\s*"?(\d+)', t)]
    return tempos


def obter_chat(url, info, t0, t1, pasta, timeout=900):
    """Ritmo do chat (mensagens por segundo) para cada segundo de [t0, t1), ou None."""
    try:
        if "twitch.tv" in url:
            return chat_twitch(info["id"].lstrip("v"), t0, t1)
        if "kick.com" in url and info.get("canal_id") and info.get("inicio"):
            return chat_kick(info["canal_id"], info["inicio"], t0, t1)
    except Exception as e:
        log(f"   chat falhou ({e})")
        return None
    tempos = _chat_ytdlp(url, pasta, timeout)
    if not tempos:
        return None
    return np.bincount([t - t0 for t in tempos if t0 <= t < t1], minlength=int(t1 - t0)).astype(np.float32)


# ------------------------------------------------- clipes feitos pela audiencia

def clipes_twitch(login, video_id):
    q = ('query { user(login: "%s") { clips(first: 100, criteria: {period: LAST_WEEK, sort: VIEWS_DESC}) '
         '{ edges { node { title viewCount durationSeconds videoOffsetSeconds video { id } } } } } }'
         % re.sub(r"[^\w]", "", login))
    r = _twitch_gql({"query": q})
    saida = []
    for e in (((r.get("data") or {}).get("user") or {}).get("clips") or {}).get("edges") or []:
        n = e["node"]
        if (n.get("video") or {}).get("id") == video_id and n.get("videoOffsetSeconds") is not None:
            saida.append((int(n["videoOffsetSeconds"]), int(n["durationSeconds"]), int(n["viewCount"]), n["title"]))
    return saida


def clipes_kick(slug, inicio_ts, total):
    r = _kick_json(f"https://kick.com/api/v2/channels/{slug}/clips?sort=view&time=week")
    saida = []
    for c in r.get("clips") or []:
        try:
            criado = datetime.datetime.fromisoformat(c["created_at"].replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        dur = int(c.get("duration") or 30)
        # A Kick nao informa em que ponto da live o clipe foi tirado, so quando ele foi publicado. O clipe
        # pega os segundos anteriores ao clique, e o espectador ainda leva de segundos a alguns minutos
        # para recortar e publicar. Por isso a posicao e uma faixa larga (de 15 s a ~1,5 min de atraso),
        # nao um ponto: o bonus cobre a faixa inteira em vez de apostar num instante exato.
        pos = int(criado - inicio_ts - dur - 90)
        if -60 <= pos < total:
            saida.append((max(0, pos), dur + 75, int(c.get("views") or c.get("view_count") or 0), c.get("title") or ""))
    return saida


def obter_clipes(url, info, total):
    """Clipes que os espectadores criaram desta live: [(segundo, duracao, views, titulo)]."""
    try:
        if "twitch.tv" in url and info.get("login"):
            return clipes_twitch(info["login"], info["id"].lstrip("v"))
        if "kick.com" in url and info.get("login") and info.get("inicio"):
            return clipes_kick(info["login"], info["inicio"], total)
    except Exception as e:
        log(f"   clipes dos espectadores indisponiveis ({str(e)[:80]})")
    return []
