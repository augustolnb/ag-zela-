from datetime import datetime
from zoneinfo import ZoneInfo

from zela.models.monitoramento import (
    EventoMonitoramento,
    FonteSensor,
    LeituraSensor,
    MetodoClassificacao,
    StatusMonitoramento,
    TipoLeitura,
)

LIMITE_HORAS_SEM_PRESENCA = 8.0
LIMITE_MINUTOS_ESP32 = 15
# Medido em produção: o celular sincronizou com intervalos de até 5h45 (Android
# adia o envio em segundo plano), e o Mi Fitness só repassa batimentos em blocos.
LIMITE_MINUTOS_PULSEIRA = 360

# Textos fixos, sem números: o motivo do AVISO é a chave de desduplicação do
# scheduler, então não pode mudar entre uma verificação e outra.
MOTIVO_ESP32_SEM_SINAL = "O ESP32 da casa parou de enviar sinal"
MOTIVO_PULSEIRA_SEM_DADOS = "A pulseira parou de sincronizar (verifique o celular e o app HC Webhook)"
MOTIVO_SEM_NENHUMA_FONTE = "ESP32 e pulseira pararam de enviar dados ao mesmo tempo"

_FUSO_LOCAL = ZoneInfo("America/Sao_Paulo")


def _hora_local(ts: datetime) -> datetime:
    """Normaliza para horário local sem fuso.

    O Health Connect manda timestamps com fuso; o ESP32 e `datetime.now()` não.
    Comparar os dois formatos diretamente levantaria TypeError.
    """
    if ts.tzinfo is None:
        return ts
    return ts.astimezone(_FUSO_LOCAL).replace(tzinfo=None)


def _minutos_desde(leituras: list[LeituraSensor], agora: datetime) -> float | None:
    if not leituras:
        return None
    ultima = max(_hora_local(leitura.timestamp) for leitura in leituras)
    return (agora - ultima).total_seconds() / 60


def _evento(
    status: StatusMonitoramento, motivo: str, leituras: list[LeituraSensor], agora: datetime
) -> EventoMonitoramento:
    return EventoMonitoramento(
        status=status,
        motivo=motivo,
        leituras_relacionadas=leituras,
        timestamp=agora,
        metodo_classificacao=MetodoClassificacao.REGRA,
    )


def classificar_por_regra(
    leituras: list[LeituraSensor],
    agora: datetime,
    limite_horas_sem_presenca: float = LIMITE_HORAS_SEM_PRESENCA,
    limite_minutos_esp32: float = LIMITE_MINUTOS_ESP32,
    limite_minutos_pulseira: float = LIMITE_MINUTOS_PULSEIRA,
) -> EventoMonitoramento:
    agora = _hora_local(agora)
    leituras_esp32 = [leitura for leitura in leituras if leitura.fonte == FonteSensor.ESP32]
    leituras_presenca = [leitura for leitura in leituras if leitura.tipo == TipoLeitura.PRESENCA]
    leituras_fc = [leitura for leitura in leituras if leitura.tipo == TipoLeitura.FREQUENCIA_CARDIACA]

    minutos_esp32 = _minutos_desde(leituras_esp32, agora)
    # Qualquer dado serve: batimentos faltam mesmo com a pulseira no braço. Isso
    # prova que a sincronização está ativa, não que a pulseira está sendo usada.
    leituras_pulseira = [leitura for leitura in leituras if leitura.fonte == FonteSensor.SMARTWATCH]
    minutos_pulseira = _minutos_desde(leituras_pulseira, agora)
    esp32_silencioso = minutos_esp32 is None or minutos_esp32 >= limite_minutos_esp32
    pulseira_silenciosa = minutos_pulseira is None or minutos_pulseira >= limite_minutos_pulseira

    # Sinais de vida chegam a 288 por dia e não dizem nada sobre o episódio;
    # ficam fora das leituras relacionadas, que vão para a resposta do agente.
    leituras_uteis = [leitura for leitura in leituras if leitura.tipo != TipoLeitura.SINAL_DE_VIDA]

    if esp32_silencioso and pulseira_silenciosa:
        return _evento(StatusMonitoramento.RISCO, MOTIVO_SEM_NENHUMA_FONTE, leituras_uteis, agora)

    if not esp32_silencioso:
        if leituras_presenca:
            minutos_sem_presenca = _minutos_desde(leituras_presenca, agora)
        else:
            # Sem presença na janela: conta desde a leitura mais antiga do ESP32,
            # o período em que ele comprovadamente estava ligado sem ver movimento.
            primeira = min(_hora_local(leitura.timestamp) for leitura in leituras_esp32)
            minutos_sem_presenca = (agora - primeira).total_seconds() / 60
        horas_sem_presenca = minutos_sem_presenca / 60
        if horas_sem_presenca >= limite_horas_sem_presenca:
            return _evento(
                StatusMonitoramento.RISCO,
                f"Sem movimentação detectada há {horas_sem_presenca:.1f}h",
                leituras_presenca,
                agora,
            )

    leituras_fc_implausiveis = [leitura for leitura in leituras_fc if not leitura.plausivel]
    if leituras_fc_implausiveis:
        return _evento(
            StatusMonitoramento.ATENCAO,
            "Frequência cardíaca fora da faixa esperada",
            leituras_fc_implausiveis,
            agora,
        )

    if esp32_silencioso:
        return _evento(StatusMonitoramento.AVISO, MOTIVO_ESP32_SEM_SINAL, leituras_presenca, agora)
    if pulseira_silenciosa:
        return _evento(StatusMonitoramento.AVISO, MOTIVO_PULSEIRA_SEM_DADOS, leituras_pulseira, agora)

    return _evento(StatusMonitoramento.NORMAL, "Nenhuma anomalia detectada", leituras_uteis, agora)
