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
