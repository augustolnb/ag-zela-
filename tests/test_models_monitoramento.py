from datetime import datetime

from zela.models.monitoramento import (
    EventoMonitoramento,
    FonteSensor,
    LeituraSensor,
    MetodoClassificacao,
    StatusMonitoramento,
    TipoLeitura,
)


def test_leitura_frequencia_cardiaca_plausivel():
    leitura = LeituraSensor(
        fonte=FonteSensor.SMARTWATCH,
        tipo=TipoLeitura.FREQUENCIA_CARDIACA,
        valor=72,
        unidade="bpm",
        timestamp=datetime(2026, 9, 13, 10, 0),
    )
    assert leitura.plausivel is True


def test_leitura_frequencia_cardiaca_implausivel_e_flagueada_nao_rejeitada():
    leitura = LeituraSensor(
        fonte=FonteSensor.SMARTWATCH,
        tipo=TipoLeitura.FREQUENCIA_CARDIACA,
        valor=300,
        unidade="bpm",
        timestamp=datetime(2026, 9, 13, 10, 0),
    )
    assert leitura.plausivel is False


def test_leitura_presenca_plausivel():
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=datetime(2026, 9, 13, 10, 0),
    )
    assert leitura.plausivel is True


def test_evento_monitoramento_valido():
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=datetime(2026, 9, 13, 10, 0),
    )
    evento = EventoMonitoramento(
        status=StatusMonitoramento.NORMAL,
        motivo="Nenhuma anomalia detectada",
        leituras_relacionadas=[leitura],
        timestamp=datetime(2026, 9, 13, 10, 0),
        metodo_classificacao=MetodoClassificacao.REGRA,
    )
    assert evento.status == StatusMonitoramento.NORMAL


def test_status_aviso_existe():
    assert StatusMonitoramento("aviso") is StatusMonitoramento.AVISO


def test_leitura_sinal_de_vida_plausivel():
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.SINAL_DE_VIDA,
        valor=1,
        unidade="sinal",
        timestamp=datetime(2026, 10, 29, 10, 0),
    )
    assert leitura.plausivel
