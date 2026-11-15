import base64
import email
import email.policy

import httpx
import pytest

from zela.integrations.gmail_client import GmailClient
from zela.integrations.google_oauth import TOKEN_URL


class _RespostaFalsa:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=self)

    def json(self):
        return self._json_data


def _post_falso(chamadas, status_api=200):
    def post(url, data=None, json=None, headers=None, params=None, timeout=None):
        chamadas.append({"url": url, "data": data, "json": json, "headers": headers, "params": params})
        if url == TOKEN_URL:
            return _RespostaFalsa({"access_token": "tok-123"})
        return _RespostaFalsa({"id": "msg-1"}, status_code=status_api)

    return post


def _cliente(modo="insert"):
    return GmailClient(
        client_id="cid", client_secret="csecret", refresh_token="rtok", email="teste@gmail.com", modo=modo
    )


def _mensagem(raw):
    return email.message_from_bytes(base64.urlsafe_b64decode(raw), policy=email.policy.default)


def test_modo_insert_poe_na_caixa_de_entrada_como_nao_lida(monkeypatch):
    chamadas = []
    monkeypatch.setattr(httpx, "post", _post_falso(chamadas))

    id_mensagem = _cliente().notificar("Zela+: hora do remédio", "Dipirona 500mg")

    assert id_mensagem == "msg-1"
    assert chamadas[0]["url"] == TOKEN_URL
    assert chamadas[0]["data"]["refresh_token"] == "rtok"
    api = chamadas[1]
    assert api["url"] == "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    assert api["params"] == {"internalDateSource": "dateHeader"}
    assert api["json"]["labelIds"] == ["INBOX", "UNREAD"]
    assert api["headers"] == {"Authorization": "Bearer tok-123"}


def test_modo_send_usa_endpoint_de_envio(monkeypatch):
    chamadas = []
    monkeypatch.setattr(httpx, "post", _post_falso(chamadas))

    _cliente(modo="send").notificar("Zela+: hora do remédio", "Dipirona 500mg")

    api = chamadas[1]
    assert api["url"] == "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    assert "labelIds" not in api["json"]


def test_raw_decodifica_com_acentos_e_remetente_zela(monkeypatch):
    chamadas = []
    monkeypatch.setattr(httpx, "post", _post_falso(chamadas))

    _cliente().notificar("Zela+: hora do remédio", "Dipirona 500mg. Você já tomou?")

    mensagem = _mensagem(chamadas[1]["json"]["raw"])
    assert mensagem["Subject"] == "Zela+: hora do remédio"
    assert mensagem["To"] == "teste@gmail.com"
    assert mensagem["From"] == "Zela+ <teste@gmail.com>"
    assert mensagem["Date"] is not None
    assert "Você já tomou?" in mensagem.get_content()


def test_modo_invalido_falha_na_criacao():
    with pytest.raises(ValueError):
        _cliente(modo="smtp")


def test_atributos_publicos():
    cliente = _cliente(modo="send")
    assert cliente.modo == "send"
    assert cliente.email == "teste@gmail.com"


def test_erro_http_propaga(monkeypatch):
    monkeypatch.setattr(httpx, "post", _post_falso([], status_api=403))

    with pytest.raises(httpx.HTTPStatusError):
        _cliente().notificar("Zela+: hora do remédio", "x")
