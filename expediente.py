"""
Expediente: liga e desliga, pelo escritorio, os processos que fazem o trabalho, sem abrir outra janela.

    vigia     `cortes.py --vigiar canais.txt`: acompanha os canais e atende os pedidos do CEO. Fica rodando.
    avulso    `cortes.py --pedidos`: atende a fila de pedidos e sai. A tela usa quando o expediente esta fechado.
              (Nao se chama "pedidos" porque estado/pedidos.json e a propria fila: o arquivo de estado apagaria ela.)

O processo continua rodando se a tela de aprovacao for fechada. Por isso o numero dele fica em
estado/<nome>.json: ao abrir a tela de novo, o escritorio sabe o que esta rodando e consegue fechar.
"""
import datetime
import json
import os
import shlex
import subprocess
import sys

_ARGUMENTOS = {"vigia": lambda carteira: ["--vigiar", carteira], "avulso": lambda carteira: ["--pedidos", "--carteira", carteira]}


def _arquivo(raiz, nome):
    return raiz / "estado" / f"{nome}.json"


def _vivo(pid):
    if os.name == "nt":
        # no Windows os.kill(pid, 0) nao consulta: encerra o processo. A consulta segura e pelo tasklist.
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"], capture_output=True, text=True)
        return f'"{pid}"' in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def situacao(raiz, vivo=_vivo, nome="vigia"):
    """-> {"rodando": bool, "desde": texto ISO ou None, "pid": numero ou None}"""
    try:
        guardado = json.loads(_arquivo(raiz, nome).read_text(encoding="utf-8"))
        pid = int(guardado["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return {"rodando": False, "desde": None, "pid": None}
    if not vivo(pid):
        _arquivo(raiz, nome).unlink(missing_ok=True)  # o processo terminou, caiu ou foi fechado por fora
        return {"rodando": False, "desde": None, "pid": None}
    return {"rodando": True, "desde": guardado.get("desde"), "pid": pid}


def abrir(raiz, opcoes="", carteira="canais.txt", popen=subprocess.Popen, vivo=_vivo, nome="vigia"):
    """Inicia o processo se ele ainda nao estiver rodando. `opcoes` sao opcoes extras do cortes.py (empresa.json)."""
    atual = situacao(raiz, vivo, nome)
    if atual["rodando"]:
        return atual
    estado = raiz / "estado"
    estado.mkdir(exist_ok=True)
    comando = [sys.executable, str(raiz / "cortes.py"), *_ARGUMENTOS[nome](str(raiz / carteira)), *shlex.split(opcoes or "")]
    extras = {}
    if os.name == "nt":
        # grupo proprio e sem janela: fechar o terminal da tela de aprovacao nao leva o processo junto
        extras["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        extras["start_new_session"] = True
    with open(estado / f"{nome}.log", "ab") as saida:
        processo = popen(comando, cwd=str(raiz), stdout=saida, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **extras)
    desde = datetime.datetime.now().isoformat(timespec="seconds")
    _arquivo(raiz, nome).write_text(json.dumps({"pid": processo.pid, "desde": desde}), encoding="utf-8")
    return {"rodando": True, "desde": desde, "pid": processo.pid}


def _encerrar(pid):
    if os.name == "nt":
        # /T leva junto o ffmpeg e o yt-dlp que o processo abriu; sem isso eles ficam orfaos segurando arquivos
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(pid, 15)
        except OSError:
            pass


def fechar(raiz, encerrar=_encerrar, vivo=_vivo, nome="vigia"):
    atual = situacao(raiz, vivo, nome)
    if atual["rodando"]:
        encerrar(atual["pid"])
    _arquivo(raiz, nome).unlink(missing_ok=True)
    return {"rodando": False, "desde": None, "pid": None}
