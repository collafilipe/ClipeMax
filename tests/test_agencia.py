import argparse
import datetime
import json
import threading
import time

import pytest

import agencia


# --------------------------------------------------------------------- carteira

def test_linha_so_com_o_link_continua_valendo_como_no_canais_txt_antigo():
    carteira = agencia.interpretar_carteira("# comentario\n\nhttps://kick.com/coringa/videos\n")
    assert [c.url for c in carteira] == ["https://kick.com/coringa/videos"]
    assert carteira[0].autorizado is False
    assert carteira[0].prioridade == 5


def test_opcoes_do_contrato_sao_lidas_da_linha_do_canal():
    linha = ("https://www.twitch.tv/alanzoka/videos?filter=archives | cliente=Alan | autorizado=sim | por_hora=2,5 "
             "| prioridade=1 | jogo=gta 6, gta vi | tags=#gta6 | mensalidade=800 | valor_mil_views=1.5")
    canal = agencia.interpretar_carteira(linha)[0]
    assert canal == agencia.Canal(url="https://www.twitch.tv/alanzoka/videos?filter=archives", cliente="Alan",
                                  autorizado=True, prioridade=1, por_hora=2.5, jogo="gta 6, gta vi", tags="#gta6",
                                  mensalidade=800.0, valor_mil_views=1.5)
    assert canal.chave == "twitch:alanzoka"


def test_opcao_desconhecida_e_recusada_com_o_numero_da_linha():
    with pytest.raises(agencia.ErroDeCarteira, match="linha 2.*prioridad"):
        agencia.interpretar_carteira("https://kick.com/a/videos\nhttps://kick.com/b/videos | prioridad=1")


def test_valor_que_nao_e_numero_e_recusado():
    with pytest.raises(agencia.ErroDeCarteira, match="linha 1.*numero"):
        agencia.interpretar_carteira("https://kick.com/a/videos | mensalidade=oitocentos")


def test_canal_repetido_e_recusado_porque_dois_fios_cortariam_a_mesma_live():
    with pytest.raises(agencia.ErroDeCarteira, match="linha 2: canal repetido.*linha 1"):
        agencia.interpretar_carteira("https://kick.com/Coringa/videos\nhttps://kick.com/coringa")


@pytest.mark.parametrize("url, chave", [
    ("https://kick.com/xQc/videos", "kick:xqc"),
    ("https://www.twitch.tv/kaicenat/videos?filter=archives", "twitch:kaicenat"),
    ("https://www.youtube.com/@IShowSpeed/streams", "youtube:ishowspeed"),
])
def test_chave_do_canal_ignora_maiusculas_e_o_resto_do_link(url, chave):
    assert agencia.chave_do_canal(url) == chave


def test_opcoes_do_canal_trocam_so_o_que_o_contrato_define_e_nao_mexem_na_original():
    a = argparse.Namespace(por_hora=3, cortes=8, jogo="", tags="", duracao=45)
    canal = agencia.Canal(url="https://kick.com/coringa/videos", por_hora=1.0, jogo="gta 6", prioridade=2)
    proprias = agencia.opcoes_do_canal(a, canal)
    assert (proprias.por_hora, proprias.jogo, proprias.cortes, proprias.duracao) == (1.0, "gta 6", 8, 45)
    assert (proprias.prioridade, proprias.canal_chave) == (2, "kick:coringa")
    assert (a.por_hora, a.jogo) == (3, "")
    assert not hasattr(a, "canal_chave")


# ------------------------------------------------------------------ fila pesada

def _esperar(condicao, limite=5.0):
    fim = time.time() + limite
    while not condicao():
        assert time.time() < fim, "a fila nao chegou ao estado esperado a tempo"
        time.sleep(0.005)


def test_fila_pesada_nunca_deixa_dois_trabalhos_rodarem_juntos():
    fila, dentro, maximo, trava = agencia.FilaPesada(), [0], [0], threading.Lock()

    def trabalho():
        with fila.vez():
            with trava:
                dentro[0] += 1
                maximo[0] = max(maximo[0], dentro[0])
            time.sleep(0.01)
            with trava:
                dentro[0] -= 1

    fios = [threading.Thread(target=trabalho) for _ in range(8)]
    for f in fios:
        f.start()
    for f in fios:
        f.join(5)
    assert maximo[0] == 1


def test_fila_pesada_atende_quem_espera_por_prioridade_e_depois_por_ordem_de_chegada():
    fila, ordem, soltar = agencia.FilaPesada(), [], threading.Event()

    def dono():
        with fila.vez(5):
            soltar.wait(5)

    def cliente(nome, prioridade):
        with fila.vez(prioridade):
            ordem.append(nome)

    primeiro = threading.Thread(target=dono)
    primeiro.start()
    _esperar(lambda: fila.esperando() == 0 and primeiro.is_alive())
    fios = []
    for k, (nome, prioridade) in enumerate([("teste", 9), ("normal_a", 5), ("vip", 1), ("normal_b", 5)], 1):
        f = threading.Thread(target=cliente, args=(nome, prioridade))
        f.start()
        fios.append(f)
        _esperar(lambda k=k: fila.esperando() == k)  # garante a ordem de chegada
    soltar.set()
    for f in [primeiro, *fios]:
        f.join(5)
    assert ordem == ["vip", "normal_a", "normal_b", "teste"]


def test_fila_pesada_e_liberada_mesmo_quando_o_trabalho_falha():
    fila = agencia.FilaPesada()
    with pytest.raises(RuntimeError):
        with fila.vez():
            raise RuntimeError("ffmpeg caiu")
    entrou = threading.Event()
    f = threading.Thread(target=lambda: (fila.vez().__enter__(), entrou.set()))
    f.start()
    assert entrou.wait(5)


# ----------------------------------------------------------------------- painel

AGORA = datetime.datetime(2026, 11, 13, 12, 0)


def _corte(situacao, dias_atras=1, **campos):
    return {"situacao": situacao, "quando": AGORA - datetime.timedelta(days=dias_atras), **campos}


def test_receita_estimada_soma_mensalidade_com_views_dos_aprovados():
    carteira = agencia.interpretar_carteira(
        "https://kick.com/coringa/videos | cliente=Coringa | autorizado=sim | mensalidade=500 | valor_mil_views=2")
    cortes = [_corte("aprovado", canal_chave="kick:coringa", views_tiktok=40_000, views_shorts=10_000),
              _corte("aprovado", canal_chave="kick:coringa", views_tiktok=None),
              _corte("descartado", canal_chave="kick:coringa", views_tiktok=999_999),
              _corte("pendente", canal_chave="kick:coringa")]
    linha = agencia.resumo_por_canal(carteira, cortes)[0]
    assert (linha["pendentes"], linha["aprovados"], linha["descartados"]) == (1, 2, 1)
    assert linha["views"] == 50_000
    assert linha["receita"] == pytest.approx(500 + 50 * 2)
    assert linha["aprovacao"] == pytest.approx(2 / 3)


def test_canal_sem_nada_revisado_fica_sem_taxa_de_aprovacao_em_vez_de_zero():
    carteira = agencia.interpretar_carteira("https://kick.com/novo/videos")
    linha = agencia.resumo_por_canal(carteira, [_corte("pendente", canal_chave="kick:novo")])[0]
    assert linha["aprovacao"] is None


def test_corte_antigo_sem_canal_chave_e_achado_pelo_nome_de_exibicao():
    carteira = agencia.interpretar_carteira("https://kick.com/paulinholokobr/videos")
    linhas = agencia.resumo_por_canal(carteira, [_corte("aprovado", canal="PaulinhoLOKObr", views_shorts=7)])
    assert len(linhas) == 1 and linhas[0]["views"] == 7


def test_corte_de_canal_que_saiu_da_carteira_aparece_separado_e_sem_autorizacao():
    linhas = agencia.resumo_por_canal([], [_corte("aprovado", canal="Fulano", views_tiktok=10)])
    assert linhas[0]["canal"] == "fora da carteira: Fulano"
    assert linhas[0]["autorizado"] is False


def test_periodo_do_painel_deixa_de_fora_cortes_mais_antigos():
    carteira = agencia.interpretar_carteira("https://kick.com/a/videos")
    cortes = [_corte("aprovado", 3, canal_chave="kick:a", views_tiktok=100),
              _corte("aprovado", 45, canal_chave="kick:a", views_tiktok=9_000)]
    linha = agencia.resumo_por_canal(carteira, cortes, desde=AGORA - datetime.timedelta(days=30))[0]
    assert (linha["aprovados"], linha["views"]) == (1, 100)


def test_painel_ordena_por_receita_e_avisa_canal_sem_autorizacao():
    carteira = agencia.interpretar_carteira(
        "https://kick.com/pequeno/videos | mensalidade=300\n"
        "https://kick.com/grande/videos | autorizado=sim | mensalidade=1500")
    texto = agencia.texto_do_painel(agencia.resumo_por_canal(carteira, []), 30)
    linhas = texto.splitlines()
    assert linhas[2].startswith("kick:grande") and "SEM AUTORIZACAO" not in linhas[2]
    assert linhas[3].startswith("kick:pequeno") and linhas[3].endswith("SEM AUTORIZACAO")
    assert "R$ 1.800,00" in linhas[4]


def test_ler_cortes_usa_criado_em_e_ignora_json_quebrado(tmp_path):
    aprovados = tmp_path / "aprovados" / "Coringa_123"
    aprovados.mkdir(parents=True)
    (aprovados / "0h10m00s.json").write_text(
        json.dumps({"canal": "Coringa", "criado_em": "2026-11-10T08:30:00", "views_tiktok": 5}), encoding="utf-8")
    (aprovados / "0h20m00s.json").write_text("{quebrado", encoding="utf-8")
    cortes = agencia.ler_cortes({"aprovado": tmp_path / "aprovados", "pendente": tmp_path / "prontos"})
    assert len(cortes) == 1
    assert cortes[0]["situacao"] == "aprovado"
    assert cortes[0]["quando"] == datetime.datetime(2026, 11, 10, 8, 30)


def test_idioma_por_canal_troca_o_da_linha_de_comando():
    br, fora = agencia.interpretar_carteira("https://kick.com/a/videos | idioma=PT\nhttps://kick.com/b/videos | idioma=auto")
    a = argparse.Namespace(idioma="auto")
    assert agencia.opcoes_do_canal(a, br).idioma == "pt"
    assert agencia.opcoes_do_canal(a, fora).idioma == "auto"
    assert agencia.linha_do_canal(br) == "https://kick.com/a/videos | idioma=pt"
    with pytest.raises(agencia.ErroDeCarteira):
        agencia.interpretar_carteira("https://kick.com/a/videos | idioma=portugues do brasil")
