from datetime import datetime, timedelta

from zela.models.monitoramento import (
    FonteSensor,
    StatusMonitoramento,
    TipoLeitura,
)
from zela.models.monitoramento import LeituraSensor
from zela.domain.monitoramento import MOTIVO_SEM_NENHUMA_FONTE
from zela.storage.db import conectar
from zela.storage.monitoramento import (
    aplicar_classificacao,
    avaliar_sono_recente,
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
        unidade="deteccao", timestamp=agora - timedelta(minutes=5),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")
    fc = LeituraSensor(
        fonte=FonteSensor.SMARTWATCH, tipo=TipoLeitura.FREQUENCIA_CARDIACA, valor=70,
        unidade="bpm", timestamp=agora - timedelta(minutes=5),
    )
    salvar_leitura(conn, fc, idoso_id="idosa-1")

    evento = aplicar_classificacao(conn, "idosa-1", agora)

    assert evento.status == StatusMonitoramento.NORMAL


def test_aplicar_classificacao_sem_nenhuma_leitura_e_risco():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)

    evento = aplicar_classificacao(conn, "idosa-1", agora)

    assert evento.status == StatusMonitoramento.RISCO
    assert evento.motivo == MOTIVO_SEM_NENHUMA_FONTE


def test_avaliar_sono_recente_considera_15_dias():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 9, 0)
    for dias in range(1, 15):
        leitura = LeituraSensor(
            fonte=FonteSensor.SMARTWATCH, tipo=TipoLeitura.SONO, valor=7,
            unidade="horas", timestamp=(agora - timedelta(days=dias)).replace(hour=7),
        )
        salvar_leitura(conn, leitura, idoso_id="idosa-1")
    noite = LeituraSensor(
        fonte=FonteSensor.SMARTWATCH, tipo=TipoLeitura.SONO, valor=4,
        unidade="horas", timestamp=agora.replace(hour=7),
    )
    salvar_leitura(conn, noite, idoso_id="idosa-1")

    evento = avaliar_sono_recente(conn, "idosa-1", agora)

    assert evento.status == StatusMonitoramento.AVISO


def test_listar_leituras_recentes_isola_por_idoso():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 10, 0)
    leitura_outra_idosa = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora,
    )
    salvar_leitura(conn, leitura_outra_idosa, idoso_id="idosa-2")

    leituras = listar_leituras_recentes(conn, "idosa-1", desde=agora - timedelta(hours=1))

    assert leituras == []


def test_aplicar_classificacao_ignora_leituras_de_outro_idoso():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)
    leitura_outra_idosa = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora,  # presença recente, mas de outra idosa
    )
    salvar_leitura(conn, leitura_outra_idosa, idoso_id="idosa-2")

    evento = aplicar_classificacao(conn, "idosa-1", agora)

    # idosa-1 não tem nenhuma leitura própria -> as duas fontes contam como silenciosas
    assert evento.status == StatusMonitoramento.RISCO
