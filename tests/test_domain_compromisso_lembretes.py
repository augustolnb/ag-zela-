from datetime import datetime, time, timedelta

from zela.domain.compromisso_lembretes import (
    calcular_horarios_lembrete_compromisso,
    calcular_overrides_minutos_google,
    lembretes_compromisso_pendentes,
)
from zela.models.rotina import Compromisso, TipoCompromisso


def _compromisso(data_hora):
    return Compromisso(
        id="c1", titulo="Consulta", data_hora=data_hora, local="Clínica", tipo=TipoCompromisso.CONSULTA
    )


def test_calcular_horarios_inclui_as_tres_chaves_quando_compromisso_e_de_tarde():
    compromisso = _compromisso(datetime(2026, 11, 10, 14, 0))
    horarios = calcular_horarios_lembrete_compromisso(compromisso)
    assert set(horarios) == {"24h", "manha", "1h"}
    assert horarios["24h"] == datetime(2026, 11, 9, 14, 0)
    assert horarios["manha"] == datetime(2026, 11, 10, 8, 0)
    assert horarios["1h"] == datetime(2026, 11, 10, 13, 0)


def test_calcular_horarios_exclui_manha_quando_compromisso_e_antes_das_8h():
    compromisso = _compromisso(datetime(2026, 11, 10, 7, 0))
    horarios = calcular_horarios_lembrete_compromisso(compromisso)
    assert set(horarios) == {"24h", "1h"}


def test_calcular_overrides_minutos_google_calcula_minutos_relativos():
    agora = datetime(2026, 11, 1, 10, 0)
    compromisso = _compromisso(datetime(2026, 11, 3, 14, 0))
    minutos = calcular_overrides_minutos_google(compromisso, agora)
    assert sorted(minutos) == [60, 360, 1440]


def test_calcular_overrides_minutos_google_exclui_horarios_ja_passados():
    compromisso = _compromisso(datetime(2026, 11, 10, 14, 0))
    agora = compromisso.data_hora - timedelta(minutes=30)  # depois de 24h, manha e 1h antes
    minutos = calcular_overrides_minutos_google(compromisso, agora)
    assert minutos == []


def test_lembretes_pendentes_inclui_instantaneo_quando_nao_enviado():
    compromisso = _compromisso(datetime(2026, 11, 10, 14, 0))
    agora = datetime(2026, 11, 1, 9, 0)
    pendentes = lembretes_compromisso_pendentes(compromisso, agora, tipos_ja_enviados=set())
    assert "instantaneo" in pendentes


def test_lembretes_pendentes_nao_repete_instantaneo_ja_enviado():
    compromisso = _compromisso(datetime(2026, 11, 10, 14, 0))
    agora = datetime(2026, 11, 1, 9, 0)
    pendentes = lembretes_compromisso_pendentes(compromisso, agora, tipos_ja_enviados={"instantaneo"})
    assert "instantaneo" not in pendentes


def test_lembretes_pendentes_detecta_1h_antes_dentro_da_janela():
    agora = datetime(2026, 11, 10, 12, 55)
    compromisso = _compromisso(datetime(2026, 11, 10, 13, 55))  # 1h antes = 12:55 (== agora)
    pendentes = lembretes_compromisso_pendentes(compromisso, agora, tipos_ja_enviados={"instantaneo"})
    assert pendentes == ["1h"]


def test_lembretes_pendentes_ignora_tipo_ja_enviado_mesmo_na_janela():
    agora = datetime(2026, 11, 10, 12, 55)
    compromisso = _compromisso(datetime(2026, 11, 10, 13, 55))
    pendentes = lembretes_compromisso_pendentes(
        compromisso, agora, tipos_ja_enviados={"instantaneo", "1h"}
    )
    assert pendentes == []


def test_lembretes_pendentes_descarta_24h_quando_criado_a_menos_de_24h_do_evento():
    agora = datetime(2026, 11, 10, 4, 0)
    compromisso = _compromisso(datetime(2026, 11, 10, 14, 0))  # 24h antes = dia 9, 14h — já passou
    pendentes = lembretes_compromisso_pendentes(
        compromisso, agora, tipos_ja_enviados={"instantaneo"}
    )
    assert "24h" not in pendentes
