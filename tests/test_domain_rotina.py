from datetime import datetime, time

from zela.domain.rotina import calcular_lembretes_pendentes, registrar_confirmacao
from zela.models.rotina import CanalConfirmacao, ConfirmacaoMedicacao, Dosagem, Medicamento, StatusConfirmacao


def _medicamento(horario=time(8, 0), dias_semana=None):
    kwargs = dict(
        id="med-1",
        nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"),
        horarios=[horario],
    )
    if dias_semana is not None:
        kwargs["dias_semana"] = dias_semana
    return Medicamento(**kwargs)


def test_lembrete_pendente_dentro_da_janela():
    medicamento = _medicamento()
    agora = datetime(2026, 9, 13, 8, 5)  # domingo (weekday() == 6); dias_semana padrão inclui todos os dias
    pendentes = calcular_lembretes_pendentes([medicamento], [], agora)
    assert pendentes == [medicamento]


def test_lembrete_fora_da_janela_nao_aparece():
    medicamento = _medicamento()
    agora = datetime(2026, 9, 13, 9, 0)
    pendentes = calcular_lembretes_pendentes([medicamento], [], agora)
    assert pendentes == []


def test_lembrete_ja_confirmado_hoje_nao_aparece():
    medicamento = _medicamento()
    agora = datetime(2026, 9, 13, 8, 5)
    confirmacao = ConfirmacaoMedicacao(
        medicamento_id="med-1",
        horario_previsto=datetime(2026, 9, 13, 8, 0),
        horario_confirmado=datetime(2026, 9, 13, 8, 1),
        status=StatusConfirmacao.CONFIRMADO,
        canal=CanalConfirmacao.WHATSAPP,
    )
    pendentes = calcular_lembretes_pendentes([medicamento], [confirmacao], agora)
    assert pendentes == []


def test_lembrete_fora_do_dia_da_semana_nao_aparece():
    # 2026-09-13 é domingo (datetime.weekday() == 6); dias_semana=[0..4] é
    # segunda a sexta, que exclui domingo.
    medicamento = _medicamento(dias_semana=[0, 1, 2, 3, 4])
    agora = datetime(2026, 9, 13, 8, 5)
    pendentes = calcular_lembretes_pendentes([medicamento], [], agora)
    assert pendentes == []


def test_registrar_confirmacao_no_horario():
    medicamento = _medicamento()
    horario_previsto = datetime(2026, 9, 13, 8, 0)
    agora = datetime(2026, 9, 13, 8, 5)
    confirmacao = registrar_confirmacao(medicamento, horario_previsto, agora)
    assert confirmacao.status == StatusConfirmacao.CONFIRMADO
    assert confirmacao.medicamento_id == "med-1"


def test_registrar_confirmacao_atrasada():
    medicamento = _medicamento()
    horario_previsto = datetime(2026, 9, 13, 8, 0)
    agora = datetime(2026, 9, 13, 9, 0)
    confirmacao = registrar_confirmacao(medicamento, horario_previsto, agora)
    assert confirmacao.status == StatusConfirmacao.ATRASADO
