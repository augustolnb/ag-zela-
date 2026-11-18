from datetime import datetime

from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura
from zela.streamlit_app.graficos import (
    COM_MOVIMENTO,
    SEM_MOVIMENTO,
    grafico_presenca,
    montar_faixas_presenca,
)


def _presenca(valor, hora, minuto=0):
    return LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=valor,
        unidade="bool", timestamp=datetime(2026, 11, 18, hora, minuto),
    )


AGORA = datetime(2026, 11, 18, 12, 0)


def test_sem_leituras_nao_gera_faixas():
    assert montar_faixas_presenca([], AGORA) == []


def test_cada_estado_vale_ate_a_proxima_leitura_e_o_ultimo_ate_agora():
    faixas = montar_faixas_presenca([_presenca(1, 8), _presenca(0, 9)], AGORA)

    assert faixas == [
        {"inicio": datetime(2026, 11, 18, 8), "fim": datetime(2026, 11, 18, 9), "estado": COM_MOVIMENTO},
        {"inicio": datetime(2026, 11, 18, 9), "fim": AGORA, "estado": SEM_MOVIMENTO},
    ]


def test_leituras_seguidas_iguais_viram_uma_faixa_so():
    faixas = montar_faixas_presenca(
        [_presenca(1, 8), _presenca(1, 8, 30), _presenca(1, 9), _presenca(0, 10)], AGORA
    )

    assert [f["estado"] for f in faixas] == [COM_MOVIMENTO, SEM_MOVIMENTO]
    assert faixas[0]["fim"] == datetime(2026, 11, 18, 10)


def test_leituras_fora_de_ordem_sao_ordenadas():
    faixas = montar_faixas_presenca([_presenca(0, 10), _presenca(1, 8)], AGORA)

    assert [f["inicio"].hour for f in faixas] == [8, 10]


def test_ignora_leituras_que_nao_sao_de_presenca():
    batimento = LeituraSensor(
        fonte=FonteSensor.SMARTWATCH, tipo=TipoLeitura.FREQUENCIA_CARDIACA,
        valor=70, unidade="bpm", timestamp=datetime(2026, 11, 18, 9),
    )

    faixas = montar_faixas_presenca([_presenca(1, 8), batimento], AGORA)

    assert len(faixas) == 1


def test_grafico_usa_cores_do_tema_escolhido():
    faixas = montar_faixas_presenca([_presenca(1, 8), _presenca(0, 9)], AGORA)

    claro = grafico_presenca(faixas, noturno=False).to_dict()
    noturno = grafico_presenca(faixas, noturno=True).to_dict()

    assert claro["encoding"]["color"]["scale"]["range"][0] == "#2563EB"
    assert noturno["encoding"]["color"]["scale"]["range"][0] == "#FFD60A"


def test_grafico_nao_desenha_legenda_propria():
    # A legenda vai em HTML abaixo do gráfico: no cartão estreito, a do Vega era cortada.
    faixas = montar_faixas_presenca([_presenca(1, 8)], AGORA)

    assert grafico_presenca(faixas).to_dict()["encoding"]["color"]["legend"] is None


def test_legenda_em_html_usa_as_cores_do_tema():
    from zela.streamlit_app.graficos import legenda_presenca

    claro, noturno = legenda_presenca(noturno=False), legenda_presenca(noturno=True)

    assert COM_MOVIMENTO in claro and SEM_MOVIMENTO in claro
    assert "#2563EB" in claro and "#E2E8F0" in claro
    assert "#FFD60A" in noturno and "#24406B" in noturno
