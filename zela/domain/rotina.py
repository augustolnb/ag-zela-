from datetime import datetime, timedelta

from zela.models.rotina import CanalConfirmacao, ConfirmacaoMedicacao, Medicamento, StatusConfirmacao

JANELA_LEMBRETE = timedelta(minutes=15)
TOLERANCIA_ATRASO = timedelta(minutes=30)


def calcular_lembretes_pendentes(
    medicamentos: list[Medicamento],
    confirmacoes: list[ConfirmacaoMedicacao],
    agora: datetime,
) -> list[Medicamento]:
    dia_semana_atual = agora.weekday()
    confirmados_hoje = {
        c.medicamento_id
        for c in confirmacoes
        if c.horario_previsto.date() == agora.date() and c.status == StatusConfirmacao.CONFIRMADO
    }

    pendentes = []
    for medicamento in medicamentos:
        if not medicamento.ativo or dia_semana_atual not in medicamento.dias_semana:
            continue
        if medicamento.id in confirmados_hoje:
            continue
        for horario in medicamento.horarios:
            horario_previsto = datetime.combine(agora.date(), horario)
            if horario_previsto <= agora <= horario_previsto + JANELA_LEMBRETE:
                pendentes.append(medicamento)
                break
    return pendentes


def registrar_confirmacao(
    medicamento: Medicamento,
    horario_previsto: datetime,
    agora: datetime,
    canal: CanalConfirmacao = CanalConfirmacao.WHATSAPP,
) -> ConfirmacaoMedicacao:
    atrasado = agora > horario_previsto + TOLERANCIA_ATRASO
    return ConfirmacaoMedicacao(
        medicamento_id=medicamento.id,
        horario_previsto=horario_previsto,
        horario_confirmado=agora,
        status=StatusConfirmacao.ATRASADO if atrasado else StatusConfirmacao.CONFIRMADO,
        canal=canal,
    )
