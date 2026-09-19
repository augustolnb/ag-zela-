import json
from pathlib import Path

CAMINHO_WORKFLOW = Path(__file__).parent.parent / "docs" / "n8n" / "zela-classificacao-mensagem.json"


def _carregar_workflow():
    with open(CAMINHO_WORKFLOW, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def test_workflow_e_json_valido_com_nos_esperados():
    workflow = _carregar_workflow()

    nomes_dos_nos = {no["name"] for no in workflow["nodes"]}
    assert nomes_dos_nos == {
        "Webhook",
        "HTTP Request",
        "If: risco?",
        "If: atencao?",
        "Responder: alertar familia",
        "Responder: verificar idosa",
        "Responder: normal",
    }


def test_workflow_usa_os_tipos_de_no_verificados():
    workflow = _carregar_workflow()
    tipos_por_nome = {no["name"]: (no["type"], no["typeVersion"]) for no in workflow["nodes"]}

    assert tipos_por_nome["Webhook"] == ("n8n-nodes-base.webhook", 1.1)
    assert tipos_por_nome["HTTP Request"] == ("n8n-nodes-base.httpRequest", 4.2)
    assert tipos_por_nome["If: risco?"] == ("n8n-nodes-base.if", 2)
    assert tipos_por_nome["If: atencao?"] == ("n8n-nodes-base.if", 2)
    for nome_resposta in ("Responder: alertar familia", "Responder: verificar idosa", "Responder: normal"):
        assert tipos_por_nome[nome_resposta] == ("n8n-nodes-base.respondToWebhook", 1.1)


def test_workflow_webhook_espera_post_e_responde_via_no_dedicado():
    workflow = _carregar_workflow()
    webhook = next(no for no in workflow["nodes"] if no["name"] == "Webhook")

    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["responseMode"] == "responseNode"


def test_workflow_conexoes_ligam_os_nos_na_ordem_esperada():
    workflow = _carregar_workflow()
    conexoes = workflow["connections"]

    def destino(nome_origem):
        return conexoes[nome_origem]["main"][0][0]["node"]

    assert destino("Webhook") == "HTTP Request"
    assert destino("HTTP Request") == "If: risco?"

    saidas_risco = conexoes["If: risco?"]["main"]
    assert saidas_risco[0][0]["node"] == "Responder: alertar familia"
    assert saidas_risco[1][0]["node"] == "If: atencao?"

    saidas_atencao = conexoes["If: atencao?"]["main"]
    assert saidas_atencao[0][0]["node"] == "Responder: verificar idosa"
    assert saidas_atencao[1][0]["node"] == "Responder: normal"
