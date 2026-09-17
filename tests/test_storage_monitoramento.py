from datetime import datetime, timedelta

from zela.models.monitoramento import (
    FonteSensor,
    StatusMonitoramento,
    TipoLeitura,
)
from zela.models.monitoramento import LeituraSensor
from zela.storage.db import conectar
from zela.storage.monitoramento import (
    aplicar_classificacao,
    listar_leituras_recentes,
    salvar_leitura,
)


def test_salvar_e_listar_leituras_recentes():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 10, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora,
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    leituras = listar_leituras_recentes(conn, "idosa-1", desde=agora - timedelta(hours=1))

    assert len(leituras) == 1
    assert leituras[0].tipo == TipoLeitura.PRESENCA
    assert leituras[0].fonte == FonteSensor.ESP32


def test_listar_leituras_recentes_exclui_leituras_antigas():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 10, 0)
    leitura_antiga = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora - timedelta(hours=30),
    )
    salvar_leitura(conn, leitura_antiga, idoso_id="idosa-1")

    leituras = listar_leituras_recentes(conn, "idosa-1", desde=agora - timedelta(hours=24))

    assert leituras == []


def test_aplicar_classificacao_risco_por_ausencia_de_presenca():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora - timedelta(hours=8),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    evento = aplicar_classificacao(conn, "idosa-1", agora)

    assert evento.status == StatusMonitoramento.RISCO


def test_aplicar_classificacao_normal_com_presenca_recente():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora - timedelta(minutes=30),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    evento = aplicar_classificacao(conn, "idosa-1", agora)

    assert evento.status == StatusMonitoramento.NORMAL


def test_aplicar_classificacao_sem_leituras_de_presenca_na_janela_e_atencao():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)
    # nenhuma leitura salva — simula ESP32 que nunca reportou ou parou há muito tempo

    evento = aplicar_classificacao(conn, "idosa-1", agora)

    assert evento.status == StatusMonitoramento.ATENCAO
    assert "sem" in evento.motivo.lower() or "nenhuma" in evento.motivo.lower()
