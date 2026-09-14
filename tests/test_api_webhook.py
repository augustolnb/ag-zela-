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
