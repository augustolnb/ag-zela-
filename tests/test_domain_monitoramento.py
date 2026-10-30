from datetime import datetime, timedelta, timezone

from zela.domain.monitoramento import (
    MOTIVO_ESP32_SEM_SINAL,
    MOTIVO_PULSEIRA_SEM_DADOS,
    MOTIVO_SEM_NENHUMA_FONTE,
    classificar_por_regra,
)
from zela.models.monitoramento import FonteSensor, LeituraSensor, StatusMonitoramento, TipoLeitura

AGORA = datetime(2026, 10, 29, 14, 0)


def esp(min_atras, tipo=TipoLeitura.SINAL_DE_VIDA):
    return LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=tipo,
        valor=1,
        unidade="sinal" if tipo == TipoLeitura.SINAL_DE_VIDA else "deteccao",
        timestamp=AGORA - timedelta(minutes=min_atras),
    )


def fc(min_atras, bpm=70, aware=False):
    timestamp = AGORA - timedelta(minutes=min_atras)
    if aware:
        timestamp = timestamp.replace(tzinfo=timezone(timedelta(hours=-3)))
    return LeituraSensor(
        fonte=FonteSensor.SMARTWATCH,
        tipo=TipoLeitura.FREQUENCIA_CARDIACA,
        valor=bpm,
        unidade="bpm",
        timestamp=timestamp,
    )


def presenca(min_atras):
    return esp(min_atras, TipoLeitura.PRESENCA)


def test_risco_8h_sem_movimento_com_esp32_vivo():
    evento = classificar_por_regra([presenca(480), esp(2), fc(5)], AGORA)
    assert evento.status == StatusMonitoramento.RISCO
    assert "8.0h" in evento.motivo


def test_normal_7h_sem_movimento():
    evento = classificar_por_regra([presenca(420), esp(2), fc(5)], AGORA)
    assert evento.status == StatusMonitoramento.NORMAL


def test_sinal_de_vida_nao_conta_como_movimento():
    evento = classificar_por_regra([presenca(540), esp(1), fc(5)], AGORA)
    assert evento.status == StatusMonitoramento.RISCO


def test_esp32_vivo_ha_8h_sem_nenhuma_presenca_e_risco():
    # A presença saiu da janela de consulta (ou nunca existiu), mas os sinais
    # de vida mostram que o sensor estava ligado durante as 8 h.
    evento = classificar_por_regra([esp(481), esp(2), fc(5)], AGORA)
    assert evento.status == StatusMonitoramento.RISCO


def test_instalacao_nova_com_esp32_vivo_ha_pouco_tempo_e_normal():
    evento = classificar_por_regra([esp(10), esp(2), fc(5)], AGORA)
    assert evento.status == StatusMonitoramento.NORMAL


def test_risco_quando_as_duas_fontes_param():
    evento = classificar_por_regra([esp(20), fc(40)], AGORA)
    assert evento.status == StatusMonitoramento.RISCO
    assert evento.motivo == MOTIVO_SEM_NENHUMA_FONTE


def test_aviso_so_esp32_parado():
    evento = classificar_por_regra([esp(20), fc(5)], AGORA)
    assert evento.status == StatusMonitoramento.AVISO
    assert evento.motivo == MOTIVO_ESP32_SEM_SINAL


def test_aviso_so_pulseira_parada():
    evento = classificar_por_regra([presenca(60), esp(2), fc(40)], AGORA)
    assert evento.status == StatusMonitoramento.AVISO
    assert evento.motivo == MOTIVO_PULSEIRA_SEM_DADOS


def test_limite_exato_de_15_min_conta_como_silencio():
    evento = classificar_por_regra([esp(15), fc(5)], AGORA)
    assert evento.status == StatusMonitoramento.AVISO


def test_atencao_vence_aviso():
    evento = classificar_por_regra([fc(1, bpm=250), esp(20)], AGORA)
    assert evento.status == StatusMonitoramento.ATENCAO


def test_sem_nenhuma_leitura_e_risco():
    evento = classificar_por_regra([], AGORA)
    assert evento.status == StatusMonitoramento.RISCO
    assert evento.motivo == MOTIVO_SEM_NENHUMA_FONTE


def test_mistura_timestamp_com_fuso_sem_erro():
    evento = classificar_por_regra([fc(5, aware=True), esp(2), presenca(60)], AGORA)
    assert evento.status == StatusMonitoramento.NORMAL


def test_sinais_de_vida_nao_vao_para_as_leituras_relacionadas():
    # São 288 por dia: iriam parar inteiros na resposta da ferramenta do agente.
    sinais = [esp(m) for m in range(2, 60, 5)]
    normal = classificar_por_regra(sinais + [presenca(30), fc(5)], AGORA)
    aviso = classificar_por_regra([esp(m) for m in range(20, 60, 5)] + [fc(5)], AGORA)
    risco = classificar_por_regra([esp(m) for m in range(20, 60, 5)] + [fc(40)], AGORA)
    for evento in (normal, aviso, risco):
        assert all(l.tipo != TipoLeitura.SINAL_DE_VIDA for l in evento.leituras_relacionadas)
