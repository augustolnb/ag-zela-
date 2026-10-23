from datetime import datetime, timedelta

import httpx


class GoogleCalendarClient:
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    API_BASE = "https://www.googleapis.com/calendar/v3"
    FUSO_HORARIO = "America/Sao_Paulo"

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, calendar_id: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.calendar_id = calendar_id

    def _access_token(self) -> str:
        resposta = httpx.post(
            self.TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        resposta.raise_for_status()
        return resposta.json()["access_token"]

    def _payload_evento(self, titulo: str, local: str, data_hora: datetime, overrides_minutos: list[int]) -> dict:
        fim = data_hora + timedelta(hours=1)
        return {
            "summary": titulo,
            "location": local,
            "start": {"dateTime": data_hora.isoformat(), "timeZone": self.FUSO_HORARIO},
            "end": {"dateTime": fim.isoformat(), "timeZone": self.FUSO_HORARIO},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": m} for m in overrides_minutos],
            },
        }

    def criar_evento(self, titulo: str, local: str, data_hora: datetime, overrides_minutos: list[int]) -> str:
        token = self._access_token()
        resposta = httpx.post(
            f"{self.API_BASE}/calendars/{self.calendar_id}/events",
            json=self._payload_evento(titulo, local, data_hora, overrides_minutos),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resposta.raise_for_status()
        return resposta.json()["id"]

    def atualizar_evento(self, event_id: str, titulo: str, local: str, data_hora: datetime, overrides_minutos: list[int]) -> None:
        token = self._access_token()
        resposta = httpx.put(
            f"{self.API_BASE}/calendars/{self.calendar_id}/events/{event_id}",
            json=self._payload_evento(titulo, local, data_hora, overrides_minutos),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resposta.raise_for_status()

    def remover_evento(self, event_id: str) -> None:
        token = self._access_token()
        resposta = httpx.delete(
            f"{self.API_BASE}/calendars/{self.calendar_id}/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        # 404 significa que o evento já foi removido no Google Agenda: não é erro.
        if resposta.status_code != 404:
            resposta.raise_for_status()
