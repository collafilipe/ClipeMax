"""Postagem sem rede: `http` e um duble que devolve respostas no formato documentado pelo YouTube e pelo TikTok."""
import datetime
import json
import time
import urllib.parse

import pytest

import agencia
import postagem

CARTEIRA = agencia.interpretar_carteira(
    "https://kick.com/coringa/videos | cliente=Coringa | autorizado=sim\n"
    "https://kick.com/xqc/videos | conta=gringos\n")


class Rede:
    """Responde por trecho da URL e guarda as chamadas, para o teste conferir o que foi enviado."""

    def __init__(self, respostas):
        self.respostas, self.chamadas = respostas, []

    def __call__(self, metodo, url, cabecalhos=None, corpo=None, timeout=300):
        self.chamadas.append({"metodo": metodo, "url": url, "cabecalhos": cabecalhos or {}, "corpo": corpo})
        for trecho, resposta in self.respostas:
            if trecho in url:
                status, cab, dados = resposta(self.chamadas[-1]) if callable(resposta) else resposta
                return status, cab, dados if isinstance(dados, bytes) else json.dumps(dados).encode()
        raise AssertionError(f"chamada inesperada: {metodo} {url}")

    def para(self, trecho):
        return [c for c in self.chamadas if trecho in c["url"]]


YT_OK = [("uploadType=resumable", (200, {"Location": "https://upload.exemplo/sessao1"}, {})),
         ("upload.exemplo", (200, {}, {"id": "abc123"}))]


@pytest.fixture
def pastas(tmp_path):
    segredos = tmp_path / "segredos"
    segredos.mkdir()
    (segredos / "youtube_app.json").write_text(
        json.dumps({"installed": {"client_id": "app-yt", "client_secret": "s"}}), encoding="utf-8")
    (segredos / "tiktok_app.json").write_text(json.dumps({"client_key": "app-tt", "client_secret": "s"}), encoding="utf-8")
    for nome in ("youtube_token", "tiktok_token", "youtube_token_gringos"):
        (segredos / f"{nome}.json").write_text(json.dumps(
            {"access_token": "tok-" + nome, "refresh_token": "ref", "expira_em": time.time() + 3600}), encoding="utf-8")
    return tmp_path


def _criar_corte(raiz, situacao="aprovado", canal_chave="kick:coringa", nome="0h10m00s", video=b"video", **campos):
    pasta = raiz / {"aprovado": "aprovados", "pendente": "prontos"}[situacao] / canal_chave.replace(":", "_")
    pasta.mkdir(parents=True, exist_ok=True)
    dados = {"canal": canal_chave.split(":")[1], "canal_chave": canal_chave, "titulo": "Ele nao acreditou",
             "shorts": "#gta6", "origem": "https://kick.com/video/1", "criado_em": "2026-11-10T08:00:00", **campos}
    (pasta / f"{nome}.json").write_text(json.dumps(dados), encoding="utf-8")
    (pasta / f"{nome}.mp4").write_bytes(video)
    return pasta / f"{nome}.json"


def _cortes(raiz):
    return agencia.ler_cortes({"aprovado": raiz / "aprovados", "pendente": raiz / "prontos"})


def _postar(raiz, plataforma, rede, **extra):
    falas = []
    n = postagem.postar(_cortes(raiz), CARTEIRA, plataforma, raiz / "segredos", http=rede, log=falas.append, **extra)
    return n, "\n".join(falas)


# ---------------------------------------------------------------- quem pode postar

def test_so_e_postado_corte_aprovado_de_canal_autorizado(pastas):
    _criar_corte(pastas, "aprovado", "kick:coringa")
    _criar_corte(pastas, "pendente", "kick:coringa", nome="0h20m00s")
    _criar_corte(pastas, "aprovado", "kick:xqc")
    rede = Rede(YT_OK)
    n, falas = _postar(pastas, "youtube", rede)
    assert n == 1
    assert len(rede.para("uploadType=resumable")) == 1
    assert "bloqueado: 0h10m00s de xqc (kick:xqc esta sem autorizado=sim na carteira)" in falas


def test_corte_de_canal_fora_da_carteira_e_bloqueado(pastas):
    _criar_corte(pastas, "aprovado", "kick:desconhecido")
    n, falas = _postar(pastas, "youtube", Rede([]))
    assert n == 0 and "canal fora da carteira" in falas


def test_rodar_de_novo_nao_posta_o_mesmo_corte_duas_vezes(pastas):
    arq = _criar_corte(pastas)
    rede = Rede(YT_OK)
    assert _postar(pastas, "youtube", rede)[0] == 1
    assert _postar(pastas, "youtube", rede)[0] == 0
    assert len(rede.para("uploadType=resumable")) == 1
    gravado = json.loads(arq.read_text(encoding="utf-8"))["postado_youtube"]
    assert gravado["id"] == "abc123" and gravado["url"] == "https://www.youtube.com/shorts/abc123"


def test_postado_no_youtube_continua_pendente_para_o_tiktok(pastas):
    _criar_corte(pastas, postado_youtube={"id": "abc123"})
    liberados, _ = postagem.separar_pendentes(_cortes(pastas), CARTEIRA, "tiktok")
    assert len(liberados) == 1
    assert postagem.separar_pendentes(_cortes(pastas), CARTEIRA, "youtube")[0] == []


def test_simular_lista_e_nao_envia_nada(pastas):
    arq = _criar_corte(pastas)
    rede = Rede([])
    n, falas = _postar(pastas, "youtube", rede, simular=True)
    assert n == 0 and rede.chamadas == []
    assert "postaria: coringa 0h10m00s" in falas
    assert "postado_youtube" not in json.loads(arq.read_text(encoding="utf-8"))


def test_limite_posta_os_mais_antigos_primeiro(pastas):
    _criar_corte(pastas, nome="novo", criado_em="2026-11-12T08:00:00")
    antigo = _criar_corte(pastas, nome="antigo", criado_em="2026-11-01T08:00:00")
    assert _postar(pastas, "youtube", Rede(YT_OK), limite=1)[0] == 1
    assert "postado_youtube" in json.loads(antigo.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------- youtube

def test_youtube_sai_privado_por_padrao_e_publico_so_quando_pedido(pastas):
    _criar_corte(pastas, nome="a")
    rede = Rede(YT_OK)
    _postar(pastas, "youtube", rede)
    assert json.loads(rede.para("uploadType")[0]["corpo"])["status"]["privacyStatus"] == "private"
    _criar_corte(pastas, nome="b")
    _postar(pastas, "youtube", rede, visibilidade="publico")
    assert json.loads(rede.para("uploadType")[1]["corpo"])["status"]["privacyStatus"] == "public"


def test_youtube_envia_o_arquivo_inteiro_para_o_endereco_que_a_api_devolveu(pastas):
    _criar_corte(pastas, video=b"x" * 1000)
    rede = Rede(YT_OK)
    _postar(pastas, "youtube", rede)
    inicio, envio = rede.chamadas
    assert inicio["cabecalhos"]["Authorization"] == "Bearer tok-youtube_token"
    assert inicio["cabecalhos"]["X-Upload-Content-Length"] == "1000"
    assert (envio["metodo"], envio["url"], envio["corpo"]) == ("PUT", "https://upload.exemplo/sessao1", b"x" * 1000)


def test_texto_do_youtube_respeita_limites_e_leva_shorts_e_credito():
    titulo, descricao = postagem.texto_youtube(
        {"titulo": "  a " * 60, "shorts": "#gta6", "canal": "Coringa", "origem": "https://kick.com/video/1"})
    assert len(titulo) == postagem.YT_TITULO_MAX and "  " not in titulo
    assert descricao == "#gta6 #shorts\n\nCorte da live de Coringa: https://kick.com/video/1"


def test_corte_sem_titulo_falha_sozinho_e_os_outros_seguem(pastas):
    _criar_corte(pastas, nome="a", titulo="", criado_em="2026-11-01T00:00:00")
    _criar_corte(pastas, nome="b")
    n, falas = _postar(pastas, "youtube", Rede(YT_OK))
    assert n == 1 and "falhou: coringa a: corte sem titulo" in falas


def test_cota_do_youtube_esgotada_para_a_fila_em_vez_de_insistir(pastas):
    _criar_corte(pastas, nome="a", criado_em="2026-11-01T00:00:00")
    _criar_corte(pastas, nome="b")
    rede = Rede([("uploadType", (403, {}, {"error": {"message": "limite", "errors": [{"reason": "uploadLimitExceeded"}]}}))])
    n, falas = _postar(pastas, "youtube", rede)
    assert n == 0 and len(rede.chamadas) == 1
    assert "parei em coringa a" in falas


def test_cada_canal_posta_na_conta_definida_no_contrato(pastas):
    carteira = agencia.interpretar_carteira("https://kick.com/xqc/videos | autorizado=sim | conta=gringos")
    _criar_corte(pastas, canal_chave="kick:xqc")
    rede = Rede(YT_OK)
    postagem.postar(_cortes(pastas), carteira, "youtube", pastas / "segredos", http=rede, log=lambda m: None)
    assert rede.chamadas[0]["cabecalhos"]["Authorization"] == "Bearer tok-youtube_token_gringos"


def test_views_do_youtube_vao_para_o_campo_que_o_painel_le(pastas):
    arq = _criar_corte(pastas, postado_youtube={"id": "abc123"}, views_tiktok=7)
    rede = Rede([("part=statistics", (200, {}, {"items": [{"id": "abc123", "statistics": {"viewCount": "4321"}}]}))])
    assert postagem.atualizar_views(_cortes(pastas), CARTEIRA, pastas / "segredos", http=rede, log=lambda m: None) == 1
    gravado = json.loads(arq.read_text(encoding="utf-8"))
    assert (gravado["views_shorts"], gravado["views_tiktok"]) == (4321, 7)


# ------------------------------------------------------------------------ tiktok

def test_tiktok_vai_como_rascunho_em_pedaco_unico_quando_cabe(pastas):
    arq = _criar_corte(pastas, video=b"y" * 500)
    rede = Rede([("inbox/video/init", (200, {}, {"data": {"publish_id": "p1", "upload_url": "https://envio.exemplo/u"}})),
                 ("envio.exemplo", (201, {}, {}))])
    n, falas = _postar(pastas, "tiktok", rede)
    assert n == 1 and "rascunho na caixa de entrada" in falas
    assert json.loads(rede.chamadas[0]["corpo"])["source_info"] == {
        "source": "FILE_UPLOAD", "video_size": 500, "chunk_size": 500, "total_chunk_count": 1}
    assert rede.chamadas[1]["cabecalhos"]["Content-Range"] == "bytes 0-499/500"
    assert json.loads(arq.read_text(encoding="utf-8"))["postado_tiktok"] == {
        "id": "p1", "rascunho": True, "quando": json.loads(arq.read_text(encoding="utf-8"))["postado_tiktok"]["quando"]}


def test_video_grande_no_tiktok_vai_em_pedacos_e_o_ultimo_leva_o_resto():
    mb = 1024 * 1024
    assert postagem.pedacos_tiktok(64 * mb) == (64 * mb, 1)
    assert postagem.pedacos_tiktok(75 * mb + 3) == (10 * mb, 7)


def test_limite_de_rascunhos_do_tiktok_para_a_fila(pastas):
    _criar_corte(pastas, nome="a", criado_em="2026-11-01T00:00:00")
    _criar_corte(pastas, nome="b")
    rede = Rede([("inbox/video/init", (403, {}, {"error": {"code": "spam_risk_too_many_pending_share", "message": "x"}}))])
    n, falas = _postar(pastas, "tiktok", rede)
    assert n == 0 and len(rede.chamadas) == 1 and "parei em" in falas


# ------------------------------------------------------------------------ contas

def test_token_vencido_e_renovado_e_o_refresh_do_google_e_preservado(pastas):
    arq = pastas / "segredos" / "youtube_token.json"
    arq.write_text(json.dumps({"access_token": "velho", "refresh_token": "ref", "expira_em": 100}), encoding="utf-8")
    rede = Rede([("oauth2.googleapis.com/token", (200, {}, {"access_token": "novo", "expires_in": 3600}))])
    assert postagem.token_de_acesso(pastas / "segredos", "youtube", http=rede, agora=lambda: 1000) == "novo"
    enviado = urllib.parse.parse_qs(rede.chamadas[0]["corpo"].decode())
    assert enviado["grant_type"] == ["refresh_token"] and enviado["client_id"] == ["app-yt"]
    assert json.loads(arq.read_text(encoding="utf-8")) == {"access_token": "novo", "refresh_token": "ref", "expira_em": 4600}


def test_token_ainda_valido_nao_gasta_chamada(pastas):
    rede = Rede([])
    assert postagem.token_de_acesso(pastas / "segredos", "tiktok", http=rede) == "tok-tiktok_token"
    assert rede.chamadas == []


def test_conta_nao_conectada_explica_o_comando_e_para_a_postagem(pastas):
    (pastas / "segredos" / "youtube_token.json").unlink()
    _criar_corte(pastas)
    n, falas = _postar(pastas, "youtube", Rede([]))
    assert n == 0 and "cortes.bat --conectar youtube --conta principal" in falas


def test_link_de_autorizacao_do_google_pede_acesso_que_nao_expira():
    link = postagem.link_de_autorizacao("youtube", {"id": "app-yt", "segredo": "s"}, "http://127.0.0.1:5000/callback/",
                                        "estado", "verificador")
    campos = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
    assert campos["access_type"] == ["offline"] and campos["prompt"] == ["consent"]
    assert campos["state"] == ["estado"] and campos["code_challenge_method"] == ["S256"]
    assert "youtube.upload" in campos["scope"][0]


def test_nome_de_conta_com_caminho_e_recusado_na_carteira():
    with pytest.raises(agencia.ErroDeCarteira, match="conta aceita so"):
        agencia.interpretar_carteira("https://kick.com/a/videos | conta=../fora")


def test_data_do_corte_ordena_a_fila_de_postagem():
    cortes = [{"situacao": "aprovado", "quando": datetime.datetime(2026, 11, d), "canal_chave": "kick:coringa",
               "arquivo": None, "titulo": str(d)} for d in (9, 3, 6)]
    liberados, _ = postagem.separar_pendentes(cortes, CARTEIRA, "youtube")
    assert [c["titulo"] for c in liberados] == ["3", "6", "9"]
