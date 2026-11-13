"""
Detecta musica no audio de um corte com o YAMNet (modelo de classificacao de sons do Google,
versao ONNX publicada pela Qualcomm, licenca MIT; arquivos em modelos/).

Serve para avisar do risco de direitos autorais: o YouTube bloqueia Shorts de mais de 1 minuto que tenham
musica reivindicada, e o TikTok pode silenciar o video. O modelo diz se ha musica, nao se ela e protegida:
trilha do proprio jogo tambem conta. E um aviso para a revisao, nao um veredito.
"""
import subprocess

import numpy as np

from fontes import RAIZ

SR = 16000
MODELO = RAIZ / "modelos" / "yamnet.onnx"
CLASSE_MUSICA, CLASSE_FALA, CLASSE_CANTO = 132, 0, 24  # indices da lista oficial de classes do YAMNet
LIMIAR = 0.10  # probabilidade acima da qual ~1 s conta como "com musica" (inclui musica de fundo sob a fala)
LIMIAR_FORTE = 0.50  # musica em destaque, claramente audivel: e a que mais interessa para direitos autorais

_sessao = None
_mel = None


def disponivel():
    return MODELO.exists() and (MODELO.parent / "yamnet.data").exists()


def _matriz_mel():
    """64 faixas mel entre 125 e 7500 Hz sobre uma FFT de 512 pontos, como no YAMNet original."""
    def mel(f):
        return 1127.0 * np.log1p(np.asarray(f, dtype=np.float64) / 700.0)
    freq = mel(np.linspace(0, SR / 2, 257))
    bordas = np.linspace(mel(125.0), mel(7500.0), 66)
    m = np.zeros((257, 64))
    for i in range(64):
        baixo, centro, alto = bordas[i:i + 3]
        m[:, i] = np.maximum(0.0, np.minimum((freq - baixo) / (centro - baixo), (alto - freq) / (alto - centro)))
    m[0, :] = 0.0
    return m


def _log_mel(onda):
    """Espectrograma log-mel com janela de 25 ms e passo de 10 ms."""
    global _mel
    if _mel is None:
        _mel = _matriz_mel()
    n = 1 + (len(onda) - 400) // 160
    idx = np.arange(400)[None, :] + 160 * np.arange(n)[:, None]
    janela = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(400) / 400)
    espectro = np.abs(np.fft.rfft(onda[idx] * janela, n=512, axis=1))
    return np.log(espectro @ _mel + 0.001).astype(np.float32)


def analisar(arquivo, ini=0.0, fim=None):
    """
    Devolve {"musica_pct", "musica_forte_s", "nivel", "trechos"} do pedaco [ini, fim) do arquivo, ou None.
    musica_pct: porcentagem do tempo com alguma musica (inclui fundo); musica_forte_s: segundos de musica em
    destaque; nivel: "nenhuma", "fundo" ou "destaque"; trechos: [(inicio, fim)] em segundos a partir de ini.
    """
    global _sessao
    if not disponivel():
        return None
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{ini:.2f}"]
    if fim is not None:
        cmd += ["-t", f"{fim - ini:.2f}"]
    cmd += ["-i", str(arquivo), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1"]
    bruto = subprocess.run(cmd, capture_output=True).stdout
    onda = np.frombuffer(bruto[:len(bruto) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
    if len(onda) < SR * 2:
        return None
    try:
        if _sessao is None:
            import onnxruntime as ort
            opcoes = ort.SessionOptions()
            opcoes.log_severity_level = 3
            _sessao = ort.InferenceSession(str(MODELO), sess_options=opcoes, providers=["CPUExecutionProvider"])
        mel = _log_mel(onda)
        notas = []
        for a in range(0, len(mel) - 96 + 1, 48):  # janelas de 0,96 s a cada 0,48 s
            saida = _sessao.run(None, {"audio": mel[a:a + 96][None, None, :, :]})[0][0]
            # o modelo devolve notas brutas (logits); a sigmoide transforma em probabilidade de 0 a 1
            p = 1.0 / (1.0 + np.exp(-saida[[CLASSE_MUSICA, CLASSE_CANTO]].astype(np.float64)))
            notas.append(float(p.max()))
    except Exception:
        return None
    if not notas:
        return None
    notas = np.array(notas)
    tem = notas >= LIMIAR
    # junta janelas vizinhas em trechos e ignora os de menos de ~1,5 s (um efeito sonoro, um toque)
    trechos, comeco = [], None
    for k, v in enumerate(list(tem) + [False]):
        if v and comeco is None:
            comeco = k
        elif not v and comeco is not None:
            if k - comeco >= 3:
                trechos.append((round(comeco * 0.48, 1), round(k * 0.48 + 0.48, 1)))
            comeco = None
    total = len(tem) * 0.48 + 0.48
    com_musica = sum(b - a for a, b in trechos)
    forte = round(float((notas >= LIMIAR_FORTE).sum()) * 0.48, 1)
    pct = round(100.0 * min(1.0, com_musica / total))
    nivel = "destaque" if (forte >= 5 or pct >= 50) else ("fundo" if pct >= 10 else "nenhuma")
    return {"musica_pct": pct, "musica_forte_s": forte, "nivel": nivel, "trechos": trechos}
