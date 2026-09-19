from datetime import datetime, time

from streamlit.testing.v1 import AppTest

from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura
from zela.models.rotina import CanalConfirmacao, ConfirmacaoMedicacao, Dosagem, Medicamento, StatusConfirmacao
from zela.storage.db import conectar
from zela.storage.monitoramento import salvar_leitura
from zela.storage.rotina import salvar_confirmacao, salvar_medicamento


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


def test_renderizar_medicacao_mostra_confirmacoes_do_dia(tmp_path):
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
    agora = datetime.now().replace(hour=8, minute=5, second=0, microsecond=0)
    salvar_confirmacao(
        conn,
        ConfirmacaoMedicacao(
            medicamento_id="med-1", horario_previsto=agora, horario_confirmado=agora,
            status=StatusConfirmacao.CONFIRMADO, canal=CanalConfirmacao.WHATSAPP,
        ),
    )

    codigo = f"""
from zela.storage.db import conectar
from zela.streamlit_app.secoes import renderizar_medicacao

conn = conectar({caminho!r})
renderizar_medicacao(conn, "idosa-1")
"""
    at = AppTest.from_string(codigo)
    at.run()

    assert at.exception == []
    textos = [m.value for m in at.markdown]
    assert any("Losartana" in t and "confirmado" in t for t in textos)


def test_renderizar_medicacao_sem_confirmacoes_mostra_mensagem(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conectar(caminho)  # garante que o schema existe

    codigo = f"""
from zela.storage.db import conectar
from zela.streamlit_app.secoes import renderizar_medicacao

conn = conectar({caminho!r})
renderizar_medicacao(conn, "idosa-1")
"""
    at = AppTest.from_string(codigo)
    at.run()

    assert at.exception == []
    assert any("Nenhum registro" in m.value for m in at.markdown)
