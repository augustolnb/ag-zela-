from datetime import date, datetime

from zela.domain.monitoramento import _hora_local
from zela.models.monitoramento import (
    EventoMonitoramento,
    LeituraSensor,
    MetodoClassificacao,
    StatusMonitoramento,
)

DESVIO_SONO = 0.30
NOITES_BASE = 14
MIN_NOITES_HISTORICO = 7


def _horas_por_data(leituras_sono: list[LeituraSensor]) -> dict[date, float]:
    # Cada sincronização do Health Connect reenvia as sessões já recebidas, e a
    # ingestão só faz INSERT: sem desduplicar, o sono seria contado em dobro.
    sessoes = {_hora_local(leitura.timestamp): leitura.valor for leitura in leituras_sono}
    horas: dict[date, float] = {}
    for fim, duracao in sessoes.items():
        horas[fim.date()] = horas.get(fim.date(), 0.0) + duracao
    return horas


def avaliar_sono(leituras_sono: list[LeituraSensor], agora: datetime) -> EventoMonitoramento | None:
    agora = _hora_local(agora)
    horas = _horas_por_data(leituras_sono)
    noite = horas.get(agora.date())
    anteriores = sorted((d for d in horas if d < agora.date()), reverse=True)[:NOITES_BASE]
    if noite is None or len(anteriores) < MIN_NOITES_HISTORICO:
        return None

    media = sum(horas[d] for d in anteriores) / len(anteriores)
    if media <= 0 or round(abs(noite - media) / media, 6) < DESVIO_SONO:
        return None
    return EventoMonitoramento(
        status=StatusMonitoramento.AVISO,
        motivo=f"Sono da noite fora do habitual: {noite:.1f}h (média {media:.1f}h)",
        leituras_relacionadas=leituras_sono,
        timestamp=agora,
        metodo_classificacao=MetodoClassificacao.REGRA,
    )
