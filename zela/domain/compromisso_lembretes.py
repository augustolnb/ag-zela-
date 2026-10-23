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
    horarios = {tipo: horario for tipo, horario in candidatos.items() if horario < data_hora}

    # Quando o compromisso é logo depois das 8h (ex.: 09:00), o alvo fixo da
    # "manha" (08:00) e o alvo do "1h antes" caem no mesmo instante (ou bem
    # próximo, dentro da JANELA_LEMBRETE) — sem este descarte, os dois
    # disparariam juntos no mesmo tick do scheduler, com mensagens
    # diferentes, e o Google Agenda receberia um override de minutos
    # duplicado. Mantemos "1h", que é mais preciso/mais próximo do horário
    # real do compromisso.
    manha = horarios.get(TipoLembreteCompromisso.MANHA.value)
    h1 = horarios.get(TipoLembreteCompromisso.H1.value)
    if manha is not None and h1 is not None and abs(manha - h1) <= JANELA_LEMBRETE:
        del horarios[TipoLembreteCompromisso.MANHA.value]

    return horarios


def lembretes_compromisso_pendentes(
    compromisso: Compromisso,
    agora: datetime,
    tipos_ja_enviados: set[str],
) -> list[str]:
    # Um compromisso cujo horário já passou nunca deve gerar nenhum lembrete
    # — nem mesmo "instantaneo". Sem esta guarda, o primeiro tick do
    # scheduler contra um banco de produção existente (onde a tabela
    # `lembrete_compromisso_enviado` começa vazia) dispararia "instantaneo"
    # para TODO compromisso já registrado, por mais antigo que seja.
    if compromisso.data_hora <= agora:
        return []

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
