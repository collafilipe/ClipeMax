"""
Pedidos do CEO: um link de live passado a um time para virar cortes.

    link de canal    o time passa a acompanhar o canal (entra no canais.txt e a vigia cuida dele)
    link de video    live antiga ou em andamento: entra na fila de pedidos e e cortada uma vez

A fila fica em estado/pedidos.json. Quem atende e a vigia, se o expediente estiver aberto, ou um
processo avulso (`cortes.py --pedidos`) que a tela inicia quando o expediente esta fechado.

So usa a biblioteca padrao: os testes rodam sem rede e sem yt-dlp.
"""
import datetime
import json
import os
import re
import threading

_TRAVA = threading.Lock()
SITUACOES = ("pendente", "em_andamento", "feito", "erro")

_CANAL = {
    "twitch": "https://www.twitch.tv/{nome}/videos?filter=archives",
    "kick": "https://kick.com/{nome}/videos",
    "youtube": "https://www.youtube.com/@{nome}/streams",
}
# paginas da Twitch que nao sao canais: sem isto "twitch.tv/videos/123" viraria o canal "videos"
_RESERVADOS = {"videos", "directory", "settings", "subscriptions", "downloads", "p", "search", "clip"}


class LinkInvalido(ValueError):
    """O link nao e de um canal nem de uma live da Twitch, da Kick ou do YouTube."""


def entender_link(url):
    """
    -> {"tipo": "canal" | "video", "plataforma", "canal": apelido ou "", "url": link normalizado}
    Para video do YouTube e da Twitch o canal nao esta no link ("canal" vem vazio); quem resolve e o
    yt-dlp, na hora de cortar.
    """
    limpo = (url or "").strip()
    if not re.match(r"https?://", limpo, flags=re.IGNORECASE):
        raise LinkInvalido("o link precisa comecar com http:// ou https://")
    m = re.search(r"twitch\.tv/videos/(\d+)", limpo, flags=re.IGNORECASE)
    if m:
        return {"tipo": "video", "plataforma": "twitch", "canal": "", "url": f"https://www.twitch.tv/videos/{m.group(1)}"}
    m = re.search(r"kick\.com/([^/?#\s]+)/videos/([0-9a-f-]{8,})", limpo, flags=re.IGNORECASE)
    if m:
        return {"tipo": "video", "plataforma": "kick", "canal": m.group(1).lower(),
                "url": f"https://kick.com/{m.group(1)}/videos/{m.group(2)}"}
    m = re.search(r"(?:youtube\.com/(?:watch\?(?:[^#\s]*&)?v=|live/|shorts/)|youtu\.be/)([\w-]{6,})", limpo, flags=re.IGNORECASE)
    if m:
        return {"tipo": "video", "plataforma": "youtube", "canal": "", "url": f"https://www.youtube.com/watch?v={m.group(1)}"}
    m = re.search(r"(twitch\.tv|kick\.com)/([^/?#\s]+)", limpo, flags=re.IGNORECASE)
    if m and m.group(2).lower() not in _RESERVADOS:
        plataforma, nome = m.group(1).split(".")[0].lower(), m.group(2).lower()
        return {"tipo": "canal", "plataforma": plataforma, "canal": nome, "url": _CANAL[plataforma].format(nome=nome)}
    m = re.search(r"youtube\.com/@([^/?#\s]+)", limpo, flags=re.IGNORECASE)
    if m:
        return {"tipo": "canal", "plataforma": "youtube", "canal": m.group(1).lower(), "url": _CANAL["youtube"].format(nome=m.group(1))}
    raise LinkInvalido("nao reconheci este link: use o endereco de um canal ou de uma live da Twitch, da Kick ou do YouTube")


def link_do_canal(plataforma, nome):
    return _CANAL[plataforma].format(nome=nome)


# ------------------------------------------------------------------------ fila

def _arquivo(pasta):
    return pasta / "pedidos.json"


def _ler(pasta):
    try:
        dados = json.loads(_arquivo(pasta).read_text(encoding="utf-8"))
        return dados if isinstance(dados, list) else []
    except (OSError, ValueError):
        return []


def _gravar(pasta, lista):
    # grava ao lado e troca: a tela e a vigia leem este arquivo ao mesmo tempo
    pasta.mkdir(parents=True, exist_ok=True)
    parcial = _arquivo(pasta).with_suffix(".tmp")
    parcial.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(parcial, _arquivo(pasta))


def listar(pasta, quantos=20):
    return _ler(pasta)[-quantos:]


def adicionar(pasta, url, time="", cortes=5, agora=None):
    """
    Poe um video na fila. `time` e a chave do time escolhido pelo CEO ("" = o time do canal do video).
    Devolve o pedido; se o mesmo video ja esta na fila ou sendo cortado, devolve o que ja existe.
    """
    link = entender_link(url)
    if link["tipo"] != "video":
        raise LinkInvalido("este link e de um canal, nao de uma live")
    agora = agora or datetime.datetime.now()
    with _TRAVA:
        lista = _ler(pasta)
        repetido = next((p for p in lista if p["url"] == link["url"] and p["situacao"] in ("pendente", "em_andamento")), None)
        if repetido:
            return repetido
        pedido = {"id": f"{agora:%Y%m%d%H%M%S}-{len(lista)}", "url": link["url"], "plataforma": link["plataforma"],
                  "canal": link["canal"], "time": time or "", "cortes": max(1, min(20, int(cortes or 5))),
                  "situacao": "pendente", "criado_em": agora.isoformat(timespec="seconds"), "detalhe": ""}
        # o historico e so para a tela: ficam os 100 pedidos mais recentes
        _gravar(pasta, [*lista, pedido][-100:])
        return pedido


def reivindicar(pasta, agora=None):
    """O proximo pedido pendente, ja marcado como em andamento (None se nao ha). Quem pega, atende."""
    agora = agora or datetime.datetime.now()
    with _TRAVA:
        lista = _ler(pasta)
        for pedido in lista:
            if pedido["situacao"] == "pendente":
                pedido.update({"situacao": "em_andamento", "iniciado_em": agora.isoformat(timespec="seconds")})
                _gravar(pasta, lista)
                return pedido
    return None


def concluir(pasta, ident, situacao, detalhe="", **extra):
    with _TRAVA:
        lista = _ler(pasta)
        for pedido in lista:
            if pedido["id"] == ident:
                pedido.update({"situacao": situacao, "detalhe": detalhe, **extra})
        _gravar(pasta, lista)


def destravar(pasta):
    """
    Pedidos que ficaram "em andamento" de um processo que morreu voltam para a fila.
    Chamado quando um atendente novo comeca: nesse momento nao ha outro atendendo.
    """
    with _TRAVA:
        lista = _ler(pasta)
        presos = [p for p in lista if p["situacao"] == "em_andamento"]
        for pedido in presos:
            pedido["situacao"] = "pendente"
        if presos:
            _gravar(pasta, lista)
        return len(presos)


def ha_pendentes(pasta):
    return any(p["situacao"] == "pendente" for p in _ler(pasta))
