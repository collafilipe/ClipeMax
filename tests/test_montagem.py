import datetime
import json

import montagem
import voz


def _item(canal, nota):
    return {"video": f"{canal}.mp4", "canal": canal, "nota": nota}


def test_ranking_abre_com_a_menor_nota_e_fecha_com_a_melhor():
    itens = [_item("A", 9), _item("B", None), _item("C", 6)]
    assert [i["canal"] for i in montagem.ordenar(itens, "ranking")] == ["B", "C", "A"]
    assert montagem.posicoes(itens, "ranking") == [3, 2, 1]


def test_comparacao_mantem_a_ordem_escolhida():
    itens = [_item("A", 9), _item("B", 2)]
    assert montagem.ordenar(itens, "comparacao") == itens
    assert montagem.posicoes(itens, "comparacao") == [1, 2]


def test_fala_da_cartela_abre_com_o_titulo_e_anuncia_o_primeiro_lugar():
    assert montagem.fala_da_cartela("ranking", 0, 3, "Coringa", "Top 3 sustos!") == "Top 3 sustos. Número 3: Coringa."
    assert montagem.fala_da_cartela("ranking", 2, 3, "Cellbit", "Top 3") == "E em primeiro lugar: Cellbit."
    assert montagem.fala_da_cartela("comparacao", 1, 2, "Yuri22", "x") == "Agora, Yuri22."


def test_montar_recusa_tipo_e_quantidade_invalidos(tmp_path):
    assert montagem.montar([_item("A", 1), _item("B", 2)], "t", "mosaico", tmp_path / "m.mp4")[0] is False
    ok, erro, _ = montagem.montar([_item("A", 1)], "t", "ranking", tmp_path / "m.mp4")
    assert ok is False and "2 a 8" in erro


def test_criar_grava_a_montagem_direto_na_mesa_do_ceo(tmp_path):
    prontos, pedido = tmp_path / "prontos", {}
    pasta = prontos / "Coringa_1"
    pasta.mkdir(parents=True)
    (pasta / "a.mp4").write_bytes(b"x")
    (pasta / "a.base").write_bytes(b"x")  # o video sem a caixa de comentario e o que entra na montagem
    (pasta / "b.mp4").write_bytes(b"x")

    def falso(itens, titulo, tipo, destino, narrar=True):
        pedido.update(itens=itens, destino=destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"video")
        return True, "", {"duracao": 90.0, "narrado": True, "ordem": [i["canal"] for i in montagem.ordenar(itens, tipo)]}

    cortes = [{"video": pasta / "a.mp4", "dados": {"canal": "Coringa", "nota_ia": 8, "nota_gestor": 5, "jogo": "GTA VI"}},
              {"video": pasta / "b.mp4", "dados": {"canal": "Yuri 22", "nota_ia": 7, "jogo": "GTA VI"}}]
    ok, erro, dados = montagem.criar(cortes, "  Quem   sofreu mais? ", "ranking", prontos,
                                     agora=datetime.datetime(2026, 11, 19, 20, 0, 0), montar_video=falso)
    assert ok and not erro
    assert pedido["itens"][0]["video"].suffix == ".base" and pedido["itens"][0]["nota"] == 5
    assert pedido["destino"] == prontos / "Montagens" / "20261119_200000_quem-sofreu-mais.mp4"
    gravado = json.loads(pedido["destino"].with_suffix(".json").read_text(encoding="utf-8"))
    assert gravado == dados and dados["etapa"] == "ceo" and dados["montagem"] and dados["jogo"] == "GTA VI"
    assert dados["titulo"] == "Quem sofreu mais?" and "#coringa #yuri22" in dados["tiktok"]
    assert [p["canal"] for p in dados["partes"]] == ["Coringa", "Yuri 22"]  # nota 5 abre, nota 7 fecha


def test_criar_exige_titulo(tmp_path):
    ok, erro, _ = montagem.criar([], "   ", "ranking", tmp_path, montar_video=lambda *a, **k: (True, "", {}))
    assert ok is False and "titulo" in erro


def test_falar_passa_o_texto_numa_palavra_so_e_some_com_arquivo_ruim(tmp_path):
    chamadas, destino = [], tmp_path / "f.mp3"

    class Resp:
        returncode = 0

    def rodar(cmd, **k):
        chamadas.append(cmd)
        destino.write_bytes(b"x" * (5000 if len(chamadas) == 1 else 10))
        return Resp()

    assert voz.falar("-  opa,   isso  aí", destino, rodar=rodar, chave="") is True and voz.ULTIMO == "edge"
    assert "--text=- opa, isso aí" in chamadas[0]
    assert voz.falar("curto", destino, rodar=rodar, chave="") is False and not destino.exists()
    assert voz.falar("   ", destino, rodar=rodar, chave="") is False and len(chamadas) == 2


def test_falar_usa_o_elevenlabs_guarda_a_frase_e_cai_na_reserva_se_falhar(tmp_path):
    pedidos, destino, cache = [], tmp_path / "f.mp3", tmp_path / "cache"

    def eleven(texto, arq, chave):
        pedidos.append((texto, chave))
        arq.write_bytes(b"e" * 4000)
        return True

    def nunca(cmd, **k):
        raise AssertionError("a reserva nao devia ser chamada")

    assert voz.falar("Isso  é opinião", destino, rodar=nunca, chave="k", eleven=eleven, cache=cache) and voz.ULTIMO == "eleven"
    destino.unlink()
    assert voz.falar("Isso é opinião", destino, rodar=nunca, chave="k", eleven=eleven, cache=cache)
    assert voz.ULTIMO == "eleven (cache)" and pedidos == [("Isso é opinião", "k")] and destino.stat().st_size == 4000

    class Resp:
        returncode = 0

    def reserva(cmd, **k):
        destino.write_bytes(b"x" * 5000)
        return Resp()

    assert voz.falar("outra frase", destino, rodar=reserva, chave="k", eleven=lambda *a: False, cache=cache)
    assert voz.ULTIMO == "edge" and len(list(cache.iterdir())) == 1  # fala da reserva nao entra no cache


def test_chave_do_elevenlabs_vem_do_primeiro_arquivo_preenchido(tmp_path):
    (tmp_path / "vazia.txt").write_text("  \n")
    (tmp_path / "boa.txt").write_text(" abc123 \n")
    assert voz._chave([tmp_path / "nao_existe.txt", tmp_path / "vazia.txt", tmp_path / "boa.txt"]) == "abc123"
    assert voz._chave([tmp_path / "nao_existe.txt"]) is None


def test_escolher_fundo_e_estavel_e_cabe_no_video(tmp_path):
    import video
    assert video.escolher_fundo(7, 30, pasta=tmp_path / "nao_existe") is None
    (tmp_path / "leia.txt").write_text("x")
    assert video.escolher_fundo(7, 30, pasta=tmp_path) is None  # so video conta
    for nome in ("a.mp4", "b.MOV"):
        (tmp_path / nome).write_bytes(b"x")
    um = video.escolher_fundo(7, 30, pasta=tmp_path, duracao=lambda f: 100.0)
    assert um == video.escolher_fundo(7, 30, pasta=tmp_path, duracao=lambda f: 100.0)
    assert um[0].parent == tmp_path and 0 <= um[1] <= 70
    assert video.escolher_fundo(7, 30, pasta=tmp_path, duracao=lambda f: 12.0)[1] == 0  # fundo curto: comeca do zero e repete
    assert video.escolher_fundo(7, 30, pasta=tmp_path, duracao=lambda f: 0.0) is None


def test_filtro_do_video_embaixo_so_vale_para_camera_cheia():
    import video
    com = video.filtro_video("blur", ("x", 0.5), None, fundo=True)
    assert "[1:v]scale=1080:840" in com and "vstack" in com
    assert "vstack" not in video.filtro_video("blur", ("x", 0.5), None)
