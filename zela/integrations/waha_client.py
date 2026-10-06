import httpx


class WahaClient:
    def __init__(self, base_url: str, session: str = "default"):
        self.base_url = base_url.rstrip("/")
        self.session = session

    def enviar_texto(self, telefone: str, texto: str) -> dict:
        resposta = httpx.post(
            f"{self.base_url}/api/sendText",
            json={"chatId": self._para_chat_id(telefone), "text": texto, "session": self.session},
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
