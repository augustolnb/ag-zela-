from datetime import datetime

from fastapi import APIRouter, Request

_ID_IDOSO_PADRAO = "idosa-1"


def _extrair_telefone_e_texto(payload: dict) -> tuple[str, str] | None:
    dados = payload.get("payload", {})
    remetente = dados.get("from")
    texto = dados.get("body")
    if not remetente or not texto:
        return None
    telefone = "+" + remetente.split("@")[0]
    return telefone, texto


def montar_roteador(processar_mensagem, waha_client, id_idoso: str = _ID_IDOSO_PADRAO) -> APIRouter:
    roteador = APIRouter()

    @roteador.post("/webhook/whatsapp")
    async def receber_mensagem(request: Request):
        payload = await request.json()
        extraido = _extrair_telefone_e_texto(payload)
        if extraido is None:
            return {"status": "ignorado"}
        telefone, texto = extraido

        resposta_texto = processar_mensagem(id_idoso, texto, datetime.now())
        waha_client.enviar_texto(telefone, resposta_texto)

        return {"status": "processado"}

    return roteador
