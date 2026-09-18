import logging
from datetime import datetime

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

_ID_IDOSO_PADRAO = "idosa-1"


def _extrair_telefone_e_texto(payload: dict) -> tuple[str, str] | None:
    dados = payload.get("payload", {})
    if dados.get("fromMe"):
        return None
    remetente = dados.get("from")
    texto = dados.get("body")
    if not remetente or not texto:
        return None
    telefone = "+" + remetente.split("@")[0]
    return telefone, texto


def montar_roteador(
    processar_mensagem,
    waha_client,
    id_idoso: str = _ID_IDOSO_PADRAO,
    telefones_permitidos: list[str] | None = None,
    processar_risco=None,
) -> APIRouter:
    roteador = APIRouter()

    @roteador.post("/webhook/whatsapp")
    async def receber_mensagem(request: Request):
        payload = await request.json()
        extraido = _extrair_telefone_e_texto(payload)
        if extraido is None:
            return {"status": "ignorado"}
        telefone, texto = extraido
        if telefones_permitidos is not None and telefone not in telefones_permitidos:
            return {"status": "ignorado"}

        agora = datetime.now()
        resposta_texto = await run_in_threadpool(processar_mensagem, id_idoso, texto, agora)
        await run_in_threadpool(waha_client.enviar_texto, telefone, resposta_texto)

        if processar_risco is not None:
            try:
                await run_in_threadpool(processar_risco, telefone, texto, agora)
            except Exception:
                logger.exception("Falha ao processar risco da mensagem")

        return {"status": "processado"}

    return roteador
