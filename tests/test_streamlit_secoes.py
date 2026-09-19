from datetime import datetime

from streamlit.testing.v1 import AppTest

from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura
from zela.storage.db import conectar
from zela.storage.monitoramento import salvar_leitura


def test_renderizar_status_mostra_classificacao_normal(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conn = conectar(caminho)
    salvar_leitura(
        conn,
        LeituraSensor(
            fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA,
            valor=1, unidade="bool", timestamp=datetime.now(),
        ),
        idoso_id="idosa-1",
    )

    codigo = f"""
from zela.storage.db import conectar
from zela.streamlit_app.secoes import renderizar_status

conn = conectar({caminho!r})
renderizar_status(conn, "idosa-1")
"""
    at = AppTest.from_string(codigo)
    at.run()

    assert at.exception == []
    assert [m.value for m in at.metric] == ["NORMAL"]
