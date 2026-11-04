from datetime import date, datetime, timedelta

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


TOLERANCIA_INICIO = timedelta(minutes=3)


def _horas_por_data(leituras_sono: list[LeituraSensor]) -> dict[date, float]:
    # O Mi Fitness atualiza a sessão em andamento, e cada versão chega ao
    # Health Connect com o mesmo início e um fim mais tarde (visto em produção:
    # 2,02 h às 03:23 e 4,92 h às 06:17 na mesma noite). Agrupa pelo início
    # (fim − duração, com folga de arredondamento) e fica com a versão mais longa.
    sessoes: list[tuple[datetime, datetime, float]] = []
    for leitura in leituras_sono:
        fim = _hora_local(leitura.timestamp)
        inicio = fim - timedelta(hours=leitura.valor)
        sessoes.append((inicio, fim, leitura.valor))
    sessoes.sort()

    unicas: list[tuple[datetime, datetime, float]] = []
    for inicio, fim, duracao in sessoes:
        if unicas and inicio - unicas[-1][0] <= TOLERANCIA_INICIO:
            if duracao > unicas[-1][2]:
                unicas[-1] = (unicas[-1][0], fim, duracao)
            continue
        unicas.append((inicio, fim, duracao))

    horas: dict[date, float] = {}
    for _, fim, duracao in unicas:
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
