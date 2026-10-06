import httpx


class WahaClient:
    def __init__(self, base_url: str, session: str = "default", api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = session
        self.api_key = api_key

    def _headers(self) -> dict:
        return {"X-Api-Key": self.api_key} if self.api_key else {}

    def enviar_texto(self, telefone: str, texto: str) -> dict:
        resposta = httpx.post(
            f"{self.base_url}/api/sendText",
            json={"chatId": self._para_chat_id(telefone), "text": texto, "session": self.session},
            headers=self._headers(),
            timeout=30,
        )
        resposta.raise_for_status()
        return resposta.json()

    def enviar_audio(self, telefone: str, audio_base64: str, mimetype: str = "audio/ogg") -> dict:
        resposta = httpx.post(
            f"{self.base_url}/api/sendVoice",
            json={
                "chatId": self._para_chat_id(telefone),
                "file": {"mimetype": mimetype, "data": audio_base64},
                "session": self.session,
            },
            headers=self._headers(),
            timeout=30,
        )
        resposta.raise_for_status()
        return resposta.json()

    @staticmethod
    def _para_chat_id(telefone: str) -> str:
        if "@" in telefone:
            # Já é um JID completo (ex.: "...@c.us" ou "...@lid" quando o
            # remetente usa o identificador de privacidade do WhatsApp) —
            # repassa sem reformatar.
            return telefone
        numero = telefone.lstrip("+")
        return f"{numero}@c.us"
