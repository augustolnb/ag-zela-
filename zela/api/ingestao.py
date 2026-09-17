from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura

_ID_IDOSO_PADRAO = "idosa-1"


def montar_roteador_ingestao(salvar_leitura, id_idoso: str = _ID_IDOSO_PADRAO) -> APIRouter:
    roteador = APIRouter()

    @roteador.post("/ingest/esp32")
    async def receber_esp32(request: Request):
        corpo = await request.json()
        try:
            leitura = LeituraSensor(
                fonte=FonteSensor.ESP32,
                tipo=TipoLeitura.PRESENCA,
                valor=corpo["valor"],
                unidade="deteccao",
                timestamp=datetime.fromisoformat(corpo["timestamp"]),
            )
        except (ValidationError, KeyError, ValueError) as erro:
            return JSONResponse(status_code=400, content={"status": "erro", "detalhe": str(erro)})
        salvar_leitura(leitura, id_idoso)
        return {"status": "recebido"}

    @roteador.post("/ingest/health-connect")
    async def receber_health_connect(request: Request):
        corpo = await request.json()
        try:
            leitura = LeituraSensor(
                fonte=FonteSensor.SMARTWATCH,
                tipo=TipoLeitura.FREQUENCIA_CARDIACA,
                valor=float(corpo["value"]),
                unidade=corpo.get("unit", "bpm"),
                timestamp=datetime.fromisoformat(corpo["timestamp"]),
            )
        except (ValidationError, KeyError, ValueError) as erro:
            return JSONResponse(status_code=400, content={"status": "erro", "detalhe": str(erro)})
        salvar_leitura(leitura, id_idoso)
        return {"status": "recebido"}

    return roteador
