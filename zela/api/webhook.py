import logging
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

_ID_IDOSO_PADRAO = "idosa-1"
_RESPOSTA_FALHA_LLM = (
    "Desculpe, não consegui responder agora. Tente de novo em alguns minutos. "
    "Se estiver passando mal, me diga o que está sentindo ou ligue 192."
)


def _extrair_telefone_e_texto(payload: dict) -> tuple[str, str] | None:
    """Extrai o identificador do remetente e o texto da mensagem.

    O WhatsApp normalmente identifica o remetente por telefone
    ("<dígitos>@c.us"), convertido aqui para E.164 ("+<dígitos>"). Quando o
    contato tem a privacidade de LID ativada, o WAHA entrega em vez disso um
    identificador opaco ("<dígitos>@lid") e nunca revela o telefone real —
    nesse caso o JID completo é devolvido como identificador, sem conversão.
    """
    dados = payload.get("payload", {})
    if dados.get("fromMe"):
        return None
    remetente = dados.get("from")
    texto = dados.get("body")
    if not remetente or not texto:
        return None
    return _identificador(remetente), texto


def _identificador(remetente: str) -> str:
    if remetente.endswith("@lid"):
        return remetente
    return "+" + remetente.split("@")[0]


def _permitido(telefone: str, telefones_permitidos, lids_permitidos) -> bool:
    lista_permitida = lids_permitidos if telefone.endswith("@lid") else telefones_permitidos
    return lista_permitida is None or telefone in lista_permitida


def montar_roteador(
    processar_mensagem,
    waha_client,
    id_idoso: str = _ID_IDOSO_PADRAO,
    telefones_permitidos: list[str] | None = None,
    lids_permitidos: list[str] | None = None,
    processar_risco=None,
    token: str | None = None,
    processar_emergencia=None,
    processar_voto=None,
) -> APIRouter:
    roteador = APIRouter()

    @roteador.post("/webhook/whatsapp")
    async def receber_mensagem(request: Request):
        # Sem isso, qualquer um que descubra esta URL pública aciona o
        # agente de IA de verdade (custo de API) e tenta mandar WhatsApp em
        # nome do Zela+ — a allowlist de telefones não basta como defesa
        # sozinha porque, antes de qualquer perfil ser cadastrado, ela vem
        # None (sem filtro) por design (ver testes sem token configurado).
        if token is not None and request.headers.get("X-Api-Key") != token:
            return JSONResponse(status_code=401, content={"erro": "token inválido"})

        payload = await request.json()

        evento = payload.get("event")
        if evento == "poll.vote.failed":
            # O WAHA não conseguiu decifrar o voto; o idoso ainda pode responder "tomei".
            logger.warning("Voto de enquete ilegível (poll.vote.failed)")
            return {"status": "ignorado"}
        if evento == "poll.vote":
            return await _tratar_voto(payload.get("payload", {}))

        extraido = _extrair_telefone_e_texto(payload)
        if extraido is None:
            return {"status": "ignorado"}
        telefone, texto = extraido
        if not _permitido(telefone, telefones_permitidos, lids_permitidos):
            return {"status": "ignorado"}

        agora = datetime.now()

        # Antes do LLM: o aviso à família não pode atrasar nem falhar por causa do Gemini.
        if processar_emergencia is not None:
            resposta_emergencia = None
            try:
                resposta_emergencia = await run_in_threadpool(processar_emergencia, telefone, texto, agora)
            except Exception:
                logger.exception("Falha na triagem de emergência da mensagem")
            if resposta_emergencia is not None:
                try:
                    await run_in_threadpool(waha_client.enviar_texto, telefone, resposta_emergencia)
                except Exception:
                    # O episódio já está salvo: a família é avisada no prazo mesmo assim.
                    logger.exception("Falha ao enviar a resposta de emergência ao paciente")
                return {"status": "emergencia"}

        # Sem isso, uma falha do LLM vira erro 500 e o WAHA repete a mesma mensagem até 15 vezes.
        try:
            resposta_texto = await run_in_threadpool(processar_mensagem, id_idoso, texto, agora)
        except Exception:
            logger.exception("Falha do LLM ao processar a mensagem")
            resposta_texto = _RESPOSTA_FALHA_LLM
        await run_in_threadpool(waha_client.enviar_texto, telefone, resposta_texto)

        if processar_risco is not None:
            try:
                await run_in_threadpool(processar_risco, telefone, texto, agora)
            except Exception:
                logger.exception("Falha ao processar risco da mensagem")

        return {"status": "processado"}

    async def _tratar_voto(dados: dict):
        voto = dados.get("vote") or {}
        remetente = voto.get("from")
        if processar_voto is None or voto.get("fromMe") or not remetente:
            return {"status": "ignorado"}
        telefone = _identificador(remetente)
        if not _permitido(telefone, telefones_permitidos, lids_permitidos):
            return {"status": "ignorado"}
        chave = (dados.get("poll") or {}).get("id", "")
        selecionadas = voto.get("selectedOptions") or []
        # Erros viram log, nunca 500: o WAHA repetiria o evento.
        try:
            resposta = await run_in_threadpool(processar_voto, chave, selecionadas, datetime.now())
            if resposta:
                await run_in_threadpool(waha_client.enviar_texto, telefone, resposta)
        except Exception:
            logger.exception("Falha ao processar voto de enquete")
        return {"status": "voto"}

    return roteador
