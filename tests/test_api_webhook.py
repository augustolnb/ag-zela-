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


def test_webhook_com_token_configurado_sem_header_retorna_401():
    waha_falso = _WahaFalso()

    def processar_falso(*args):
        raise AssertionError("não deveria ser chamado sem token válido")

    app = FastAPI()
    app.include_router(montar_roteador(processar_falso, waha_falso, token="segredo-waha"))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={"event": "message", "payload": {"from": "5511987654321@c.us", "body": "oi", "fromMe": False}},
    )

    assert resposta.status_code == 401
    assert waha_falso.enviados == []


def test_webhook_com_token_configurado_header_errado_retorna_401():
    waha_falso = _WahaFalso()

    def processar_falso(*args):
        raise AssertionError("não deveria ser chamado com token inválido")

    app = FastAPI()
    app.include_router(montar_roteador(processar_falso, waha_falso, token="segredo-waha"))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={"event": "message", "payload": {"from": "5511987654321@c.us", "body": "oi", "fromMe": False}},
        headers={"X-Api-Key": "errado"},
    )

    assert resposta.status_code == 401
    assert waha_falso.enviados == []


def test_webhook_com_token_configurado_header_correto_processa_normalmente():
    waha_falso = _WahaFalso()

    def processar_falso(id_idoso, texto, agora):
        return "ok"

    app = FastAPI()
    app.include_router(montar_roteador(processar_falso, waha_falso, token="segredo-waha"))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={"event": "message", "payload": {"from": "5511987654321@c.us", "body": "oi", "fromMe": False}},
        headers={"X-Api-Key": "segredo-waha"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "processado"}
    assert waha_falso.enviados == [("+5511987654321", "ok")]


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


def _corpo(texto):
    return {"payload": {"from": "5511987654321@c.us", "body": texto, "fromMe": False}}


def _cliente_emergencia(processar, waha, processar_emergencia, processar_risco=None):
    app = FastAPI()
    app.include_router(
        montar_roteador(processar, waha, processar_emergencia=processar_emergencia, processar_risco=processar_risco)
    )
    return TestClient(app)


def test_emergencia_responde_sem_chamar_llm_nem_risco():
    waha = _WahaFalso()

    def llm(*args):
        raise AssertionError("LLM não pode ser chamado")

    def risco(*args):
        raise AssertionError("risco não pode ser chamado")

    cliente = _cliente_emergencia(llm, waha, lambda t, x, a: "Você está bem?", risco)
    resposta = cliente.post("/webhook/whatsapp", json=_corpo("tontura"))

    assert resposta.json() == {"status": "emergencia"}
    assert waha.enviados == [("+5511987654321", "Você está bem?")]


def test_mensagem_comum_segue_para_llm():
    waha = _WahaFalso()
    cliente = _cliente_emergencia(lambda i, t, a: "oi", waha, lambda t, x, a: None)
    assert cliente.post("/webhook/whatsapp", json=_corpo("bom dia")).json() == {"status": "processado"}
    assert waha.enviados == [("+5511987654321", "oi")]


def test_falha_ao_confirmar_ao_paciente_nao_derruba_webhook():
    class _WahaQuebrado:
        def enviar_texto(self, telefone, texto):
            raise RuntimeError("falha")

    triagens = []

    def triar(telefone, texto, agora):
        triagens.append(texto)
        return "Você está bem?"

    cliente = _cliente_emergencia(lambda *a: "x", _WahaQuebrado(), triar)
    assert cliente.post("/webhook/whatsapp", json=_corpo("tontura")).json() == {"status": "emergencia"}
    assert triagens == ["tontura"]


def test_falha_na_triagem_nao_impede_resposta_do_llm():
    waha = _WahaFalso()

    def triar(telefone, texto, agora):
        raise RuntimeError("banco indisponível")

    cliente = _cliente_emergencia(lambda i, t, a: "oi", waha, triar)
    assert cliente.post("/webhook/whatsapp", json=_corpo("bom dia")).json() == {"status": "processado"}


def test_falha_do_llm_responde_mensagem_amigavel_sem_erro_500():
    waha = _WahaFalso()

    def llm_quebrado(id_idoso, texto, agora):
        raise RuntimeError("No module named 'mcp'")

    app = FastAPI()
    app.include_router(montar_roteador(llm_quebrado, waha))
    resposta = TestClient(app).post("/webhook/whatsapp", json=_corpo("bom dia"))

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "processado"}
    assert len(waha.enviados) == 1
    assert "192" in waha.enviados[0][1]


def test_falha_do_llm_nao_impede_avaliacao_de_risco():
    riscos = []

    def llm_quebrado(id_idoso, texto, agora):
        raise RuntimeError("fora do ar")

    app = FastAPI()
    app.include_router(
        montar_roteador(llm_quebrado, _WahaFalso(), processar_risco=lambda t, x, a: riscos.append(x))
    )
    TestClient(app).post("/webhook/whatsapp", json=_corpo("bom dia"))

    assert riscos == ["bom dia"]


# Votos de enquete — plano 2026-11-15-enquete-remedio, Task 5. Formato observado em produção.
_LID = "109281332445239@lid"


def _voto(selecionadas, de=_LID, from_me=False, evento="poll.vote"):
    return {
        "event": evento,
        "payload": {
            "vote": {
                "id": "v1", "to": "x@c.us", "from": de, "fromMe": from_me,
                "selectedOptions": selecionadas, "timestamp": 1794783590309,
            },
            "poll": {"id": "true_x@lid_ABC", "to": de, "from": "x@c.us", "fromMe": True},
        },
    }


def _cliente_voto(waha, processar_voto, lids_permitidos=None, processar=None):
    def llm(*args):
        raise AssertionError("LLM não pode ser chamado para votos")

    app = FastAPI()
    app.include_router(
        montar_roteador(
            processar or llm, waha, lids_permitidos=lids_permitidos, processar_voto=processar_voto,
            processar_emergencia=lambda *a: (_ for _ in ()).throw(AssertionError("triagem não vale para votos")),
        )
    )
    return TestClient(app)


def test_voto_chama_processar_voto_e_responde_quem_votou():
    waha, chamadas = _WahaFalso(), []

    def processar_voto(chave, selecionadas, agora):
        chamadas.append((chave, selecionadas))
        return "Anotado!"

    resposta = _cliente_voto(waha, processar_voto, lids_permitidos=[_LID]).post(
        "/webhook/whatsapp", json=_voto(["✅ Tomei"])
    )

    assert resposta.json() == {"status": "voto"}
    assert chamadas == [("true_x@lid_ABC", ["✅ Tomei"])]
    assert waha.enviados == [(_LID, "Anotado!")]


def test_voto_fora_da_lista_permitida_e_ignorado():
    waha = _WahaFalso()

    def processar_voto(*args):
        raise AssertionError("não pode ser chamado")

    resposta = _cliente_voto(waha, processar_voto, lids_permitidos=[_LID]).post(
        "/webhook/whatsapp", json=_voto(["✅ Tomei"], de="999@lid")
    )

    assert resposta.json() == {"status": "ignorado"}
    assert waha.enviados == []


def test_voto_proprio_e_ignorado():
    waha = _WahaFalso()
    resposta = _cliente_voto(waha, lambda *a: "x").post("/webhook/whatsapp", json=_voto(["✅ Tomei"], from_me=True))
    assert resposta.json() == {"status": "ignorado"}
    assert waha.enviados == []


def test_voto_falho_so_gera_log():
    waha = _WahaFalso()

    def processar_voto(*args):
        raise AssertionError("não pode ser chamado")

    resposta = _cliente_voto(waha, processar_voto).post(
        "/webhook/whatsapp", json=_voto([], evento="poll.vote.failed")
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ignorado"}
    assert waha.enviados == []


def test_voto_com_erro_no_callback_responde_200_sem_enviar():
    waha = _WahaFalso()

    def processar_voto(*args):
        raise RuntimeError("banco fora")

    resposta = _cliente_voto(waha, processar_voto).post("/webhook/whatsapp", json=_voto(["✅ Tomei"]))

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "voto"}
    assert waha.enviados == []


def test_voto_sem_resposta_nao_envia_nada():
    waha = _WahaFalso()
    resposta = _cliente_voto(waha, lambda *a: None).post("/webhook/whatsapp", json=_voto(["✅ Tomei"]))
    assert resposta.json() == {"status": "voto"}
    assert waha.enviados == []
