"""Links que o CEO passa pelo escritorio: entender o link, a fila de pedidos e os times so por pedido."""
import datetime

import pytest

import agencia
import pedidos

AGORA = datetime.datetime(2026, 11, 13, 16, 0)


# ------------------------------------------------------------- entender o link

@pytest.mark.parametrize("url, esperado", [
    ("https://www.twitch.tv/videos/2926903009?t=1h", ("video", "twitch", "", "https://www.twitch.tv/videos/2926903009")),
    ("https://kick.com/Coringa/videos/01a1d378-c208-7a30-8182-d89dded660ea",
     ("video", "kick", "coringa", "https://kick.com/Coringa/videos/01a1d378-c208-7a30-8182-d89dded660ea")),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10", ("video", "youtube", "", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")),
    ("https://youtu.be/dQw4w9WgXcQ", ("video", "youtube", "", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")),
    ("https://www.youtube.com/live/dQw4w9WgXcQ", ("video", "youtube", "", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")),
    ("https://www.twitch.tv/Alanzoka", ("canal", "twitch", "alanzoka", "https://www.twitch.tv/alanzoka/videos?filter=archives")),
    ("https://kick.com/xqc/videos", ("canal", "kick", "xqc", "https://kick.com/xqc/videos")),
    ("https://www.youtube.com/@IShowSpeed/streams", ("canal", "youtube", "ishowspeed", "https://www.youtube.com/@IShowSpeed/streams")),
])
def test_link_de_canal_e_de_live_sao_reconhecidos_e_normalizados(url, esperado):
    link = pedidos.entender_link(url)
    assert (link["tipo"], link["plataforma"], link["canal"], link["url"]) == esperado


@pytest.mark.parametrize("url", ["", "coringa", "ftp://kick.com/coringa", "https://exemplo.com/video/1", "https://www.twitch.tv/directory"])
def test_link_que_nao_e_canal_nem_live_e_recusado_com_explicacao(url):
    with pytest.raises(pedidos.LinkInvalido):
        pedidos.entender_link(url)


# ------------------------------------------------------------------------ fila

def test_pedido_entra_na_fila_e_e_atendido_uma_vez_so(tmp_path):
    pedido = pedidos.adicionar(tmp_path, "https://www.twitch.tv/videos/123456", "twitch:alanzoka", 3, AGORA)
    assert (pedido["situacao"], pedido["time"], pedido["cortes"]) == ("pendente", "twitch:alanzoka", 3)
    assert pedidos.ha_pendentes(tmp_path)
    pego = pedidos.reivindicar(tmp_path)
    assert pego["id"] == pedido["id"] and pego["situacao"] == "em_andamento"
    assert pedidos.reivindicar(tmp_path) is None and not pedidos.ha_pendentes(tmp_path)
    pedidos.concluir(tmp_path, pedido["id"], "feito", "3 corte(s) para a esteira", time="twitch:alanzoka")
    assert [(p["situacao"], p["detalhe"]) for p in pedidos.listar(tmp_path)] == [("feito", "3 corte(s) para a esteira")]


def test_mesma_live_duas_vezes_nao_vira_dois_pedidos_enquanto_o_primeiro_nao_termina(tmp_path):
    primeiro = pedidos.adicionar(tmp_path, "https://www.twitch.tv/videos/123456?t=5m", agora=AGORA)
    segundo = pedidos.adicionar(tmp_path, "https://www.twitch.tv/videos/123456", agora=AGORA)
    assert segundo["id"] == primeiro["id"] and len(pedidos.listar(tmp_path)) == 1
    pedidos.concluir(tmp_path, primeiro["id"], "feito")
    # depois de pronto, pedir de novo e um pedido novo (a producao pula os momentos que ja viraram corte)
    assert pedidos.adicionar(tmp_path, "https://www.twitch.tv/videos/123456", agora=AGORA)["id"] != primeiro["id"]


def test_link_de_canal_nao_entra_na_fila_de_cortes(tmp_path):
    with pytest.raises(pedidos.LinkInvalido, match="canal"):
        pedidos.adicionar(tmp_path, "https://kick.com/coringa")


def test_pedido_de_atendente_que_morreu_volta_para_a_fila(tmp_path):
    pedidos.adicionar(tmp_path, "https://www.twitch.tv/videos/1", agora=AGORA)
    pedidos.reivindicar(tmp_path)
    assert pedidos.destravar(tmp_path) == 1
    assert pedidos.reivindicar(tmp_path)["situacao"] == "em_andamento"


def test_quantidade_de_cortes_fica_entre_1_e_20(tmp_path):
    assert pedidos.adicionar(tmp_path, "https://www.twitch.tv/videos/1", cortes=0, agora=AGORA)["cortes"] == 5
    assert pedidos.adicionar(tmp_path, "https://www.twitch.tv/videos/2", cortes=99, agora=AGORA)["cortes"] == 20


def test_arquivo_de_fila_estragado_vale_como_fila_vazia(tmp_path):
    (tmp_path / "pedidos.json").write_text("{quebrado", encoding="utf-8")
    assert pedidos.listar(tmp_path) == [] and pedidos.reivindicar(tmp_path) is None


# ------------------------------------------------------------- times na carteira

def test_canal_passado_pelo_escritorio_entra_no_fim_do_arquivo_sem_mexer_no_resto(tmp_path):
    arquivo = tmp_path / "canais.txt"
    arquivo.write_text("# meus canais\nhttps://kick.com/coringa/videos | cliente=Coringa\n", encoding="utf-8")
    canal = agencia.adicionar_canal(arquivo, "https://www.twitch.tv/alanzoka/videos?filter=archives", cliente="Alan", vigiar=False)
    assert (canal.chave, canal.cliente, canal.vigiar) == ("twitch:alanzoka", "Alan", False)
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    assert linhas[:2] == ["# meus canais", "https://kick.com/coringa/videos | cliente=Coringa"]
    assert linhas[2] == "https://www.twitch.tv/alanzoka/videos?filter=archives | cliente=Alan | vigiar=nao"
    assert [c.chave for c in agencia.ler_carteira(arquivo)] == ["kick:coringa", "twitch:alanzoka"]


def test_canal_repetido_e_recusado_e_o_arquivo_fica_como_estava(tmp_path):
    arquivo = tmp_path / "canais.txt"
    arquivo.write_text("https://kick.com/coringa/videos\n", encoding="utf-8")
    with pytest.raises(agencia.ErroDeCarteira, match="repetido"):
        agencia.adicionar_canal(arquivo, "https://kick.com/Coringa/videos")
    assert arquivo.read_text(encoding="utf-8") == "https://kick.com/coringa/videos\n"


def test_primeiro_canal_cria_o_arquivo(tmp_path):
    canal = agencia.adicionar_canal(tmp_path / "canais.txt", "https://kick.com/xqc/videos")
    assert canal.vigiar is True and agencia.ler_carteira(tmp_path / "canais.txt") == [canal]


def test_nome_de_cliente_com_barra_vertical_nao_quebra_a_linha(tmp_path):
    canal = agencia.adicionar_canal(tmp_path / "canais.txt", "https://kick.com/xqc/videos", cliente="xQc | oficial")
    assert canal.cliente == "xQc   oficial"
