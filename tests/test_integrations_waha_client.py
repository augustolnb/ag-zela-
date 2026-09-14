import httpx

from zela.integrations.waha_client import WahaClient


class _RespostaFalsa:
    def __init__(self, json_data):
        self._json_data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def test_enviar_texto_monta_payload_correto(monkeypatch):
    chamadas = []

    def post_falso(url, json, timeout):
        chamadas.append((url, json, timeout))
        return _RespostaFalsa({"id": "msg-1"})

    monkeypatch.setattr(httpx, "post", post_falso)

    cliente = WahaClient(base_url="http://localhost:3000")
    resultado = cliente.enviar_texto("+5511987654321", "Olá!")

    assert resultado == {"id": "msg-1"}
    url, payload, _ = chamadas[0]
    assert url == "http://localhost:3000/api/sendText"
    assert payload["chatId"] == "5511987654321@c.us"
    assert payload["text"] == "Olá!"
    assert payload["session"] == "default"


def test_enviar_audio_monta_payload_correto(monkeypatch):
    chamadas = []

    def post_falso(url, json, timeout):
        chamadas.append((url, json, timeout))
        return _RespostaFalsa({"id": "msg-2"})

    monkeypatch.setattr(httpx, "post", post_falso)

    cliente = WahaClient(base_url="http://localhost:3000")
    resultado = cliente.enviar_audio("+5511987654321", "YmFzZTY0", mimetype="audio/ogg")

    assert resultado == {"id": "msg-2"}
    url, payload, _ = chamadas[0]
    assert url == "http://localhost:3000/api/sendVoice"
    assert payload["file"]["data"] == "YmFzZTY0"
    assert payload["file"]["mimetype"] == "audio/ogg"


def test_para_chat_id_remove_sinal_de_mais():
    assert WahaClient._para_chat_id("+5511987654321") == "5511987654321@c.us"
