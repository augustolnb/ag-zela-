from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura

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
    agora = datetime.now()
    if timestamp > agora + TOLERANCIA_FUTURO:
        raise ValueError(f"timestamp no futuro: {timestamp.isoformat()!r}")
    if timestamp < agora - LIMITE_PASSADO:
        raise ValueError(f"timestamp implausivelmente antigo: {timestamp.isoformat()!r}")


def montar_roteador_ingestao(salvar_leitura, id_idoso: str = _ID_IDOSO_PADRAO) -> APIRouter:
    roteador = APIRouter()

    @roteador.post("/ingest/esp32")
    async def receber_esp32(request: Request):
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
        try:
            corpo = await request.json()
            timestamp = datetime.fromisoformat(corpo["timestamp"])
            _validar_timestamp_plausivel(timestamp)
            leitura = LeituraSensor(
                fonte=FonteSensor.SMARTWATCH,
                tipo=TipoLeitura.FREQUENCIA_CARDIACA,
                valor=float(corpo["value"]),
                unidade=corpo.get("unit", "bpm"),
                timestamp=timestamp,
            )
        except (ValidationError, KeyError, ValueError, TypeError) as erro:
            return JSONResponse(status_code=400, content={"status": "erro", "detalhe": str(erro)})
        await run_in_threadpool(salvar_leitura, leitura, id_idoso)
        return {"status": "recebido"}

    return roteador
