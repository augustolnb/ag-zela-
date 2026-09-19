import logging
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from zela.embeddings.classificador import classificar_por_similaridade

logger = logging.getLogger(__name__)


def montar_roteador_classificacao(cliente_embedding, obter_exemplos_com_embedding) -> APIRouter:
    roteador = APIRouter()

    @roteador.post("/api/classificar-mensagem")
    async def classificar_mensagem(request: Request):
        try:
            corpo = await request.json()
            texto = corpo["texto"]
            if not isinstance(texto, str) or not texto:
                raise ValueError("campo 'texto' deve ser uma string não vazia")
        except (KeyError, TypeError, ValueError) as erro:
            return JSONResponse(status_code=400, content={"erro": f"corpo inválido: {erro}"})

        try:
            embedding = await run_in_threadpool(cliente_embedding.obter_embedding, texto)
            exemplos = await run_in_threadpool(obter_exemplos_com_embedding)
            evento = classificar_por_similaridade(embedding, exemplos, texto, datetime.now())
        except Exception:
            logger.exception("Falha ao classificar mensagem")
            return JSONResponse(status_code=503, content={"erro": "falha ao classificar"})

        return {"status": evento.status.value, "motivo": evento.motivo}

    return roteador
