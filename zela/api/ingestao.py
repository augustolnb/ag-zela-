import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura

logger = logging.getLogger(__name__)

_ID_IDOSO_PADRAO = "idosa-1"

# Tolerância de relógio (ex.: pequeno drift de NTP) para timestamps futuros,
# e limite para timestamps muito antigos (ex.: ESP32 que ainda não
# sincronizou NTP e envia uma data próxima da época Unix). Fora dessa janela
# a leitura é rejeitada com 400 em vez de ser aceita silenciosamente — um
# timestamp futuro faria `classificar_por_regra` computar horas negativas
# "sem presença" (mascarando um risco real), e um timestamp muito antigo cai
# fora da janela de lookback de `aplicar_classificacao`, alimentando o
# caminho de "sem dados".
TOLERANCIA_FUTURO = timedelta(minutes=5)
LIMITE_PASSADO = timedelta(days=365)


def _validar_timestamp_plausivel(timestamp: datetime) -> None:
    # datetime.now(None) == datetime.now() (naive) — mas datetime.now(tz)
    # com o mesmo tzinfo do timestamp evita o TypeError de comparar um
    # datetime "aware" (ex.: Health Connect manda com offset, tipo
    # "-03:00") com um "naive" (ESP32 manda sem timezone).
    agora = datetime.now(timestamp.tzinfo)
    if timestamp > agora + TOLERANCIA_FUTURO:
        raise ValueError(f"timestamp no futuro: {timestamp.isoformat()!r}")
    if timestamp < agora - LIMITE_PASSADO:
        raise ValueError(f"timestamp implausivelmente antigo: {timestamp.isoformat()!r}")


def _token_valido(request: Request, token: str | None) -> bool:
    return token is None or request.headers.get("X-Api-Key") == token


def _ler_passos(item: dict) -> LeituraSensor:
    return LeituraSensor(
        fonte=FonteSensor.SMARTWATCH,
        tipo=TipoLeitura.PASSOS,
        valor=float(item["count"]),
        unidade="passos",
        timestamp=datetime.fromisoformat(item["end_time"]),
    )


def _ler_sono(item: dict) -> LeituraSensor:
    return LeituraSensor(
        fonte=FonteSensor.SMARTWATCH,
        tipo=TipoLeitura.SONO,
        valor=item["duration_seconds"] / 3600,
        unidade="horas",
        timestamp=datetime.fromisoformat(item["session_end_time"]),
    )


def _ler_frequencia_cardiaca(item: dict) -> LeituraSensor:
    return LeituraSensor(
        fonte=FonteSensor.SMARTWATCH,
        tipo=TipoLeitura.FREQUENCIA_CARDIACA,
        # "bpm" existe nos dois modos de resolução do app (amostra bruta ou
        # agregado por minuto, onde bpm é um alias de avg) — ver docs/webhook.md
        # do projeto health-connect-webhook.
        valor=float(item["bpm"]),
        unidade="bpm",
        timestamp=datetime.fromisoformat(item["time"]),
    )


# Payload real do app "Health Connect Webhook" (confirmado em produção,
# issue #41): um objeto com uma chave por tipo de dado, cada uma uma lista
# de registros — não o formato plano {"value", "unit", "timestamp"} que o
# README assumia antes de testarmos com o app de verdade.
_EXTRATORES_HEALTH_CONNECT = {
    "steps": _ler_passos,
    "sleep": _ler_sono,
    "heart_rate": _ler_frequencia_cardiaca,
}


def _extrair_leituras_health_connect(corpo: dict) -> tuple[list[LeituraSensor], int]:
    """Converte o payload do Health Connect Webhook em leituras.

    Um único POST real traz dezenas de registros (histórico de frequência
    cardíaca em janelas de minutos, por exemplo) — um item individual
    malformado é descartado em vez de derrubar o lote inteiro.
    """
    leituras: list[LeituraSensor] = []
    descartadas = 0
    for chave, extrator in _EXTRATORES_HEALTH_CONNECT.items():
        for item in corpo.get(chave) or []:
            try:
                leitura = extrator(item)
                _validar_timestamp_plausivel(leitura.timestamp)
            except (ValidationError, KeyError, ValueError, TypeError):
                descartadas += 1
                continue
            leituras.append(leitura)
    return leituras, descartadas


def montar_roteador_ingestao(
    salvar_leitura, id_idoso: str = _ID_IDOSO_PADRAO, token: str | None = None
) -> APIRouter:
    roteador = APIRouter()

    @roteador.post("/ingest/esp32")
    async def receber_esp32(request: Request):
        if not _token_valido(request, token):
            return JSONResponse(status_code=401, content={"status": "erro", "detalhe": "token inválido"})
        try:
            corpo = await request.json()
            timestamp = datetime.fromisoformat(corpo["timestamp"])
            _validar_timestamp_plausivel(timestamp)
            leitura = LeituraSensor(
                fonte=FonteSensor.ESP32,
                tipo=TipoLeitura.PRESENCA,
                valor=corpo["valor"],
                unidade="deteccao",
                timestamp=timestamp,
            )
        except (ValidationError, KeyError, ValueError, TypeError) as erro:
            return JSONResponse(status_code=400, content={"status": "erro", "detalhe": str(erro)})
        await run_in_threadpool(salvar_leitura, leitura, id_idoso)
        return {"status": "recebido"}

    @roteador.post("/ingest/health-connect")
    async def receber_health_connect(request: Request):
        if not _token_valido(request, token):
            return JSONResponse(status_code=401, content={"status": "erro", "detalhe": "token inválido"})
        try:
            corpo = await request.json()
        except ValueError as erro:
            return JSONResponse(status_code=400, content={"status": "erro", "detalhe": str(erro)})
        if not isinstance(corpo, dict):
            return JSONResponse(status_code=400, content={"status": "erro", "detalhe": "corpo deve ser um objeto JSON"})

        leituras, descartadas = _extrair_leituras_health_connect(corpo)
        if not leituras:
            return JSONResponse(
                status_code=400,
                content={"status": "erro", "detalhe": "nenhuma leitura reconhecida no payload"},
            )

        for leitura in leituras:
            await run_in_threadpool(salvar_leitura, leitura, id_idoso)

        logger.info(
            "health-connect: %d leitura(s) salvas, %d descartada(s)", len(leituras), descartadas
        )
        return {"status": "recebido", "leituras_salvas": len(leituras), "leituras_descartadas": descartadas}

    return roteador
