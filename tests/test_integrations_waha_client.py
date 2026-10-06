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

    def post_falso(url, json, headers, timeout):
        chamadas.append((url, json, headers, timeout))
        return _RespostaFalsa({"id": "msg-1"})

    monkeypatch.setattr(httpx, "post", post_falso)

    cliente = WahaClient(base_url="http://localhost:3000")
    resultado = cliente.enviar_texto("+5511987654321", "Olá!")

    assert resultado == {"id": "msg-1"}
    url, payload, headers, _ = chamadas[0]
    assert url == "http://localhost:3000/api/sendText"
    assert payload["chatId"] == "5511987654321@c.us"
    assert payload["text"] == "Olá!"
    assert payload["session"] == "default"
    assert headers == {}


def test_enviar_audio_monta_payload_correto(monkeypatch):
    chamadas = []

    def post_falso(url, json, headers, timeout):
        chamadas.append((url, json, headers, timeout))
        return _RespostaFalsa({"id": "msg-2"})

    monkeypatch.setattr(httpx, "post", post_falso)

    cliente = WahaClient(base_url="http://localhost:3000")
    resultado = cliente.enviar_audio("+5511987654321", "YmFzZTY0", mimetype="audio/ogg")

    assert resultado == {"id": "msg-2"}
    url, payload, _, _ = chamadas[0]
    assert url == "http://localhost:3000/api/sendVoice"
    assert payload["file"]["data"] == "YmFzZTY0"
    assert payload["file"]["mimetype"] == "audio/ogg"


def test_enviar_texto_inclui_header_de_api_key_quando_configurada(monkeypatch):
    chamadas = []

    def post_falso(url, json, headers, timeout):
        chamadas.append((url, json, headers, timeout))
        return _RespostaFalsa({"id": "msg-4"})

    monkeypatch.setattr(httpx, "post", post_falso)

    cliente = WahaClient(base_url="http://localhost:3000", api_key="chave-secreta")
    cliente.enviar_texto("+5511987654321", "Olá!")

    _, _, headers, _ = chamadas[0]
    assert headers == {"X-Api-Key": "chave-secreta"}


def test_para_chat_id_remove_sinal_de_mais():
    assert WahaClient._para_chat_id("+5511987654321") == "5511987654321@c.us"


def test_para_chat_id_repassa_jid_lid_sem_reformatar():
    assert WahaClient._para_chat_id("109281332445239@lid") == "109281332445239@lid"


def test_enviar_texto_para_remetente_lid_nao_reformata_chat_id(monkeypatch):
    chamadas = []

    def post_falso(url, json, headers, timeout):
        chamadas.append((url, json, headers, timeout))
        return _RespostaFalsa({"id": "msg-3"})

    monkeypatch.setattr(httpx, "post", post_falso)

    cliente = WahaClient(base_url="http://localhost:3000")
    cliente.enviar_texto("109281332445239@lid", "Olá!")

    _, payload, _, _ = chamadas[0]
    assert payload["chatId"] == "109281332445239@lid"
