import subprocess

import aviso


def test_texto_dos_cortes_concorda_com_a_quantidade():
    assert aviso.texto_dos_cortes(1, 4)[0] == "1 corte novo para aprovar"
    titulo, texto = aviso.texto_dos_cortes(3, 9)
    assert titulo == "3 cortes novos para aprovar" and texto.startswith("9 aguardando")


def test_montar_escapa_o_texto_e_poe_o_link():
    xml = aviso.montar('Corte "A" <b> & cia', "R$ 5 > 3", "http://127.0.0.1:8765/?a=1&b=2")
    assert "<b>" not in xml and "&lt;b&gt; &amp; cia" in xml and "R$ 5 &gt; 3" in xml
    assert 'activationType="protocol" launch="http://127.0.0.1:8765/?a=1&amp;b=2"' in xml
    assert "launch=" not in aviso.montar("a", "b")


def test_avisar_passa_o_texto_por_variavel_de_ambiente():
    chamadas = []

    def rodar(cmd, **kw):
        chamadas.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0)

    assert aviso.avisar("Titulo $x", "texto", rodar=rodar, plataforma="win32") is True
    cmd, kw = chamadas[0]
    assert "Titulo" not in " ".join(cmd) and "Titulo $x" in kw["env"]["CLIPEMAX_AVISO"]


def test_avisar_nunca_derruba_quem_chamou():
    def quebrado(cmd, **kw):
        raise OSError("sem powershell")

    assert aviso.avisar("a", "b", rodar=quebrado, plataforma="win32") is False
    assert aviso.avisar("a", "b", rodar=quebrado, plataforma="linux") is False
