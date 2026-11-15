"""
Montagem: varios cortes num video so, com uma ideia que e do canal (ranking ou comparacao entre streamers).

Corte solto e o trecho de outra pessoa com legenda; a montagem e um video que nao existe em nenhuma live:
a escolha, a ordem, o titulo e a conducao sao do dono do canal. E a transformacao que as plataformas aceitam
com mais facilidade sem o dono precisar aparecer ou gravar a voz.

Cada corte entra inteiro, com uma cartela antes (numero ou nome do streamer, sobre o proprio corte desfocado)
e um selo pequeno no canto durante o trecho. A cartela e narrada com o titulo que o dono escreveu.
"""
import datetime
import json
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path

import video
import voz

TIPOS = ("ranking", "comparacao")
MINIMO, MAXIMO = 2, 8
LIMITE_SHORTS = 180  # segundos; acima disso o YouTube nao trata o video como Short
_OURO = "&H005AAFD4"  # #d4af5a na ordem do ASS (azul, verde, vermelho)
_SAIDA = ["-r", "60", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-maxrate", "8M", "-bufsize", "16M",
          "-pix_fmt", "yuv420p", "-video_track_timescale", "15360",
          "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-f", "mp4"]
_FMT = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding")


def ordenar(itens, tipo):
    """
    Ordem em que os cortes aparecem. Ranking e contagem regressiva: o de menor nota abre e o melhor fecha,
    que e o que segura o espectador ate o fim. Comparacao mantem a ordem em que o dono escolheu.
    """
    if tipo != "ranking":
        return list(itens)
    return sorted(itens, key=lambda i: (i.get("nota") if i.get("nota") is not None else -1))


def posicoes(itens, tipo):
    """Numero mostrado em cada corte, na ordem de exibicao: N..1 no ranking, 1..N na comparacao."""
    n = len(itens)
    return [n - k if tipo == "ranking" else k + 1 for k in range(n)]


def fala_da_cartela(tipo, k, total, canal, titulo):
    """O que a narracao diz na cartela do corte `k` (0 = primeiro a aparecer)."""
    abre = f"{titulo.rstrip('.!?')}. " if k == 0 and titulo else ""
    if tipo == "ranking":
        numero = total - k
        return abre + (f"E em primeiro lugar: {canal}." if numero == 1 and total > 1 else f"Número {numero}: {canal}.")
    return abre + (f"{canal}." if k == 0 else f"Agora, {canal}.")


def _slug(texto):
    sem = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem.lower()).strip("-")[:50] or "montagem"


def _ass(estilos, falas):
    return "\n".join(["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 0", "",
                      "[V4+ Styles]", _FMT, *estilos, "", "[Events]",
                      "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text", *falas])


def ass_da_cartela(titulo, grande, nome, dur):
    """Cartela: titulo da montagem em cima, o numero (ou a posicao) enorme no meio e o streamer embaixo."""
    fim = video.t_ass(dur)
    falas = [f"Dialogue: 1,0:00:00.00,{fim},Num,,0,0,0,,{{\\fad(120,0)}}{video._limpo(grande)}",
             f"Dialogue: 1,0:00:00.00,{fim},Nome,,0,0,0,,{{\\fad(120,0)}}{video._limpo(nome).upper()}"]
    if titulo:
        falas.append(f"Dialogue: 1,0:00:00.00,{fim},Tit,,0,0,0,,{video._limpo(titulo).upper()}")
    return _ass([
        f"Style: Num,Impact,330,{_OURO},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,10,4,5,60,60,0,1",
        "Style: Nome,Impact,104,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,7,3,2,70,70,560,1",
        "Style: Tit,Arial,58,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,8,90,90,330,1",
    ], falas)


def ass_do_selo(texto, dur):
    """Selo pequeno no canto de cima a direita durante o corte: o espectador que chegou no meio sabe onde esta."""
    return _ass(
        [f"Style: Selo,Impact,62,&H00101010,&H000000FF,{_OURO},&H00000000,-1,0,0,0,100,100,0,0,3,10,0,9,40,40,40,1"],
        [f"Dialogue: 4,0:00:00.00,{video.t_ass(dur)},Selo,,0,0,0,,{video._limpo(texto)}"])


def _ffmpeg(args, pasta):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], cwd=pasta, capture_output=True, text=True,
                       errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode == 0, (r.stderr or "")[-300:]


def _cartela(pasta, n, origem, ass, fala, dur):
    """Cartela de `dur` segundos sobre um quadro desfocado do proprio corte, com a narracao (ou silencio)."""
    quadro, saida = f"q{n}.jpg", f"c{n}.mp4"
    ok, erro = _ffmpeg(["-ss", "1", "-i", str(origem), "-frames:v", "1", "-vf", "scale=1080:1920", "-q:v", "4", quadro], pasta)
    if not ok:
        return None, erro
    (Path(pasta) / f"c{n}.ass").write_text(ass, encoding="utf-8")
    som = ["-i", str(fala)] if fala else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    ok, erro = _ffmpeg(["-loop", "1", "-framerate", "60", "-i", quadro, *som, "-filter_complex",
                        f"[0:v]boxblur=26:2,eq=brightness=-0.3:saturation=0.7,ass=c{n}.ass,setsar=1[v];"
                        f"[1:a]aresample=48000,adelay=150:all=1,volume=1.5,apad[a]",
                        "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}", *_SAIDA, saida], pasta)
    return (saida if ok else None), erro


def _trecho(pasta, n, origem, ass):
    """O corte inteiro, com o selo da montagem, no mesmo formato das cartelas (para emendar sem recodificar)."""
    saida = f"t{n}.mp4"
    (Path(pasta) / f"t{n}.ass").write_text(ass, encoding="utf-8")
    ok, erro = _ffmpeg(["-i", str(origem), "-vf", f"scale=1080:1920,setsar=1,ass=t{n}.ass", *_SAIDA, saida], pasta)
    return (saida if ok else None), erro


def montar(itens, titulo, tipo, destino, narrar=True, falar=voz.falar):
    """
    itens: [{"video": caminho, "canal": nome, "nota": numero ou None}, ...] na ordem escolhida pelo dono.
    Grava `destino` (mp4) so se tudo der certo. Devolve (ok, erro, info), info com duracao, ordem e narracao.
    """
    titulo, destino = " ".join(str(titulo).split())[:80], Path(destino)
    if tipo not in TIPOS:
        return False, "tipo de montagem desconhecido", {}
    if not MINIMO <= len(itens) <= MAXIMO:
        return False, f"a montagem leva de {MINIMO} a {MAXIMO} cortes", {}
    itens = ordenar(itens, tipo)
    numeros, total, pecas, narrados = posicoes(itens, tipo), len(itens), [], 0
    with tempfile.TemporaryDirectory(prefix="cortes_montagem_") as pasta:
        for k, item in enumerate(itens):
            origem, canal = Path(item["video"]).resolve(), str(item.get("canal") or "")
            dur = video.duracao_de(origem)
            if not dur:
                return False, f"nao consegui ler {origem.name}", {}
            fala = Path(pasta) / f"f{k}.mp3"
            tem_fala = bool(narrar) and falar(fala_da_cartela(tipo, k, total, canal, titulo), fala)
            narrados += tem_fala
            tempo = max(1.4, video.duracao_de(fala) + 0.45) if tem_fala else (2.2 if k == 0 and titulo else 1.4)
            grande = f"#{numeros[k]}" if tipo == "ranking" else f"{numeros[k]}/{total}"
            cartela, erro = _cartela(pasta, k, origem, ass_da_cartela(titulo if k == 0 else "", grande, canal, tempo),
                                     fala if tem_fala else None, tempo)
            if not cartela:
                return False, erro.strip()[-200:] or "falha na cartela", {}
            trecho, erro = _trecho(pasta, k, origem, ass_do_selo(grande, dur))
            if not trecho:
                return False, erro.strip()[-200:] or "falha ao preparar um corte", {}
            pecas += [cartela, trecho]
        (Path(pasta) / "lista.txt").write_text("".join(f"file '{p}'\n" for p in pecas), encoding="utf-8")
        destino.parent.mkdir(parents=True, exist_ok=True)
        novo = destino.with_suffix(".novo")
        ok, erro = _ffmpeg(["-f", "concat", "-safe", "0", "-i", "lista.txt", "-c", "copy", "-movflags", "+faststart",
                            "-f", "mp4", str(novo.resolve())], pasta)
    if not ok or not novo.exists() or novo.stat().st_size < 10000:
        novo.unlink(missing_ok=True)
        return False, erro.strip()[-200:] or "falha ao emendar", {}
    novo.replace(destino)
    return True, "", {"duracao": round(video.duracao_de(destino), 1), "narrado": narrados == total,
                      "ordem": [str(i.get("canal") or "") for i in itens]}


def criar(cortes, titulo, tipo, pasta_prontos, narrar=True, agora=None, montar_video=None):
    """
    Monta o video e deixa-o na mesa do CEO como um corte comum (pasta Montagens, etapa "ceo": a esteira
    nao reavalia o que o proprio dono montou). `cortes`: [{"video": Path, "dados": dict do .json}, ...].
    Devolve (ok, erro, dados gravados).
    """
    agora = agora or datetime.datetime.now()
    itens = []
    for c in cortes:
        d, mp4 = c["dados"], Path(c["video"])
        base = mp4.with_suffix(".base")  # sem a caixa de comentario do corte solto, que brigaria com o selo
        itens.append({"video": base if base.exists() else mp4, "canal": d.get("canal") or mp4.parent.name.rsplit("_", 1)[0],
                      "nota": d.get("nota_gestor") if d.get("nota_gestor") is not None else d.get("nota_ia"),
                      "titulo": d.get("titulo", ""), "origem": d.get("origem", ""), "jogo": d.get("jogo", "")})
    titulo = " ".join(str(titulo).split())[:80]
    if not titulo:
        return False, "de um titulo para a montagem: ele aparece na abertura e e narrado", {}
    destino = Path(pasta_prontos) / "Montagens" / f"{agora:%Y%m%d_%H%M%S}_{_slug(titulo)}.mp4"
    ok, erro, info = (montar_video or montar)(itens, titulo, tipo, destino, narrar=narrar)
    if not ok:
        return False, erro, {}
    usados = ordenar(itens, tipo)
    canais = list(dict.fromkeys(i["canal"] for i in usados))
    marcas = " ".join("#" + re.sub(r"\W", "", c.lower()) for c in canais)
    jogos = list(dict.fromkeys(i["jogo"] for i in usados if i["jogo"] and i["jogo"] != "nenhum"))
    dados = {
        "canal": "Montagem", "montagem": True, "tipo": tipo, "titulo": titulo, "duracao": info["duracao"],
        "narrado": info["narrado"], "etapa": "ceo", "jogo": jogos[0] if len(jogos) == 1 else "",
        "motivo": ("Ranking" if tipo == "ranking" else "Comparação") + f" com {len(usados)} cortes: " + ", ".join(info["ordem"]) + ".",
        "tiktok": f"{titulo} {marcas} #cortes #fyp", "shorts": f"{titulo} {marcas} #shorts",
        "partes": [{"canal": i["canal"], "titulo": i["titulo"], "origem": i["origem"]} for i in usados],
        "trilha": [{"etapa": "ceo", "quem": "Você", "veredito": "entregue", "melhoria": "",
                    "parecer": "Montagem criada por você na tela de aprovação.", "quando": agora.isoformat(timespec="seconds")}],
    }
    destino.with_suffix(".json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return True, "", dados
