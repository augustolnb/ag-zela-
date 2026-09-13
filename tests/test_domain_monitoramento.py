from datetime import datetime, timedelta

from zela.domain.monitoramento import classificar_por_regra
from zela.models.monitoramento import FonteSensor, StatusMonitoramento, TipoLeitura
from zela.models.monitoramento import LeituraSensor


def test_classifica_normal_sem_leituras():
    agora = datetime(2026, 9, 13, 14, 0)
    evento = classificar_por_regra([], agora)
    assert evento.status == StatusMonitoramento.NORMAL


def test_classifica_risco_por_ausencia_de_presenca():
    agora = datetime(2026, 9, 13, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=agora - timedelta(hours=8),
    )
    evento = classificar_por_regra([leitura], agora)
    assert evento.status == StatusMonitoramento.RISCO
    assert "8.0h" in evento.motivo or "8h" in evento.motivo


def test_classifica_normal_com_presenca_recente():
    agora = datetime(2026, 9, 13, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=agora - timedelta(minutes=30),
    )
    evento = classificar_por_regra([leitura], agora)
    assert evento.status == StatusMonitoramento.NORMAL


def test_classifica_atencao_por_frequencia_cardiaca_implausivel():
    agora = datetime(2026, 9, 13, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.SMARTWATCH,
        tipo=TipoLeitura.FREQUENCIA_CARDIACA,
        valor=250,
        unidade="bpm",
        timestamp=agora,
    )
    evento = classificar_por_regra([leitura], agora)
    assert evento.status == StatusMonitoramento.ATENCAO
