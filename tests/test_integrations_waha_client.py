import httpx
import pytest

from zela.integrations.waha_client import WahaClient


class _RespostaFalsa:
    def __init__(self, json_data):
        self._json_data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


@pytest.fixture(autouse=True)
def _sem_consulta_real(monkeypatch):
    def get_indisponivel(*args, **kwargs):
        raise httpx.ConnectError("sem rede em teste")

    monkeypatch.setattr(httpx, "get", get_indisponivel)


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


def _get_falso(resposta, chamadas):
    def get_falso(url, params, headers, timeout):
        chamadas.append((url, params))
        return resposta

    return get_falso


def _post_capturando(enviados):
    def post_falso(url, json, headers, timeout):
        enviados.append(json["chatId"])
        return _RespostaFalsa({"id": "m"})

    return post_falso


def test_enviar_texto_usa_chat_id_resolvido_para_conta_com_lid(monkeypatch):
    enviados, consultas = [], []
    monkeypatch.setattr(httpx, "post", _post_capturando(enviados))
    monkeypatch.setattr(
        httpx, "get", _get_falso(_RespostaFalsa({"numberExists": True, "chatId": "123@lid"}), consultas)
    )

    cliente = WahaClient(base_url="http://waha")
    cliente.enviar_texto("+5563900000000", "a")
    cliente.enviar_texto("+5563900000000", "b")

    assert enviados == ["123@lid", "123@lid"]
    assert len(consultas) == 1
    assert consultas[0][1]["phone"] == "5563900000000"


def test_enviar_texto_com_jid_nao_consulta_waha(monkeypatch):
    enviados, consultas = [], []
    monkeypatch.setattr(httpx, "post", _post_capturando(enviados))
    monkeypatch.setattr(httpx, "get", _get_falso(_RespostaFalsa({}), consultas))

    WahaClient(base_url="http://waha").enviar_texto("123@lid", "a")

    assert enviados == ["123@lid"]
    assert consultas == []


def test_falha_na_consulta_usa_formato_antigo_sem_guardar_em_cache(monkeypatch):
    enviados = []
    monkeypatch.setattr(httpx, "post", _post_capturando(enviados))
    respostas = [httpx.ConnectError("fora"), _RespostaFalsa({"numberExists": True, "chatId": "9@lid"})]

    def get_instavel(url, params, headers, timeout):
        resposta = respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    monkeypatch.setattr(httpx, "get", get_instavel)

    cliente = WahaClient(base_url="http://waha")
    cliente.enviar_texto("+5563900000000", "a")
    cliente.enviar_texto("+5563900000000", "b")

    assert enviados == ["5563900000000@c.us", "9@lid"]


def test_numero_inexistente_usa_formato_antigo(monkeypatch):
    enviados = []
    monkeypatch.setattr(httpx, "post", _post_capturando(enviados))
    monkeypatch.setattr(httpx, "get", _get_falso(_RespostaFalsa({"numberExists": False, "chatId": None}), []))

    WahaClient(base_url="http://waha").enviar_texto("+5563900000000", "a")

    assert enviados == ["5563900000000@c.us"]
