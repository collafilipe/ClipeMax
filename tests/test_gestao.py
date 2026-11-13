"""Pagina Gestao: mudar times e empresa, ver desempenho e postar, tudo sem linha de comando."""
import json

import pytest

import agencia

pytest.importorskip("numpy")  # gestao.py importa fontes, que importa numpy

import gestao  # noqa: E402

CANAIS = ("# meus canais\n"
          "https://kick.com/coringa/videos | cliente=Coringa | prioridade=1\n"
          "\n"
          "# gringos\n"
          "https://kick.com/xqc/videos\n")


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    (tmp_path / "canais.txt").write_text(CANAIS, encoding="utf-8")
    monkeypatch.setattr(gestao, "CARTEIRA", tmp_path / "canais.txt")
    monkeypatch.setattr(gestao, "EMPRESA", tmp_path / "empresa.json")
    monkeypatch.setattr(gestao, "SEGREDOS", tmp_path / "segredos")
    monkeypatch.setattr(gestao, "PASTAS", {k: tmp_path / k for k in ("pendente", "aprovado", "descartado")})
    return tmp_path


def _aprovado(pasta, nome="a", **campos):
    destino = pasta / "aprovado" / "coringa"
    destino.mkdir(parents=True, exist_ok=True)
    dados = {"canal": "Coringa", "canal_chave": "kick:coringa", "titulo": "Titulo", "criado_em": "2026-11-13T10:00:00",
             "trilha": [{"etapa": "gerente", "veredito": "aprovado"}, {"etapa": "ceo", "veredito": "aprovado", "quando": "2026-11-13T11:00:00"}],
             **campos}
    (destino / f"{nome}.json").write_text(json.dumps(dados), encoding="utf-8")
    (destino / f"{nome}.mp4").write_bytes(b"video")


# ----------------------------------------------------------------------- times

def test_salvar_time_muda_so_a_linha_dele_e_preserva_comentarios(pasta):
    r = gestao.salvar_time({"chave": "kick:xqc", "campos": {"cliente": "xQc", "autorizado": True, "jogo": "gta 6", "por_hora": "2",
                                                            "mensalidade": "800", "vigiar": False}})
    assert "xQc" in r["mensagem"]
    assert (pasta / "canais.txt").read_text(encoding="utf-8").splitlines() == [
        "# meus canais", "https://kick.com/coringa/videos | cliente=Coringa | prioridade=1", "", "# gringos",
        "https://kick.com/xqc/videos | cliente=xQc | autorizado=sim | vigiar=nao | por_hora=2 | jogo=gta 6 | mensalidade=800"]


def test_campo_em_branco_volta_ao_padrao(pasta):
    gestao.salvar_time({"chave": "kick:coringa", "campos": {"cliente": "", "prioridade": ""}})
    canal = agencia.ler_carteira(pasta / "canais.txt")[0]
    assert (canal.cliente, canal.prioridade) == ("", 5)
    assert (pasta / "canais.txt").read_text(encoding="utf-8").splitlines()[1] == "https://kick.com/coringa/videos"


def test_valor_invalido_e_recusado_e_o_arquivo_fica_como_estava(pasta):
    with pytest.raises(agencia.ErroDeCarteira, match="numero"):
        gestao.salvar_time({"chave": "kick:xqc", "campos": {"por_hora": "muitos"}})
    with pytest.raises(agencia.ErroDeCarteira, match="desconhecida"):
        gestao.salvar_time({"chave": "kick:xqc", "campos": {"url": "https://kick.com/outro"}})
    with pytest.raises(agencia.ErroDeCarteira, match="nao esta no arquivo"):
        gestao.salvar_time({"chave": "kick:ninguem", "campos": {"cliente": "x"}})
    assert (pasta / "canais.txt").read_text(encoding="utf-8") == CANAIS


def test_remover_time_tira_so_a_linha_dele(pasta):
    gestao.salvar_time({"chave": "kick:coringa", "remover": True})
    assert [c.chave for c in agencia.ler_carteira(pasta / "canais.txt")] == ["kick:xqc"]
    assert "# meus canais" in (pasta / "canais.txt").read_text(encoding="utf-8")


def test_linha_do_canal_volta_igual_depois_de_lida():
    linha = "https://kick.com/a/videos | cliente=A | funcionario=Bia | autorizado=sim | prioridade=2 | por_hora=1.5 | tags=#x | conta=gringos"
    assert agencia.linha_do_canal(agencia.interpretar_carteira(linha)[0]) == linha


# --------------------------------------------------------------------- empresa

def test_empresa_grava_so_o_que_difere_do_padrao(pasta):
    gestao.salvar_empresa({"campos": {"nome": "Cortes do Filipe", "gerente": "Gustavo", "cota_ceo_por_canal": "3", "diretor": "Diretor editorial"}})
    assert json.loads((pasta / "empresa.json").read_text(encoding="utf-8")) == {"nome": "Cortes do Filipe", "gerente": "Gustavo", "cota_ceo_por_canal": 3}
    gestao.salvar_empresa({"campos": {"gerente": ""}})  # nome em branco volta ao padrao
    assert "gerente" not in json.loads((pasta / "empresa.json").read_text(encoding="utf-8"))
    assert gestao.config()["empresa"]["cota_ceo_por_canal"] == 3


@pytest.mark.parametrize("campos, trecho", [
    ({"cota_ceo_por_canal": "0"}, "entre 1 e 50"), ({"nota_minima_gerente": "11"}, "entre 1 e 10"),
    ({"cota_ceo_por_canal": "cinco"}, "numero inteiro"), ({"salario": "10"}, "desconhecida"),
    ({"duracao_minima": "90"}, "menor que a maxima"),
])
def test_empresa_recusa_valor_fora_da_faixa_e_nao_grava(pasta, campos, trecho):
    with pytest.raises(ValueError, match=trecho):
        gestao.salvar_empresa({"campos": campos})
    assert not (pasta / "empresa.json").exists()


# -------------------------------------------------------- desempenho e postagem

def test_painel_traz_receita_e_avaliacao_prontas_para_a_tela(pasta):
    gestao.salvar_time({"chave": "kick:coringa", "campos": {"mensalidade": "500", "valor_mil_views": "2"}})
    _aprovado(pasta, views_shorts=10_000)
    q = gestao.painel({"dias": ["0"]})
    coringa = next(l for l in q["receita"] if l["canal"] == "Coringa")
    assert (coringa["aprovados"], coringa["views"], coringa["receita"]) == (1, 10_000, 520.0)
    assert isinstance(coringa["ultimo"], str)  # data ja em texto: a tela recebe JSON
    assert q["gerente"]["julgados_pelo_ceo"] == 1 and q["times"][0]["aprovados_ceo"] == 1
    json.dumps(q)


def test_postar_pelo_site_simula_por_padrao_e_respeita_a_autorizacao(pasta):
    _aprovado(pasta)
    r = gestao.postar({"plataforma": "youtube"})
    assert r["feitos"] == 0 and any("bloqueado" in l and "autorizado=sim" in l for l in r["linhas"])
    gestao.salvar_time({"chave": "kick:coringa", "campos": {"autorizado": True}})
    r = gestao.postar({"plataforma": "youtube"})
    assert any(l.startswith("postaria: Coringa a") for l in r["linhas"]) and "simulacao" in r["linhas"][-1]
    assert "postado_youtube" not in json.loads((pasta / "aprovado" / "coringa" / "a.json").read_text(encoding="utf-8"))


def test_postar_recusa_plataforma_ou_visibilidade_desconhecida(pasta):
    with pytest.raises(ValueError):
        gestao.postar({"plataforma": "kwai"})
    with pytest.raises(ValueError):
        gestao.postar({"plataforma": "youtube", "visibilidade": "secreto"})


def test_config_mostra_contas_conectadas_e_quantos_aprovados_esperam(pasta):
    _aprovado(pasta, "a")
    _aprovado(pasta, "b", postado_youtube={"id": "x"})
    (pasta / "segredos").mkdir()
    for nome in ("youtube_app", "youtube_token", "youtube_token_gringos"):
        (pasta / "segredos" / f"{nome}.json").write_text("{}", encoding="utf-8")
    p = gestao.config()["postagem"]
    assert p["youtube"] == {"app": True, "contas": ["gringos", "principal"], "recado": "", "esperando": 1}
    assert (p["tiktok"]["app"], p["tiktok"]["contas"], p["tiktok"]["esperando"]) == (False, [], 2)


def test_conectar_sem_as_chaves_do_app_explica_o_que_falta_em_vez_de_abrir_o_navegador(pasta):
    with pytest.raises(ValueError, match="youtube_app.json"):
        gestao.conectar({"plataforma": "youtube"})
