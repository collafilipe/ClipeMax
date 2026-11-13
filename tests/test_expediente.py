"""Diario do escritorio e expediente (ligar e desligar a vigia), sem iniciar processo de verdade."""
import datetime
import json
import sys

import pytest

import agencia
import esteira
import expediente

AGORA = datetime.datetime(2026, 11, 13, 15, 0)
CARTEIRA = agencia.interpretar_carteira("https://kick.com/coringa/videos | cliente=Coringa | funcionario=Arthur")


# ---------------------------------------------------------------------- diario

def test_evento_entra_no_diario_e_vira_o_fazendo_agora_da_pessoa(tmp_path):
    esteira.registrar_evento(tmp_path, "kick:coringa", "edicao", "renderizando o corte 1h02m03s (45s)", AGORA)
    esteira.registrar_evento(tmp_path, "empresa", "gerente", "Coringa: aprovou 1h02m03s com nota 8", AGORA)
    eventos = esteira.ler_eventos(tmp_path)
    quadro = esteira.quadro_do_escritorio([], CARTEIRA, esteira.EMPRESA_PADRAO,
                                          json.loads((tmp_path / "atividade.json").read_text(encoding="utf-8")), AGORA, eventos)
    pessoas = {p["papel"]: p for p in quadro["times"][0]["pessoas"]}
    assert pessoas["edicao"]["fazendo"] == "renderizando o corte 1h02m03s (45s)"
    assert pessoas["radar"]["fazendo"] == ""
    assert next(g for g in quadro["gestao"] if g["id"] == "gerente")["fazendo"] == "Coringa: aprovou 1h02m03s com nota 8"
    assert [e["quem"] for e in quadro["eventos"]] == [
        f"{esteira.nome_de_pessoa('kick:coringa', 'edicao')} · Edição · Coringa", "Gerente de conteúdo"]


def test_aviso_antigo_nao_conta_como_fazendo_agora(tmp_path):
    esteira.registrar_evento(tmp_path, "kick:coringa", "radar", "ouvindo a live", AGORA - datetime.timedelta(hours=2))
    atividade = json.loads((tmp_path / "atividade.json").read_text(encoding="utf-8"))
    quadro = esteira.quadro_do_escritorio([], CARTEIRA, esteira.EMPRESA_PADRAO, atividade, AGORA)
    assert quadro["times"][0]["pessoas"][0]["fazendo"] == ""


def test_marcar_situacao_do_time_nao_apaga_o_que_cada_pessoa_esta_fazendo(tmp_path):
    esteira.registrar_evento(tmp_path, "kick:coringa", "radar", "achou 2 momento(s)", AGORA)
    esteira.marcar_atividade(tmp_path / "atividade.json", "kick:coringa", "olhando a live", AGORA)
    do_canal = json.loads((tmp_path / "atividade.json").read_text(encoding="utf-8"))["kick:coringa"]
    assert do_canal["situacao"] == "olhando a live" and do_canal["papeis"]["radar"]["texto"] == "achou 2 momento(s)"


def test_diario_devolve_so_os_ultimos_e_ignora_linha_cortada(tmp_path):
    for i in range(50):
        esteira.registrar_evento(tmp_path, "empresa", "ceo", f"evento {i}", AGORA)
    with open(tmp_path / "eventos.jsonl", "a", encoding="utf-8") as f:
        f.write('{"quando": "2026')  # queda no meio da escrita
    eventos = esteira.ler_eventos(tmp_path, 10)
    assert [e["texto"] for e in eventos] == [f"evento {i}" for i in range(41, 50)]


def test_esteira_avisa_o_diario_de_cada_decisao_com_o_dono_certo(tmp_path):
    pastas = {"pendente": tmp_path / "prontos", "aprovado": tmp_path / "aprovados", "descartado": tmp_path / "descartados"}
    pasta = pastas["pendente"] / "coringa"
    pasta.mkdir(parents=True)
    (pasta / "a.json").write_text(json.dumps({"canal": "Coringa", "canal_chave": "kick:coringa", "duracao": 45, "titulo": "t",
                                              "fala": "f", "nota_ia": 8}), encoding="utf-8")
    (pasta / "a.mp4").write_bytes(b"v" * 500_000)
    avisos = []
    esteira.rodar(pastas, CARTEIRA, esteira.EMPRESA_PADRAO, None, None, AGORA, lambda m: None,
                  evento=lambda chave, papel, texto: avisos.append((chave, papel, texto.split(":")[0])))
    assert avisos == [("kick:coringa", "lider", "aprovou a"), ("empresa", "qualidade", "Coringa"),
                      ("empresa", "compliance", "Coringa"), ("empresa", "diretor", "Coringa")]


# ------------------------------------------------------------------ expediente

class Processo:
    pid = 4321


def test_abrir_o_expediente_inicia_a_vigia_com_a_carteira_e_as_opcoes_da_empresa(tmp_path):
    chamadas = []

    def popen(comando, **extras):
        chamadas.append(comando)
        return Processo()

    estado = expediente.abrir(tmp_path, '--jogo "gta 6" --por-hora 2', popen=popen, vivo=lambda pid: True)
    assert estado["rodando"] and estado["pid"] == 4321
    assert chamadas == [[sys.executable, str(tmp_path / "cortes.py"), "--vigiar", str(tmp_path / "canais.txt"),
                         "--jogo", "gta 6", "--por-hora", "2"]]
    assert expediente.situacao(tmp_path, vivo=lambda pid: True)["rodando"]


def test_abrir_duas_vezes_nao_inicia_duas_vigias(tmp_path):
    chamadas = []

    def popen(comando, **extras):
        chamadas.append(comando)
        return Processo()

    expediente.abrir(tmp_path, popen=popen, vivo=lambda pid: True)
    expediente.abrir(tmp_path, popen=popen, vivo=lambda pid: True)
    assert len(chamadas) == 1


def test_vigia_que_caiu_sozinha_aparece_como_expediente_fechado(tmp_path):
    expediente.abrir(tmp_path, popen=lambda c, **e: Processo(), vivo=lambda pid: True)
    assert expediente.situacao(tmp_path, vivo=lambda pid: False) == {"rodando": False, "desde": None, "pid": None}
    assert not (tmp_path / "estado" / "vigia.json").exists()


def test_fechar_o_expediente_encerra_o_processo_guardado(tmp_path):
    expediente.abrir(tmp_path, popen=lambda c, **e: Processo(), vivo=lambda pid: True)
    encerrados = []
    estado = expediente.fechar(tmp_path, encerrar=encerrados.append, vivo=lambda pid: True)
    assert encerrados == [4321] and not estado["rodando"]
    assert not expediente.situacao(tmp_path, vivo=lambda pid: True)["rodando"]


def test_fechar_sem_expediente_aberto_nao_tenta_encerrar_nada(tmp_path):
    encerrados = []
    expediente.fechar(tmp_path, encerrar=encerrados.append)
    assert encerrados == []


@pytest.mark.parametrize("conteudo", ["", "{", '{"pid": "abc"}', '{"desde": "x"}'])
def test_arquivo_de_estado_estragado_vale_como_expediente_fechado(tmp_path, conteudo):
    (tmp_path / "estado").mkdir()
    (tmp_path / "estado" / "vigia.json").write_text(conteudo, encoding="utf-8")
    assert not expediente.situacao(tmp_path, vivo=lambda pid: True)["rodando"]


def test_atendente_avulso_de_pedidos_nao_mexe_na_fila_nem_no_estado_da_vigia(tmp_path):
    import pedidos
    pedidos.adicionar(tmp_path / "estado", "https://www.twitch.tv/videos/1")
    chamadas = []

    def popen(comando, **extras):
        chamadas.append(comando)
        return Processo()

    expediente.abrir(tmp_path, popen=popen, vivo=lambda pid: True, nome="avulso")
    assert chamadas[0][2:] == ["--pedidos", "--carteira", str(tmp_path / "canais.txt")]
    assert pedidos.ha_pendentes(tmp_path / "estado")  # a fila continua inteira
    assert expediente.situacao(tmp_path, vivo=lambda pid: True, nome="avulso")["rodando"]
    assert not expediente.situacao(tmp_path, vivo=lambda pid: True)["rodando"]
