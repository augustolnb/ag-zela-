import logging

import httpx

logger = logging.getLogger(__name__)


class WahaClient:
    def __init__(self, base_url: str, session: str = "default", api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session
        self.api_key = api_key
        self._chat_ids: dict[str, str] = {}

    def _headers(self) -> dict:
        return {"X-Api-Key": self.api_key} if self.api_key else {}

    def enviar_texto(self, telefone: str, texto: str) -> dict:
        resposta = httpx.post(
            f"{self.base_url}/api/sendText",
            json={"chatId": self.resolver_chat_id(telefone), "text": texto, "session": self.session},
            headers=self._headers(),
            timeout=30,
        )
        resposta.raise_for_status()
        return resposta.json()

    def enviar_audio(self, telefone: str, audio_base64: str, mimetype: str = "audio/ogg") -> dict:
        resposta = httpx.post(
            f"{self.base_url}/api/sendVoice",
            json={
                "chatId": self.resolver_chat_id(telefone),
                "file": {"mimetype": mimetype, "data": audio_base64},
                "session": self.session,
            },
            headers=self._headers(),
            timeout=30,
        )
        resposta.raise_for_status()
        return resposta.json()

    def resolver_chat_id(self, telefone: str) -> str:
        """Telefone → JID real. Conta com LID recusa "<telefone>@c.us" com
        "No LID for user"; o check-exists do WAHA devolve o JID certo. Se a
        consulta falhar, tenta o formato antigo em vez de deixar de enviar."""
        if "@" in telefone:
            return telefone
        if telefone in self._chat_ids:
            return self._chat_ids[telefone]
        try:
            resposta = httpx.get(
                f"{self.base_url}/api/contacts/check-exists",
                params={"phone": telefone.lstrip("+"), "session": self.session},
                headers=self._headers(),
                timeout=10,
            )
            resposta.raise_for_status()
            dados = resposta.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("Não foi possível resolver o chatId; usando o formato padrão")
            return self._para_chat_id(telefone)
        chat_id = dados.get("chatId") if dados.get("numberExists") else None
        if not chat_id:
            return self._para_chat_id(telefone)
        self._chat_ids[telefone] = chat_id
        return chat_id

    @staticmethod
    def _para_chat_id(telefone: str) -> str:
        if "@" in telefone:
            # Já é um JID completo (ex.: "...@c.us" ou "...@lid" quando o
            # remetente usa o identificador de privacidade do WhatsApp) —
            # repassa sem reformatar.
            return telefone
        numero = telefone.lstrip("+")
        return f"{numero}@c.us"
