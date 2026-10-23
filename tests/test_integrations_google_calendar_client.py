import httpx

from zela.integrations.google_calendar_client import GoogleCalendarClient


class _RespostaFalsa:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=self)

    def json(self):
        return self._json_data


def test_criar_evento_busca_token_e_envia_payload_correto(monkeypatch):
    from datetime import datetime

    chamadas = []

    def post_falso(url, data=None, json=None, headers=None, timeout=None):
        chamadas.append((url, data, json, headers))
        if url == GoogleCalendarClient.TOKEN_URL:
            return _RespostaFalsa({"access_token": "tok-123"})
        return _RespostaFalsa({"id": "evt-1"})

    monkeypatch.setattr(httpx, "post", post_falso)

    cliente = GoogleCalendarClient(
        client_id="cid", client_secret="csecret", refresh_token="rtok", calendar_id="fam@gmail.com"
    )
    event_id = cliente.criar_evento(
        titulo="Consulta", local="Clínica X",
        data_hora=datetime(2026, 11, 1, 9, 0), overrides_minutos=[1440, 60],
    )

    assert event_id == "evt-1"
    url_token, dados_token, _, _ = chamadas[0]
    assert url_token == GoogleCalendarClient.TOKEN_URL
    assert dados_token["refresh_token"] == "rtok"
    assert dados_token["grant_type"] == "refresh_token"

    url_evento, _, payload, headers = chamadas[1]
    assert url_evento == "https://www.googleapis.com/calendar/v3/calendars/fam@gmail.com/events"
    assert headers == {"Authorization": "Bearer tok-123"}
    assert payload["summary"] == "Consulta"
    assert payload["location"] == "Clínica X"
    assert payload["start"] == {"dateTime": "2026-11-01T09:00:00", "timeZone": "America/Sao_Paulo"}
    assert payload["reminders"] == {
        "useDefault": False,
        "overrides": [{"method": "popup", "minutes": 1440}, {"method": "popup", "minutes": 60}],
    }


def test_atualizar_evento_chama_put_no_id_correto(monkeypatch):
    from datetime import datetime

    chamadas_post, chamadas_put = [], []
    monkeypatch.setattr(httpx, "post", lambda url, **kw: (chamadas_post.append((url, kw)), _RespostaFalsa({"access_token": "tok-123"}))[1])

    def put_falso(url, json=None, headers=None, timeout=None):
        chamadas_put.append((url, json, headers))
        return _RespostaFalsa({})

    monkeypatch.setattr(httpx, "put", put_falso)

    cliente = GoogleCalendarClient(client_id="cid", client_secret="csecret", refresh_token="rtok", calendar_id="fam@gmail.com")
    cliente.atualizar_evento("evt-1", titulo="Consulta", local="Clínica X", data_hora=datetime(2026, 11, 1, 9, 0), overrides_minutos=[60])

    url, _, headers = chamadas_put[0]
    assert url == "https://www.googleapis.com/calendar/v3/calendars/fam@gmail.com/events/evt-1"
    assert headers == {"Authorization": "Bearer tok-123"}


def test_remover_evento_tolera_404(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _RespostaFalsa({"access_token": "tok-123"}))

    def delete_falso(url, headers=None, timeout=None):
        return _RespostaFalsa({}, status_code=404)

    monkeypatch.setattr(httpx, "delete", delete_falso)

    cliente = GoogleCalendarClient(client_id="cid", client_secret="csecret", refresh_token="rtok", calendar_id="fam@gmail.com")
    cliente.remover_evento("evt-ja-sumiu")  # não deve levantar
