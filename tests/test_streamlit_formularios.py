from datetime import date, datetime, time, timedelta

from streamlit.testing.v1 import AppTest

from zela.models.rotina import Compromisso, Dosagem, Medicamento, TipoCompromisso
from zela.storage.db import conectar
from zela.storage.rotina import (
    listar_compromissos,
    listar_medicamentos,
    salvar_compromisso,
    salvar_medicamento,
)

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


def test_formulario_medicamento_avisa_sobre_multiplos_horarios(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conn = conectar(caminho)
    salvar_medicamento(
        conn,
        Medicamento(
            id="med-1", nome="Losartana",
            dosagem=Dosagem(quantidade=50, unidade="mg"),
            horarios=[time(8, 0), time(20, 0)],
        ),
        idoso_id="idosa-1",
    )

    at = AppTest.from_string(_CODIGO_MEDICAMENTO.format(caminho=caminho))
    at.run()

    at.selectbox[0].set_value("Losartana").run()

    assert at.exception == []
    assert any("mais de um horário" in aviso.value for aviso in at.warning)


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


_CODIGO_COMPROMISSO = """
from zela.storage.db import conectar
from zela.streamlit_app.formularios import formulario_compromisso

conn = conectar({caminho!r})
formulario_compromisso(conn, "idosa-1")
"""


def test_formulario_compromisso_cria_novo(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conectar(caminho)

    at = AppTest.from_string(_CODIGO_COMPROMISSO.format(caminho=caminho))
    at.run()

    at.text_input[0].set_value("Consulta cardiologista")
    amanha = date.today() + timedelta(days=1)
    at.date_input[0].set_value(amanha)
    at.time_input[0].set_value(datetime.now().time().replace(second=0, microsecond=0))
    at.text_input[1].set_value("Clínica Central")
    at.selectbox[1].set_value(TipoCompromisso.CONSULTA)
    at.button[0].click().run()

    assert at.exception == []
    compromissos = listar_compromissos(conectar(caminho), "idosa-1")
    assert len(compromissos) == 1
    assert compromissos[0].titulo == "Consulta cardiologista"
    assert compromissos[0].tipo == TipoCompromisso.CONSULTA
    assert compromissos[0].local == "Clínica Central"
    assert compromissos[0].data_hora.date() == amanha


def test_formulario_compromisso_edita_existente(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conn = conectar(caminho)
    salvar_compromisso(
        conn,
        Compromisso(
            id="comp-1", titulo="Exame", data_hora=datetime.now() + timedelta(days=1),
            local="Laboratório X", tipo=TipoCompromisso.EXAME,
        ),
        idoso_id="idosa-1",
    )

    at = AppTest.from_string(_CODIGO_COMPROMISSO.format(caminho=caminho))
    at.run()

    at.selectbox[0].set_value("Exame").run()
    at.text_input[1].set_value("Laboratório Y")
    at.button[0].click().run()

    assert at.exception == []
    compromissos = listar_compromissos(conectar(caminho), "idosa-1")
    assert len(compromissos) == 1
    assert compromissos[0].id == "comp-1"
    assert compromissos[0].local == "Laboratório Y"
