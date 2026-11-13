"""A esteira da empresa sem Claude e sem ffmpeg: a gerencia e uma funcao de teste que devolve pareceres prontos."""
import datetime
import json

import pytest

import agencia
import esteira

AGORA = datetime.datetime(2026, 11, 13, 15, 0)
CARTEIRA = agencia.interpretar_carteira(
    "https://kick.com/coringa/videos | cliente=Coringa | autorizado=sim | funcionario=Arthur\n"
    "https://kick.com/xqc/videos\n")
EMPRESA = {**esteira.EMPRESA_PADRAO, "cota_ceo_por_canal": 2}
VIDEO = b"v" * 500_000  # tamanho de um video de verdade para 45 s; menos que isso a qualidade acusa render quebrado


@pytest.fixture
def pastas(tmp_path):
    return {"pendente": tmp_path / "prontos", "aprovado": tmp_path / "aprovados", "descartado": tmp_path / "descartados"}


def _corte(pastas, nome, canal_chave="kick:coringa", video=VIDEO, situacao="pendente", **campos):
    pasta = pastas[situacao] / canal_chave.replace(":", "_")
    pasta.mkdir(parents=True, exist_ok=True)
    dados = {"canal": canal_chave.split(":")[1], "canal_chave": canal_chave, "titulo": "Titulo do time",
             "tiktok": "legenda", "shorts": "legenda #shorts", "duracao": 45.0, "nota_ia": 7, "fala": "olha isso",
             "enquadramento": "webcam + jogo", "criado_em": AGORA.isoformat(), **campos}
    (pasta / f"{nome}.json").write_text(json.dumps(dados), encoding="utf-8")
    if video is not None:
        (pasta / f"{nome}.mp4").write_bytes(video)
    return pasta / f"{nome}.json"


def _ler(arq):
    return json.loads(arq.read_text(encoding="utf-8"))


def _gerente(notas=None, **fixo):
    """Gerente de teste: aprova tudo com nota 8, salvo o que vier em notas={nome do corte: nota}."""
    def parecer(itens, canal):
        saida = {}
        for item in itens:
            nota = (notas or {}).get(item["id"].split("/")[-1], 8)
            saida[item["id"]] = {"nota": nota, "veredito": "aprovar" if nota >= 6 else "reprovar", "parecer": "ok",
                                 "melhoria": "abrir com a reacao", "titulo": item["titulo"],
                                 "legenda_tiktok": item["legenda_tiktok"], "legenda_shorts": item["legenda_shorts"], **fixo}
        return saida
    return parecer


def _rodar(pastas, gerente="padrao", empresa=EMPRESA, agora=AGORA):
    falas = []
    resumo = esteira.rodar(pastas, CARTEIRA, empresa, _gerente() if gerente == "padrao" else gerente, None, agora, falas.append)
    return resumo, "\n".join(falas)


def _vereditos(arq):
    return [(p["etapa"], p["veredito"]) for p in _ler(arq)["trilha"] if p["etapa"] != "producao"]


def _decididos(pastas, canal_chave, aprovados, reprovados):
    """Historico de decisoes do CEO sobre um canal, para o humor do time."""
    for i in range(aprovados + reprovados):
        veredito, situacao = ("aprovado", "aprovado") if i < aprovados else ("reprovado", "descartado")
        _corte(pastas, f"h{i}", canal_chave, situacao=situacao, etapa=situacao,
               trilha=[{"etapa": "ceo", "veredito": veredito, "quando": f"2026-11-0{1 + i % 9}T10:00:00"}])


# ------------------------------------------------------------- caminho completo

def test_corte_bom_passa_por_toda_a_cadeia_de_gestores_ate_a_fila_do_ceo(pastas):
    arq = _corte(pastas, "a")
    resumo, _ = _rodar(pastas)
    assert _ler(arq)["etapa"] == "ceo"
    assert _vereditos(arq) == [("lider_time", "aprovado"), ("qualidade", "aprovado"), ("compliance", "aprovado"),
                               ("gerente", "aprovado"), ("diretor", "promovido")]
    assert resumo["subiram_ao_ceo"] == 1 and resumo["aguardando_ceo"] == 1


def test_trilha_comeca_com_o_que_cada_pessoa_do_time_fez(pastas):
    arq = _corte(pastas, "a", sinais="chat 3.0x a media da live", motivo="reacao forte")
    _rodar(pastas)
    producao = [p for p in _ler(arq)["trilha"] if p["etapa"] == "producao"]
    assert [p["quem"].split("(")[1] for p in producao] == ["Radar)", "Edição)", "Redação)"]
    assert producao[0]["parecer"] == "chat 3.0x a media da live"
    assert producao[1]["parecer"] == "webcam + jogo, 45s, com legenda"
    assert producao[2]["parecer"] == "nota 7: reacao forte"
    # o lider do time e o nome dado no canais.txt
    assert _ler(arq)["trilha"][3]["quem"] == "Arthur (Líder do time)"


def test_rodar_a_esteira_de_novo_nao_repete_pareceres(pastas):
    arq = _corte(pastas, "a")
    _rodar(pastas)
    resumo, falas = _rodar(pastas)
    assert len(_ler(arq)["trilha"]) == 8  # 3 da producao + 5 da cadeia
    assert resumo["subiram_ao_ceo"] == 0 and falas == ""


def test_corte_parado_numa_etapa_da_esteira_antiga_continua_de_onde_estava(pastas):
    arq = _corte(pastas, "a", etapa="gestor", trilha=[{"etapa": "revisor", "veredito": "aprovado"}])
    _rodar(pastas)
    assert _ler(arq)["etapa"] == "ceo"
    assert [e for e, _ in _vereditos(arq)] == ["revisor", "gerente", "diretor"]


# -------------------------------------------------- cada etapa barra so o que e dela

@pytest.mark.parametrize("campos, etapa, trecho", [
    ({"nota_ia": 3}, "lider_time", "abaixo da mínima de 5"),
    ({"duracao": 5}, "qualidade", "abaixo do mínimo"),
    ({"duracao": 75}, "qualidade", "acima do máximo"),
    ({"musica": "destaque", "musica_pct": 90}, "compliance", "música em destaque"),
    ({"cutscene": True}, "compliance", "spoiler"),
])
def test_cada_etapa_barra_so_o_que_e_do_seu_dominio_e_diz_o_que_melhorar(pastas, campos, etapa, trecho):
    arq = _corte(pastas, "a", **campos)
    resumo, _ = _rodar(pastas)
    barrado = pastas["descartado"] / "kick_coringa" / "a.json"
    assert resumo[f"{etapa}_barrou"] == 1 and not arq.exists()
    assert (pastas["descartado"] / "kick_coringa" / "a.mp4").exists()
    ultimo = _ler(barrado)["trilha"][-1]
    assert (ultimo["etapa"], ultimo["veredito"]) == (etapa, "reprovado")
    assert trecho in ultimo["parecer"] and ultimo["melhoria"]
    assert _ler(barrado)["etapa"] == "descartado"


def test_lider_barra_corte_sem_video_e_qualidade_barra_render_quebrado(pastas):
    sem_video, quebrado = _corte(pastas, "sem", video=None), _corte(pastas, "quebrado", video=b"x" * 2000)
    resumo, _ = _rodar(pastas)
    assert (resumo["lider_time_barrou"], resumo["qualidade_barrou"]) == (1, 1)
    assert not sem_video.exists() and not quebrado.exists()


def test_avisos_nao_barram_mas_chegam_ao_ceo_com_o_que_melhorar(pastas):
    arq = _corte(pastas, "a", "kick:xqc", musica="fundo", ofensas=2, titulo="", fala="", enquadramento="fundo desfocado")
    _rodar(pastas)
    pareceres = {p["etapa"]: p for p in _ler(arq)["trilha"]}
    assert _ler(arq)["etapa"] == "ceo"
    assert "Redação: o corte subiu sem título" in pareceres["lider_time"]["melhoria"]
    assert "fundo desfocado" in pareceres["qualidade"]["parecer"] and "webcam" in pareceres["qualidade"]["melhoria"]
    assert all(t in pareceres["compliance"]["parecer"] for t in ("sem autorização", "música de fundo", "xingamento"))


def test_compliance_nao_avisa_autorizacao_quando_o_canal_tem(pastas):
    arq = _corte(pastas, "a", "kick:coringa")
    _rodar(pastas)
    assert next(p for p in _ler(arq)["trilha"] if p["etapa"] == "compliance")["parecer"] == "liberado"


def test_corte_que_nao_pode_ser_movido_fica_inteiro_onde_estava_e_a_esteira_segue(pastas, monkeypatch):
    preso, outro = _corte(pastas, "preso", cutscene=True), _corte(pastas, "outro")
    original = esteira.os.replace

    def mover(origem, destino):
        if "descartados" in str(destino) and str(destino).endswith("preso.json"):
            raise OSError("caminho longo demais")
        return original(origem, destino)

    monkeypatch.setattr(esteira.os, "replace", mover)
    resumo, falas = _rodar(pastas)
    # video e dados continuam juntos na pasta de pendentes, parados na etapa que tentou barrar
    assert preso.exists() and preso.with_suffix(".mp4").exists()
    assert not (pastas["descartado"] / "kick_coringa" / "preso.mp4").exists()
    assert _ler(preso)["etapa"] == "compliance"
    assert resumo["compliance_barrou"] == 0 and "nao consegui mover" in falas
    assert _ler(outro)["etapa"] == "ceo"


# --------------------------------------------------------------------- gerente

def test_gerente_barra_corte_com_nota_abaixo_da_minima_e_devolve_o_que_melhorar(pastas):
    fraco, bom = _corte(pastas, "fraco"), _corte(pastas, "bom")
    resumo, falas = _rodar(pastas, _gerente({"fraco": 3}))
    barrado = _ler(pastas["descartado"] / "kick_coringa" / "fraco.json")
    assert resumo["gerente_barrou"] == 1 and not fraco.exists() and bom.exists()
    assert barrado["nota_gestor"] == 3 and barrado["trilha"][-1]["melhoria"] == "abrir com a reacao"
    assert "gerência barrou kick_coringa/fraco (nota 3)" in falas


def test_gerente_reescreve_o_titulo_e_guarda_o_original_para_o_ceo_comparar(pastas):
    arq = _corte(pastas, "a")
    _rodar(pastas, _gerente(titulo="Titulo melhor"))
    assert _ler(arq)["titulo"] == "Titulo melhor"
    assert _ler(arq)["antes_do_gestor"] == {"titulo": "Titulo do time"}


def test_quando_a_ia_falha_os_cortes_esperam_na_gerencia_em_vez_de_subir_sem_parecer(pastas):
    arq = _corte(pastas, "a")

    def quebrado(itens, canal):
        raise RuntimeError("limite do plano")

    resumo, falas = _rodar(pastas, quebrado)
    assert _ler(arq)["etapa"] == "gerente" and resumo["subiram_ao_ceo"] == 0
    assert "tento na proxima rodada" in falas
    _rodar(pastas)  # na rodada seguinte a IA voltou
    assert _ler(arq)["etapa"] == "ceo"


def test_sem_ia_instalada_o_corte_sobe_marcado_como_sem_parecer(pastas):
    arq = _corte(pastas, "a")
    _rodar(pastas, gerente=None)
    assert _ler(arq)["etapa"] == "ceo"
    assert ("gerente", "ausente") in _vereditos(arq)


def test_gerente_recebe_os_cortes_por_canal_com_os_avisos_de_qualidade_e_compliance(pastas):
    _corte(pastas, "a", "kick:coringa")
    _corte(pastas, "b", "kick:xqc", musica="fundo")
    _corte(pastas, "c", "kick:coringa")
    lotes = {}

    def anotar(itens, canal):
        lotes[canal] = itens
        return _gerente()(itens, canal)

    _rodar(pastas, anotar)
    assert sorted(i["id"].split("/")[-1] for i in lotes["coringa"]) == ["a", "c"]
    assert "música de fundo" in lotes["xqc"][0]["avisos_do_revisor"]


def test_gerente_nao_recebe_o_aviso_de_autorizacao_que_e_assunto_do_compliance(pastas):
    _corte(pastas, "a", "kick:xqc", musica="fundo")  # canal sem autorizacao e com musica de fundo
    _corte(pastas, "b", "kick:xqc")                  # so sem autorizacao
    recebidos = {}

    def anotar(itens, canal):
        recebidos.update({i["id"].split("/")[-1]: i["avisos_do_revisor"] for i in itens})
        return _gerente()(itens, canal)

    _rodar(pastas, anotar)
    assert "autorização" not in recebidos["a"] and "música de fundo" in recebidos["a"]
    assert recebidos["b"] == "vídeo dentro do padrão; liberado"
    # o CEO continua vendo o aviso na trilha
    compliance = next(p for p in _ler(pastas["pendente"] / "kick_xqc" / "b.json")["trilha"] if p["etapa"] == "compliance")
    assert "sem autorização" in compliance["parecer"]


# --------------------------------------------------------------------- diretor

def test_diretor_so_manda_ao_ceo_os_melhores_do_canal_e_deixa_o_resto_na_reserva(pastas):
    arqs = {n: _corte(pastas, n) for n in ("a", "b", "c")}
    resumo, falas = _rodar(pastas, _gerente({"a": 7, "b": 9, "c": 8}))
    assert {n: _ler(a)["etapa"] for n, a in arqs.items()} == {"a": "diretor", "b": "ceo", "c": "ceo"}
    assert resumo["na_reserva"] == 1 and "1 corte(s) na reserva" in falas
    assert "1º melhor do canal hoje" in _ler(arqs["b"])["trilha"][-1]["parecer"]


def test_cota_do_ceo_e_por_dia_e_conta_o_que_ele_ja_decidiu(pastas):
    arqs = {n: _corte(pastas, n) for n in ("a", "b", "c")}
    _rodar(pastas, _gerente({"a": 7, "b": 9, "c": 8}))
    # o CEO aprova um: sai da pasta de pendentes, mas continua contando na cota de hoje
    destino = pastas["aprovado"] / "kick_coringa"
    destino.mkdir(parents=True)
    arqs["b"].rename(destino / "b.json")
    _rodar(pastas)
    assert _ler(arqs["a"])["etapa"] == "diretor"
    # no dia seguinte a cota renova e o corte da reserva sobe
    _rodar(pastas, agora=AGORA + datetime.timedelta(days=1))
    assert _ler(arqs["a"])["etapa"] == "ceo"


def test_cota_e_separada_por_canal(pastas):
    for n in ("a", "b", "c"):
        _corte(pastas, n, "kick:coringa")
    outro = _corte(pastas, "d", "kick:xqc")
    _rodar(pastas)
    assert _ler(outro)["etapa"] == "ceo"


# ----------------------------------------------------------------------- humor

@pytest.mark.parametrize("aprovados, reprovados, nivel", [
    (0, 0, "normal"), (4, 0, "normal"),  # menos de 5 decisoes: ainda nao da para dizer nada
    (8, 2, "animado"), (5, 5, "normal"), (3, 7, "cauteloso"), (1, 9, "pressao"),
])
def test_humor_do_time_sai_da_taxa_de_aprovacao_do_ceo(aprovados, reprovados, nivel):
    cortes = [{"trilha": [{"etapa": "ceo", "veredito": v, "quando": f"2026-11-01T10:{i:02d}:00"}]}
              for i, v in enumerate(["aprovado"] * aprovados + ["reprovado"] * reprovados)]
    assert esteira.humor_do_time(cortes)["nivel"] == nivel


def test_humor_olha_so_as_ultimas_decisoes(pastas):
    antigas = [{"trilha": [{"etapa": "ceo", "veredito": "reprovado", "quando": f"2026-10-01T10:{i:02d}:00"}]} for i in range(10)]
    recentes = [{"trilha": [{"etapa": "ceo", "veredito": "aprovado", "quando": f"2026-11-01T10:{i:02d}:00"}]} for i in range(10)]
    assert esteira.humor_do_time(antigas + recentes)["nivel"] == "animado"


def test_time_sob_pressao_fica_mais_exigente_e_barra_o_que_antes_passava(pastas):
    arq = _corte(pastas, "a", nota_ia=6)
    _decididos(pastas, "kick:coringa", aprovados=1, reprovados=9)
    resumo, _ = _rodar(pastas)
    assert resumo["lider_time_barrou"] == 1 and not arq.exists()
    parecer = _ler(pastas["descartado"] / "kick_coringa" / "a.json")["trilha"][-1]["parecer"]
    assert "abaixo da mínima de 7 (time sob pressão)" in parecer


def test_time_animado_ganha_vaga_na_pauta_e_time_sob_pressao_perde(pastas):
    _decididos(pastas, "kick:coringa", aprovados=9, reprovados=1)
    _decididos(pastas, "kick:xqc", aprovados=0, reprovados=9)
    bons = [_corte(pastas, n, "kick:coringa", nota_ia=9) for n in ("a", "b", "c", "d")]
    ruins = [_corte(pastas, n, "kick:xqc", nota_ia=9) for n in ("e", "f")]
    _rodar(pastas)  # cota base 2: animado sobe 3, sob pressao sobe 1
    assert sorted(_ler(a)["etapa"] for a in bons) == ["ceo", "ceo", "ceo", "diretor"]
    assert sorted(_ler(a)["etapa"] for a in ruins) == ["ceo", "diretor"]


# ------------------------------------------------------------------ ceo e empresa

def test_decisao_do_ceo_entra_na_trilha_e_resgate_volta_para_a_fila_dele():
    dados = esteira.decisao_do_ceo({"trilha": []}, "descartar", agora=AGORA)
    assert (dados["etapa"], dados["trilha"][-1]["veredito"]) == ("descartado", "reprovado")
    dados = esteira.decisao_do_ceo(dados, "restaurar", agora=AGORA)
    assert (dados["etapa"], dados["trilha"][-1]["veredito"]) == ("ceo", "resgatado")


def test_empresa_json_troca_so_o_que_traz_e_recusa_opcao_desconhecida(tmp_path):
    arq = tmp_path / "empresa.json"
    assert esteira.carregar_empresa(arq) == esteira.EMPRESA_PADRAO
    arq.write_text(json.dumps({"gerente": "Gustavo", "cota_ceo_por_canal": 3}), encoding="utf-8")
    empresa = esteira.carregar_empresa(arq)
    assert (empresa["gerente"], empresa["cota_ceo_por_canal"], empresa["diretor"]) == ("Gustavo", 3, "Diretor editorial")
    arq.write_text(json.dumps({"cota": 3}), encoding="utf-8")
    with pytest.raises(ValueError, match="opcao desconhecida"):
        esteira.carregar_empresa(arq)


def test_cada_time_tem_sempre_as_mesmas_quatro_pessoas():
    time = esteira.pessoas_do_time("kick:coringa", "Arthur")
    assert [p["cargo"] for p in time] == ["Radar", "Edição", "Redação", "Líder do time"]
    assert time[-1]["nome"] == "Arthur"
    assert time == esteira.pessoas_do_time("kick:coringa", "Arthur")
    assert esteira.pessoas_do_time("kick:xqc")[-1]["nome"] in esteira._NOMES


# ------------------------------------------------------------------- avaliacao

def _historico(canal_chave, *vereditos):
    return {"canal_chave": canal_chave, "trilha": [{"etapa": e, "veredito": v} for e, v in vereditos]}


def test_avaliacao_mede_times_e_gerencia_pelas_decisoes_do_ceo():
    cortes = [
        _historico("kick:coringa", ("lider_time", "aprovado"), ("gerente", "aprovado"), ("ceo", "aprovado")),
        _historico("kick:coringa", ("lider_time", "aprovado"), ("gerente", "aprovado"), ("ceo", "reprovado")),
        _historico("kick:coringa", ("lider_time", "reprovado")),
        _historico("kick:coringa", ("compliance", "reprovado")),
        _historico("kick:coringa", ("gerente", "reprovado"), ("ceo", "resgatado"), ("ceo", "aprovado")),
        _historico("kick:xqc", ("lider_time", "aprovado"), ("gerente", "aprovado")),
    ]
    linhas, gerente = esteira.avaliacao(cortes, CARTEIRA)
    coringa = next(l for l in linhas if l["time"] == "Coringa")
    assert (coringa["produzidos"], coringa["barrados_lider_time"], coringa["barrados_compliance"],
            coringa["barrados_gerente"]) == (5, 1, 1, 1)
    assert (coringa["aprovados_ceo"], coringa["reprovados_ceo"]) == (2, 1)
    assert coringa["aprovacao_ceo"] == pytest.approx(2 / 3)
    assert next(l for l in linhas if l["time"] == "kick:xqc")["aprovacao_ceo"] is None
    assert gerente == {"julgados_pelo_ceo": 2, "acerto": 0.5, "barrados_que_o_ceo_resgatou": 1}
    assert "ainda nao dizem muita coisa" in esteira.texto_da_avaliacao(linhas, gerente)


# ------------------------------------------------------------------ escritorio

def test_escritorio_mostra_times_gestao_filas_humor_e_feedback(pastas, tmp_path):
    for n in ("a", "b", "c"):
        _corte(pastas, n)
    _rodar(pastas)  # cota 2: dois sobem ao CEO, um fica na reserva do diretor
    _corte(pastas, "chegou_depois")
    atividade = tmp_path / "estado" / "atividade.json"
    esteira.marcar_atividade(atividade, "kick:coringa", "olhando a live", AGORA)
    esteira.marcar_atividade(atividade, "kick:xqc", "olhando a live", AGORA - datetime.timedelta(hours=2))
    quadro = esteira.quadro_do_escritorio(agencia.ler_cortes(pastas), CARTEIRA, EMPRESA,
                                          json.loads(atividade.read_text(encoding="utf-8")), AGORA)
    assert quadro["ceo"]["fila"] == 2
    assert {g["id"]: g["fila"] for g in quadro["gestao"]} == {"qualidade": 0, "compliance": 0, "gerente": 0, "diretor": 1}
    coringa, xqc = quadro["times"]
    assert (coringa["situacao"], coringa["ligado"], coringa["feitos_hoje"], coringa["fila"]) == ("olhando a live", True, 4, 1)
    assert [p["cargo"] for p in coringa["pessoas"]] == ["Radar", "Edição", "Redação", "Líder do time"]
    assert coringa["humor"]["nivel"] == "normal" and coringa["feedback"][-1]["texto"] == "abrir com a reacao"
    assert (xqc["situacao"], xqc["ligado"], xqc["autorizado"]) == ("vigia desligada", False, False)
    assert [e["id"] for e in quadro["etapas"]] == list(esteira.ETAPAS)
    etapas = {c["id"].split("/")[-1]: c["etapa"] for c in quadro["cortes"]}
    assert etapas == {"a": "ceo", "b": "ceo", "c": "diretor", "chegou_depois": "lider_time"}
    assert quadro["ticker"][0] == {"texto": "2 NA MESA DO CEO", "tom": "baixa"}
