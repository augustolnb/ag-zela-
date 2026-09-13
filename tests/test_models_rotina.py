from datetime import datetime, time, timedelta

import pytest
from pydantic import ValidationError

from zela.models.rotina import (
    CanalConfirmacao,
    Compromisso,
    ConfirmacaoMedicacao,
    Dosagem,
    Medicamento,
    StatusConfirmacao,
    TipoCompromisso,
)


def test_medicamento_valido():
    medicamento = Medicamento(
        id="med-1",
        nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"),
        horarios=[time(8, 0), time(20, 0)],
    )
    assert medicamento.ativo is True
    assert medicamento.dias_semana == list(range(7))


def test_dosagem_rejeita_quantidade_nao_positiva():
    with pytest.raises(ValidationError):
        Dosagem(quantidade=0, unidade="mg")


def test_medicamento_rejeita_horarios_vazios():
    with pytest.raises(ValidationError):
        Medicamento(id="med-1", nome="Losartana", dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[])


def test_medicamento_rejeita_horarios_duplicados():
    with pytest.raises(ValidationError):
        Medicamento(
            id="med-1",
            nome="Losartana",
            dosagem=Dosagem(quantidade=50, unidade="mg"),
            horarios=[time(8, 0), time(8, 0)],
        )


def test_medicamento_rejeita_dia_semana_invalido():
    with pytest.raises(ValidationError):
        Medicamento(
            id="med-1",
            nome="Losartana",
            dosagem=Dosagem(quantidade=50, unidade="mg"),
            horarios=[time(8, 0)],
            dias_semana=[7],
        )


def test_compromisso_rejeita_data_no_passado():
    with pytest.raises(ValidationError):
        Compromisso(
            id="cp-1",
            titulo="Consulta cardiologista",
            data_hora=datetime.now() - timedelta(days=1),
            local="Clínica Central",
            tipo=TipoCompromisso.CONSULTA,
        )


def test_compromisso_aceita_data_futura():
    compromisso = Compromisso(
        id="cp-1",
        titulo="Consulta cardiologista",
        data_hora=datetime.now() + timedelta(days=1),
        local="Clínica Central",
        tipo=TipoCompromisso.CONSULTA,
    )
    assert compromisso.tipo == TipoCompromisso.CONSULTA


def test_confirmacao_medicacao_valida():
    confirmacao = ConfirmacaoMedicacao(
        medicamento_id="med-1",
        horario_previsto=datetime(2026, 9, 13, 8, 0),
        horario_confirmado=datetime(2026, 9, 13, 8, 5),
        status=StatusConfirmacao.CONFIRMADO,
        canal=CanalConfirmacao.WHATSAPP,
    )
    assert confirmacao.status == StatusConfirmacao.CONFIRMADO
