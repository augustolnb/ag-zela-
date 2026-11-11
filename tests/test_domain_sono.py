from datetime import datetime, timedelta, timezone

from zela.domain.sono import _horas_por_data, avaliar_sono
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


# Dados reais de produção: o Mi Fitness atualiza a sessão em andamento, e cada
# versão chega com o mesmo início (fim − duração) e um fim mais tarde.
def versao(fim, horas):
    return LeituraSensor(
        fonte=FonteSensor.SMARTWATCH, tipo=TipoLeitura.SONO, valor=horas, unidade="horas", timestamp=fim
    )


def test_versoes_da_mesma_noite_contam_so_a_mais_longa():
    noite = [versao(AGORA.replace(hour=3, minute=23), 2.02), versao(AGORA.replace(hour=6, minute=17), 4.92)]
    assert avaliar_sono(historico(horas=5) + noite, AGORA) is None


def test_versoes_repetidas_nao_inflam_a_media():
    anteriores = []
    for d in range(1, 15):
        dia = AGORA - timedelta(days=d)
        anteriores += [
            versao(dia.replace(hour=5, minute=42), 6.05),
            versao(dia.replace(hour=6, minute=25), 6.77),
            versao(dia.replace(hour=7, minute=37), 7.97),
        ]
    evento = avaliar_sono(anteriores + [versao(AGORA.replace(hour=6, minute=17), 4.92)], AGORA)
    assert "(média 8.0h)" in evento.motivo


def test_versao_parcial_antes_da_meia_noite_conta_so_no_dia_do_fim():
    ontem = AGORA - timedelta(days=1)
    leituras = [versao(ontem.replace(hour=23, minute=17), 1.08), versao(AGORA.replace(hour=6, minute=6), 7.9)]
    assert _horas_por_data(leituras) == {AGORA.date(): 7.9}


def test_inicios_com_diferenca_de_arredondamento_sao_a_mesma_sessao():
    leituras = [
        versao(AGORA.replace(hour=5, minute=58), 2.53),
        versao(AGORA.replace(hour=6, minute=30), 3.07),
        versao(AGORA.replace(hour=7, minute=50), 4.4),
    ]
    assert _horas_por_data(leituras) == {AGORA.date(): 4.4}
