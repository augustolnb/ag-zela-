from datetime import datetime

from zela.models.monitoramento import (
    EventoMonitoramento,
    LeituraSensor,
    MetodoClassificacao,
    StatusMonitoramento,
    TipoLeitura,
)

LIMITE_HORAS_SEM_PRESENCA = 6.0


def classificar_por_regra(
    leituras: list[LeituraSensor],
    agora: datetime,
    limite_horas_sem_presenca: float = LIMITE_HORAS_SEM_PRESENCA,
) -> EventoMonitoramento:
    leituras_presenca = [leitura for leitura in leituras if leitura.tipo == TipoLeitura.PRESENCA]
    leituras_fc = [leitura for leitura in leituras if leitura.tipo == TipoLeitura.FREQUENCIA_CARDIACA]

    if leituras_presenca:
        ultima_presenca = max(leitura.timestamp for leitura in leituras_presenca)
        horas_sem_presenca = (agora - ultima_presenca).total_seconds() / 3600
        if horas_sem_presenca >= limite_horas_sem_presenca:
            return EventoMonitoramento(
                status=StatusMonitoramento.RISCO,
                motivo=f"Sem movimentação detectada há {horas_sem_presenca:.1f}h",
                leituras_relacionadas=leituras_presenca,
                timestamp=agora,
                metodo_classificacao=MetodoClassificacao.REGRA,
            )

    leituras_fc_implausiveis = [leitura for leitura in leituras_fc if not leitura.plausivel]
    if leituras_fc_implausiveis:
        return EventoMonitoramento(
            status=StatusMonitoramento.ATENCAO,
            motivo="Frequência cardíaca fora da faixa esperada",
            leituras_relacionadas=leituras_fc_implausiveis,
            timestamp=agora,
            metodo_classificacao=MetodoClassificacao.REGRA,
        )

    return EventoMonitoramento(
        status=StatusMonitoramento.NORMAL,
        motivo="Nenhuma anomalia detectada",
        leituras_relacionadas=leituras,
        timestamp=agora,
        metodo_classificacao=MetodoClassificacao.REGRA,
    )
