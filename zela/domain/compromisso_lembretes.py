from datetime import datetime, time, timedelta
from enum import Enum

from zela.domain.rotina import JANELA_LEMBRETE
from zela.models.rotina import Compromisso

HORARIO_LEMBRETE_MANHA = time(8, 0)


class TipoLembreteCompromisso(str, Enum):
    INSTANTANEO = "instantaneo"
    H24 = "24h"
    MANHA = "manha"
    H1 = "1h"
    CANCELAMENTO = "cancelamento"


def calcular_horarios_lembrete_compromisso(compromisso: Compromisso) -> dict[str, datetime]:
    data_hora = compromisso.data_hora
    candidatos = {
        TipoLembreteCompromisso.H24.value: data_hora - timedelta(hours=24),
        TipoLembreteCompromisso.MANHA.value: datetime.combine(data_hora.date(), HORARIO_LEMBRETE_MANHA),
        TipoLembreteCompromisso.H1.value: data_hora - timedelta(hours=1),
    }
    return {tipo: horario for tipo, horario in candidatos.items() if horario < data_hora}


def lembretes_compromisso_pendentes(
    compromisso: Compromisso,
    agora: datetime,
    tipos_ja_enviados: set[str],
) -> list[str]:
    pendentes: list[str] = []
    if TipoLembreteCompromisso.INSTANTANEO.value not in tipos_ja_enviados:
        pendentes.append(TipoLembreteCompromisso.INSTANTANEO.value)
    for tipo, horario_alvo in calcular_horarios_lembrete_compromisso(compromisso).items():
        if tipo in tipos_ja_enviados:
            continue
        if horario_alvo <= agora <= horario_alvo + JANELA_LEMBRETE:
            pendentes.append(tipo)
    return pendentes


def calcular_overrides_minutos_google(compromisso: Compromisso, agora: datetime) -> list[int]:
    minutos: list[int] = []
    for horario_alvo in calcular_horarios_lembrete_compromisso(compromisso).values():
        if horario_alvo > agora:
            minutos.append(int((compromisso.data_hora - horario_alvo).total_seconds() // 60))
    return minutos
