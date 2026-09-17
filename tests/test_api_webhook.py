# tests/test_api_webhook.py
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zela.api.webhook import montar_roteador


class _WahaFalso:
    def __init__(self):
        self.enviados = []

    def enviar_texto(self, telefone, texto):
        self.enviados.append((telefone, texto))
        return {"id": "msg-1"}


def test_webhook_processa_mensagem_e_envia_resposta():
    waha_falso = _WahaFalso()

    def processar_falso(id_idoso, texto, agora):
        assert id_idoso == "idosa-1"
        assert texto == "já tomei"
        return "Que bom! Confirmado."

    app = FastAPI()
    app.include_router(montar_roteador(processar_falso, waha_falso))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={
            "event": "message",
            "session": "default",
            "payload": {"from": "5511987654321@c.us", "body": "já tomei", "fromMe": False},
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "processado"}
    assert waha_falso.enviados == [("+5511987654321", "Que bom! Confirmado.")]


def test_webhook_ignora_payload_sem_remetente_ou_texto():
    waha_falso = _WahaFalso()
    app = FastAPI()
    app.include_router(montar_roteador(lambda *a: "nunca chamado", waha_falso))
    cliente = TestClient(app)

    resposta = cliente.post("/webhook/whatsapp", json={"event": "message", "payload": {}})

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ignorado"}
    assert waha_falso.enviados == []


def test_webhook_ignora_mensagem_propria_fromme():
    waha_falso = _WahaFalso()

    def processar_falso(*args):
        raise AssertionError("não deveria ser chamado para mensagem fromMe")

    app = FastAPI()
    app.include_router(montar_roteador(processar_falso, waha_falso))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={
            "event": "message",
            "payload": {"from": "5511987654321@c.us", "body": "oi", "fromMe": True},
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ignorado"}
    assert waha_falso.enviados == []


def test_webhook_ignora_numero_fora_da_lista_permitida():
    waha_falso = _WahaFalso()

    def processar_falso(*args):
        raise AssertionError("não deveria ser chamado para número não permitido")

    app = FastAPI()
    app.include_router(
        montar_roteador(processar_falso, waha_falso, telefones_permitidos=["+5511911111111"])
    )
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={
            "event": "message",
            "payload": {"from": "5511987654321@c.us", "body": "oi", "fromMe": False},
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ignorado"}
    assert waha_falso.enviados == []


def test_webhook_processa_numero_da_lista_permitida():
    waha_falso = _WahaFalso()

    def processar_falso(id_idoso, texto, agora):
        return "ok"

    app = FastAPI()
    app.include_router(
        montar_roteador(processar_falso, waha_falso, telefones_permitidos=["+5511911111111"])
    )
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={
            "event": "message",
            "payload": {"from": "5511911111111@c.us", "body": "oi", "fromMe": False},
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "processado"}
    assert waha_falso.enviados == [("+5511911111111", "ok")]


def test_webhook_aceita_numero_de_familiar_quando_ha_mais_de_um_permitido():
    waha_falso = _WahaFalso()

    def processar_falso(id_idoso, texto, agora):
        return "A vovó está bem hoje."

    app = FastAPI()
    app.include_router(
        montar_roteador(
            processar_falso, waha_falso,
            telefones_permitidos=["+5511911111111", "+5511987654321"],
        )
    )
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={
            "event": "message",
            "payload": {"from": "5511987654321@c.us", "body": "como ela está?", "fromMe": False},
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "processado"}
    assert waha_falso.enviados == [("+5511987654321", "A vovó está bem hoje.")]
