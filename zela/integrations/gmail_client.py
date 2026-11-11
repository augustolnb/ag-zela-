import base64
from email.message import EmailMessage
from email.utils import formatdate

import httpx

from zela.integrations.google_oauth import obter_access_token

MODOS = ("insert", "send")


class GmailClient:
    """Põe mensagens na caixa de entrada da conta logada no celular do idoso.

    O Mi Fitness espelha a notificação do Gmail na pulseira. Dois modos,
    porque um e-mail da conta para ela mesma pode não gerar notificação:
    - "insert": users.messages.insert, direto na caixa de entrada como não lida;
    - "send": users.messages.send, da conta para ela mesma.
    """

    API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, email: str, modo: str = "insert"):
        if modo not in MODOS:
            raise ValueError(f"modo do Gmail inválido: {modo!r} (use {' ou '.join(MODOS)})")
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.email = email
        self.modo = modo

    def _raw(self, assunto: str, corpo: str) -> str:
        mensagem = EmailMessage()
        mensagem["From"] = f"Zela+ <{self.email}>"
        mensagem["To"] = self.email
        mensagem["Subject"] = assunto
        mensagem["Date"] = formatdate(localtime=True)
        mensagem.set_content(corpo)
        return base64.urlsafe_b64encode(mensagem.as_bytes()).decode()

    def notificar(self, assunto: str, corpo: str) -> str:
        token = obter_access_token(self.client_id, self.client_secret, self.refresh_token)
        cabecalhos = {"Authorization": f"Bearer {token}"}
        if self.modo == "insert":
            resposta = httpx.post(
                self.API_BASE,
                json={"raw": self._raw(assunto, corpo), "labelIds": ["INBOX", "UNREAD"]},
                params={"internalDateSource": "dateHeader"},
                headers=cabecalhos,
                timeout=30,
            )
        else:
            resposta = httpx.post(
                f"{self.API_BASE}/send",
                json={"raw": self._raw(assunto, corpo)},
                headers=cabecalhos,
                timeout=30,
            )
        resposta.raise_for_status()
        return resposta.json()["id"]
