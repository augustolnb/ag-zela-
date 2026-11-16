import pytest
from streamlit.testing.v1 import AppTest

from zela.streamlit_app.estilo import aplicar_estilo, badge_nivel, icone


@pytest.mark.parametrize(
    "nivel,classe,rotulo",
    [
        ("info", "zela-badge-info", "INFO"),
        ("atencao", "zela-badge-atencao", "ATENÇÃO"),
        ("critico", "zela-badge-critico", "CRÍTICO"),
    ],
)
def test_badge_nivel_retorna_html_com_classe_e_rotulo(nivel, classe, rotulo):
    html = badge_nivel(nivel)

    assert classe in html
    assert rotulo in html


@pytest.mark.parametrize("nome", ["heart-pulse", "pill", "bell", "activity"])
def test_icone_retorna_svg_com_traco_fino(nome):
    svg = icone(nome)

    assert svg.startswith("<svg")
    assert 'stroke-width="1.5"' in svg


def test_aplicar_estilo_injeta_css_sem_erro():
    codigo = """
from zela.streamlit_app.estilo import aplicar_estilo

aplicar_estilo()
"""
    at = AppTest.from_string(codigo)
    at.run()

    assert at.exception == []
    assert any("<style>" in m.value for m in at.markdown)



# Modo noturno: azul escuro, letras brancas, detalhes amarelos.
def _css_injetado(codigo):
    at = AppTest.from_string(codigo)
    at.run()
    assert at.exception == []
    return "".join(m.value for m in at.markdown if "<style>" in m.value)


def test_modo_noturno_usa_azul_escuro_branco_e_amarelo():
    from zela.streamlit_app.estilo import AMARELO_DESTAQUE, AZUL_NOTURNO, BRANCO

    assert (AZUL_NOTURNO, BRANCO, AMARELO_DESTAQUE) == ("#0B1F3A", "#FFFFFF", "#FFD60A")
    css = _css_injetado("from zela.streamlit_app.estilo import aplicar_estilo\naplicar_estilo(noturno=True)\n")
    assert "#0B1F3A" in css and "#FFFFFF" in css and "#FFD60A" in css


def test_modo_diurno_nao_injeta_a_paleta_noturna():
    css = _css_injetado("from zela.streamlit_app.estilo import aplicar_estilo\naplicar_estilo()\n")
    assert "#0B1F3A" not in css
