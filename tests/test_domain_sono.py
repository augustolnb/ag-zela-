from datetime import datetime, timedelta, timezone

from zela.domain.sono import avaliar_sono
from zela.models.monitoramento import FonteSensor, LeituraSensor, StatusMonitoramento, TipoLeitura

AGORA = datetime(2026, 10, 29, 9, 0)


def sessao(dias_atras, horas, hora_fim=7, aware=False):
    fim = (AGORA - timedelta(days=dias_atras)).replace(hour=hora_fim)
    if aware:
        fim = fim.replace(tzinfo=timezone(timedelta(hours=-3)))
    return LeituraSensor(
        fonte=FonteSensor.SMARTWATCH, tipo=TipoLeitura.SONO, valor=horas, unidade="horas", timestamp=fim
    )


def historico(noites=14, horas=7):
    return [sessao(d, horas) for d in range(1, noites + 1)]


def test_noite_30pct_mais_curta_gera_aviso():
    evento = avaliar_sono(historico() + [sessao(0, 4.9)], AGORA)
    assert evento.status == StatusMonitoramento.AVISO
    assert "4.9h" in evento.motivo and "7.0h" in evento.motivo


def test_noite_dentro_da_faixa_nao_avisa():
    assert avaliar_sono(historico() + [sessao(0, 6)], AGORA) is None


def test_noite_muito_longa_gera_aviso():
    assert avaliar_sono(historico() + [sessao(0, 9.1)], AGORA).status == StatusMonitoramento.AVISO


def test_menos_de_7_noites_nao_avisa():
    assert avaliar_sono(historico(noites=6) + [sessao(0, 3)], AGORA) is None


def test_sem_registro_da_noite_nao_avisa():
    assert avaliar_sono(historico(), AGORA) is None


def test_sessoes_duplicadas_nao_somam_duas_vezes():
    assert avaliar_sono(historico() + [sessao(0, 7), sessao(0, 7)], AGORA) is None


def test_cochilo_soma_na_noite():
    assert avaliar_sono(historico() + [sessao(0, 6), sessao(0, 1, hora_fim=8)], AGORA) is None


def test_base_usa_no_maximo_14_noites():
    # A 15ª noite, muito longa, não pode entrar na média.
    leituras = historico() + [sessao(15, 40)] + [sessao(0, 7)]
    assert avaliar_sono(leituras, AGORA) is None


def test_mistura_timestamp_com_fuso_sem_erro():
    assert avaliar_sono(historico() + [sessao(0, 7, aware=True)], AGORA) is None
