"""
Narracao: transforma o texto que o dono do canal escreveu em fala, para entrar no video.

Corte so com texto na tela e lido pelas plataformas como edicao leve; comentario falado pesa mais contra a
regra de conteudo reutilizado. A voz e sintetica, mas o texto e sempre do dono do canal: contexto escrito pela
IA nao e narrado, porque roteiro e voz automaticos em todo video e justamente o que a regra pune.

Dois motores, nesta ordem:
  1. ElevenLabs, voz Brian: a mesma do narrador das series de historias do dono do canal, que ele aprovou
     (as vozes do Edge foram reprovadas la por "cara de IA"). Precisa da chave dele; o plano gratuito da
     10.000 caracteres por mes, entao cada frase fica guardada em estado/cache_voz e nunca e paga duas vezes.
  2. edge-tts (Microsoft, gratuito): reserva para quando nao ha chave, acabou a cota ou a rede falhou.
Sem nenhum dos dois, devolve False e o video sai sem fala; narracao nunca derruba o render.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
VOZ = "pt-BR-AntonioNeural"  # reserva (edge-tts)
# Brian, com os ajustes do narrador aprovado nas series (estudio/vozes_elevenlabs.json)
ELEVEN = {"voice_id": "nPczCjzI2devNBz1zQrb", "nome": "Brian", "model_id": "eleven_multilingual_v2",
          "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True}}
# a chave pode ficar no proprio ClipeMax (segredos/ nao vai para o git) ou onde o estudio das series ja guarda
CHAVES = (RAIZ / "segredos" / "elevenlabs_key.txt",
          Path.home() / "Documents" / "MoneyPrinterTurbo" / "estudio" / "elevenlabs_key.txt")
CACHE = RAIZ / "estado" / "cache_voz"
ULTIMO = ""  # motor que gravou a ultima fala: "eleven", "eleven (cache)", "edge" ou ""


def _chave(arquivos=None):
    for arq in CHAVES if arquivos is None else arquivos:
        try:
            chave = arq.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if chave:
            return chave
    return None


def _eleven(texto, destino, chave, abrir=urllib.request.urlopen):
    """Uma fala pelo ElevenLabs. True se o arquivo saiu; qualquer falha (cota, rede, chave) devolve False."""
    corpo = json.dumps({"text": texto, "model_id": ELEVEN["model_id"], "voice_settings": ELEVEN["voice_settings"]})
    pedido = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN['voice_id']}?output_format=mp3_44100_128",
        data=corpo.encode("utf-8"), headers={"xi-api-key": chave, "Content-Type": "application/json"})
    try:
        with abrir(pedido, timeout=90) as resp:
            audio = resp.read()
    except (urllib.error.URLError, OSError, ValueError):
        return False
    if len(audio) < 1000:
        return False
    Path(destino).write_bytes(audio)
    return True


def saldo(abrir=urllib.request.urlopen):
    """(usados, limite) de caracteres do mes no ElevenLabs, ou None sem chave ou sem resposta."""
    chave = _chave()
    if not chave:
        return None
    try:
        pedido = urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": chave})
        with abrir(pedido, timeout=30) as resp:
            dados = json.loads(resp.read())
        return int(dados["character_count"]), int(dados["character_limit"])
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
        return None


def falar(texto, destino, voz=VOZ, rodar=subprocess.run, chave=None, eleven=_eleven, cache=None):
    """Grava `texto` falado em `destino` (mp3). Devolve True se o arquivo saiu; o motor usado fica em ULTIMO."""
    global ULTIMO
    destino, texto, ULTIMO = Path(destino), " ".join(str(texto).split()), ""
    if not texto:
        return False
    chave = _chave() if chave is None else chave
    if chave:
        cache = CACHE if cache is None else cache
        marca = hashlib.sha1(f"{ELEVEN['voice_id']}|{json.dumps(ELEVEN['voice_settings'], sort_keys=True)}|{texto}".encode()).hexdigest()
        guardado = cache / f"{marca}.mp3"
        try:
            if guardado.exists() and guardado.stat().st_size > 1000:
                shutil.copyfile(guardado, destino)
                ULTIMO = "eleven (cache)"
                return True
            if eleven(texto, destino, chave):
                cache.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(destino, guardado)
                ULTIMO = "eleven"
                return True
        except OSError:
            pass
    try:
        # --text=... numa palavra so: comentario comecando com hifen nao pode virar opcao do comando
        r = rodar([sys.executable, "-m", "edge_tts", "--voice", voz, f"--text={texto}", "--write-media", str(destino)],
                  capture_output=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return False
    ok = r.returncode == 0 and destino.exists() and destino.stat().st_size > 1000
    if not ok:
        destino.unlink(missing_ok=True)
        return False
    ULTIMO = "edge"
    return True
