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


def test_webhook_chama_processar_risco_quando_fornecido():
    waha_falso = _WahaFalso()
    chamadas_risco = []

    def processar_falso(id_idoso, texto, agora):
        return "ok"

    def processar_risco_falso(telefone, texto, agora):
        chamadas_risco.append((telefone, texto))

    app = FastAPI()
    app.include_router(
        montar_roteador(processar_falso, waha_falso, processar_risco=processar_risco_falso)
    )
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={
            "event": "message",
            "payload": {"from": "5511987654321@c.us", "body": "caí no banheiro", "fromMe": False},
        },
    )

    assert resposta.status_code == 200
    assert chamadas_risco == [("+5511987654321", "caí no banheiro")]


def test_webhook_nao_falha_quando_processar_risco_nao_e_fornecido():
    waha_falso = _WahaFalso()

    def processar_falso(id_idoso, texto, agora):
        return "ok"

    app = FastAPI()
    app.include_router(montar_roteador(processar_falso, waha_falso))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={"event": "message", "payload": {"from": "5511987654321@c.us", "body": "oi", "fromMe": False}},
    )

    assert resposta.status_code == 200


def test_webhook_ignora_lid_fora_da_lista_permitida():
    waha_falso = _WahaFalso()

    def processar_falso(*args):
        raise AssertionError("não deveria ser chamado para LID não permitido")

    app = FastAPI()
    app.include_router(
        montar_roteador(processar_falso, waha_falso, lids_permitidos=["999999999999999@lid"])
    )
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={
            "event": "message",
            "payload": {"from": "109281332445239@lid", "body": "tomei o remedio", "fromMe": False},
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ignorado"}
    assert waha_falso.enviados == []


def test_webhook_processa_lid_da_lista_permitida_e_responde_para_o_mesmo_jid():
    waha_falso = _WahaFalso()

    def processar_falso(id_idoso, texto, agora):
        return "Que bom! Confirmado."

    app = FastAPI()
    app.include_router(
        montar_roteador(
            processar_falso, waha_falso, lids_permitidos=["109281332445239@lid"]
        )
    )
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={
            "event": "message",
            "payload": {"from": "109281332445239@lid", "body": "tomei o remedio", "fromMe": False},
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "processado"}
    assert waha_falso.enviados == [("109281332445239@lid", "Que bom! Confirmado.")]


def test_webhook_aceita_lid_quando_lista_de_lid_nao_e_configurada():
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
            "payload": {"from": "109281332445239@lid", "body": "oi", "fromMe": False},
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "processado"}
    assert waha_falso.enviados == [("109281332445239@lid", "ok")]


def test_webhook_nao_falha_quando_processar_risco_levanta_excecao():
    waha_falso = _WahaFalso()

    def processar_falso(id_idoso, texto, agora):
        return "ok"

    def processar_risco_com_falha(telefone, texto, agora):
        raise RuntimeError("Gemini fora do ar")

    app = FastAPI()
    app.include_router(
        montar_roteador(processar_falso, waha_falso, processar_risco=processar_risco_com_falha)
    )
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={"event": "message", "payload": {"from": "5511987654321@c.us", "body": "oi", "fromMe": False}},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "processado"}
