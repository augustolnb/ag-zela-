from datetime import time

from streamlit.testing.v1 import AppTest

from zela.models.rotina import Dosagem, Medicamento
from zela.storage.db import conectar
from zela.storage.rotina import listar_medicamentos, salvar_medicamento

_CODIGO_MEDICAMENTO = """
from zela.storage.db import conectar
from zela.streamlit_app.formularios import formulario_medicamento

conn = conectar({caminho!r})
formulario_medicamento(conn, "idosa-1")
"""


def test_formulario_medicamento_cria_novo(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conectar(caminho)  # garante que o schema existe

    at = AppTest.from_string(_CODIGO_MEDICAMENTO.format(caminho=caminho))
    at.run()

    at.text_input[0].set_value("Losartana")
    at.number_input[0].set_value(50.0)
    at.text_input[1].set_value("mg")
    at.time_input[0].set_value(time(8, 0))
    at.multiselect[0].set_value([0, 1, 2, 3, 4])
    at.button[0].click().run()

    assert at.exception == []
    medicamentos = listar_medicamentos(conectar(caminho), "idosa-1")
    assert len(medicamentos) == 1
    assert medicamentos[0].nome == "Losartana"
    assert medicamentos[0].dosagem.quantidade == 50.0
    assert medicamentos[0].dosagem.unidade == "mg"
    assert medicamentos[0].dias_semana == [0, 1, 2, 3, 4]


def test_formulario_medicamento_edita_existente(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conn = conectar(caminho)
    salvar_medicamento(
        conn,
        Medicamento(
            id="med-1", nome="Losartana",
            dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
        ),
        idoso_id="idosa-1",
    )

    at = AppTest.from_string(_CODIGO_MEDICAMENTO.format(caminho=caminho))
    at.run()

    at.selectbox[0].set_value("Losartana").run()
    at.number_input[0].set_value(100.0)
    at.button[0].click().run()

    assert at.exception == []
    medicamentos = listar_medicamentos(conectar(caminho), "idosa-1")
    assert len(medicamentos) == 1
    assert medicamentos[0].id == "med-1"
    assert medicamentos[0].dosagem.quantidade == 100.0


def test_formulario_medicamento_erro_de_validacao_e_exibido(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conectar(caminho)

    at = AppTest.from_string(_CODIGO_MEDICAMENTO.format(caminho=caminho))
    at.run()

    # Dosagem.quantidade exige > 0 (Field(gt=0), em zela/models/rotina.py) —
    # mas o widget st.number_input(min_value=0.0) aceita 0.0 normalmente
    # (min_value é inclusivo), então 0.0 chega até o Medicamento(...) e é
    # rejeitado ali por um ValueError real do Pydantic, não simulado.
    at.text_input[0].set_value("Losartana")
    at.number_input[0].set_value(0.0)
    at.text_input[1].set_value("mg")
    at.button[0].click().run()

    assert at.exception == []
    assert len(at.error) >= 1
    medicamentos = listar_medicamentos(conectar(caminho), "idosa-1")
    assert medicamentos == []
