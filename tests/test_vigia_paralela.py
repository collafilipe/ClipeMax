"""A rodada da vigia com varios canais. A rede e o video sao trocados por dubles: aqui so se testa a orquestracao."""
import argparse
import threading
import time

import pytest

pytest.importorskip("numpy")  # cortes.py importa numpy; os testes de agencia.py rodam sem ele

import agencia  # noqa: E402
import cortes  # noqa: E402


@pytest.fixture(autouse=True)
def _atividade_em_pasta_de_teste(monkeypatch, tmp_path):
    # a rodada avisa o escritorio do que cada clipador faz; no teste isso nao pode cair no estado/ de verdade
    monkeypatch.setattr(cortes, "ATIVIDADE", tmp_path / "atividade.json")
    # cada canal chama a esteira ao terminar; aqui ela nao pode mexer nos cortes de verdade
    monkeypatch.setattr(cortes, "rodar_esteira", lambda carteira, a: esteiras.append(len(carteira)))


esteiras = []


def test_cada_canal_manda_os_cortes_para_a_esteira_assim_que_termina(monkeypatch):
    carteira = agencia.interpretar_carteira("https://kick.com/a/videos\nhttps://kick.com/b/videos")
    monkeypatch.setattr(cortes, "vigiar_canal", lambda url, a: None)
    esteiras.clear()
    cortes.rodada(carteira, _opcoes())
    assert esteiras == [2, 2]


def test_canal_com_erro_nao_chama_a_esteira(monkeypatch):
    def quebrado(url, a):
        raise RuntimeError("fora do ar")

    carteira = agencia.interpretar_carteira("https://kick.com/a/videos")
    monkeypatch.setattr(cortes, "vigiar_canal", quebrado)
    esteiras.clear()
    cortes.rodada(carteira, _opcoes())
    assert esteiras == []


def _opcoes(**extra):
    return argparse.Namespace(paralelos=4, por_hora=3, cortes=8, jogo="", tags="", **extra)


def test_canais_sao_vigiados_ao_mesmo_tempo_e_nao_em_fila(monkeypatch):
    carteira = agencia.interpretar_carteira("\n".join(f"https://kick.com/canal{i}/videos" for i in range(4)))
    todos_juntos = threading.Barrier(4, timeout=5)
    monkeypatch.setattr(cortes, "vigiar_canal", lambda url, a: todos_juntos.wait())
    # em fila a barreira de 4 nunca fecharia e o teste falharia por tempo
    cortes.rodada(carteira, _opcoes())
    assert not todos_juntos.broken


def test_paralelos_limita_quantos_canais_rodam_juntos(monkeypatch):
    carteira = agencia.interpretar_carteira("\n".join(f"https://kick.com/canal{i}/videos" for i in range(6)))
    dentro, maximo, trava = [0], [0], threading.Lock()

    def falso(url, a):
        with trava:
            dentro[0] += 1
            maximo[0] = max(maximo[0], dentro[0])
        time.sleep(0.05)
        with trava:
            dentro[0] -= 1

    monkeypatch.setattr(cortes, "vigiar_canal", falso)
    cortes.rodada(carteira, argparse.Namespace(**{**vars(_opcoes()), "paralelos": 2}))
    assert maximo[0] == 2


def test_cada_canal_recebe_as_opcoes_do_proprio_contrato(monkeypatch):
    carteira = agencia.interpretar_carteira(
        "https://kick.com/coringa/videos | por_hora=1 | jogo=gta 6 | prioridade=1\n"
        "https://www.twitch.tv/alanzoka/videos")
    vistos = {}
    monkeypatch.setattr(cortes, "vigiar_canal",
                        lambda url, a: vistos.update({a.canal_chave: (a.por_hora, a.jogo, a.prioridade)}))
    cortes.rodada(carteira, _opcoes())
    assert vistos == {"kick:coringa": (1.0, "gta 6", 1), "twitch:alanzoka": (3, "", 5)}


def test_erro_em_um_canal_nao_impede_os_outros_de_rodar(monkeypatch, capsys):
    carteira = agencia.interpretar_carteira("https://kick.com/quebrado/videos\nhttps://kick.com/bom/videos")
    feitos = []

    def falso(url, a):
        if "quebrado" in url:
            raise RuntimeError("plataforma fora do ar")
        feitos.append(url)

    monkeypatch.setattr(cortes, "vigiar_canal", falso)
    cortes.rodada(carteira, _opcoes())
    assert feitos == ["https://kick.com/bom/videos"]
    assert "[kick:quebrado] ERRO em https://kick.com/quebrado/videos: plataforma fora do ar" in capsys.readouterr().out


def test_falhas_contadas_por_varios_canais_ao_mesmo_tempo_nao_se_perdem(monkeypatch, tmp_path):
    monkeypatch.setattr(cortes, "ESTADO", tmp_path)
    monkeypatch.setattr(cortes, "FALHAS", tmp_path / "falhas.json")
    monkeypatch.setattr(cortes, "PROCESSADOS", tmp_path / "processados.txt")
    fios = [threading.Thread(target=cortes._contar_falha, args=(f"https://kick.com/video/{i}",)) for i in range(20)]
    for f in fios:
        f.start()
    for f in fios:
        f.join(5)
    import json
    assert len(json.loads((tmp_path / "falhas.json").read_text(encoding="utf-8"))) == 20


# ------------------------------------------------------- pedidos do CEO: qual time atende

def _info(canal="xQc", login="xqc"):
    return {"canal": canal, "login": login}


def test_pedido_vai_para_o_time_que_o_ceo_escolheu(tmp_path):
    arquivo = tmp_path / "canais.txt"
    arquivo.write_text("https://kick.com/coringa/videos | cliente=Coringa\n", encoding="utf-8")
    canal = cortes._time_do_pedido({"time": "kick:coringa", "plataforma": "twitch", "canal": ""}, arquivo, _info())
    assert canal.chave == "kick:coringa"
    assert len(agencia.ler_carteira(arquivo)) == 1


def test_pedido_sem_time_escolhido_vai_para_o_time_do_canal_do_video(tmp_path):
    arquivo = tmp_path / "canais.txt"
    arquivo.write_text("https://kick.com/xqc/videos\n", encoding="utf-8")
    canal = cortes._time_do_pedido({"time": "", "plataforma": "kick", "canal": "xqc"}, arquivo, _info())
    assert canal.chave == "kick:xqc" and canal.vigiar is True


def test_live_de_canal_sem_time_cria_um_time_que_so_trabalha_a_pedido(tmp_path):
    arquivo = tmp_path / "canais.txt"
    canal = cortes._time_do_pedido({"time": "", "plataforma": "youtube", "canal": ""}, arquivo, _info("IShowSpeed", "@IShowSpeed"))
    assert (canal.chave, canal.cliente, canal.vigiar) == ("youtube:ishowspeed", "IShowSpeed", False)
    assert arquivo.read_text(encoding="utf-8").strip() == "https://www.youtube.com/@ishowspeed/streams | cliente=IShowSpeed | vigiar=nao"


def test_vigia_nao_acompanha_time_que_so_trabalha_a_pedido(monkeypatch, tmp_path):
    arquivo = tmp_path / "canais.txt"
    arquivo.write_text("https://kick.com/a/videos\nhttps://kick.com/b/videos | vigiar=nao\n", encoding="utf-8")
    vistos = []
    monkeypatch.setattr(cortes, "vigiar_canal", lambda url, a: vistos.append(url))
    monkeypatch.setattr(cortes, "ESTADO", tmp_path / "estado")
    cortes.vigiar(argparse.Namespace(**{**vars(_opcoes()), "vigiar": str(arquivo), "intervalo": 10, "uma_rodada": True}))
    assert vistos == ["https://kick.com/a/videos"]
