from fastapi.testclient import TestClient


def test_app_inclui_rota_de_webhook():
    from zela.api.main import app

    # NOTA: usamos app.openapi()["paths"] em vez de iterar app.routes
    # diretamente porque o FastAPI instalado (0.141.1) passou a armazenar
    # rotas incluídas via include_router() atrás de um wrapper preguiçoso
    # (_IncludedRouter), que não expõe mais `.path` como os objetos Route
    # de versões anteriores assumidas pelo brief original da task.
    caminhos = set(app.openapi()["paths"])
    assert "/webhook/whatsapp" in caminhos


def test_app_sobe_e_desce_com_lifespan(monkeypatch):
    class _AgendadorFalso:
        def shutdown(self):
            pass

    monkeypatch.setattr("zela.api.main.iniciar_scheduler", lambda *a, **k: _AgendadorFalso())

    from zela.api.main import app

    with TestClient(app) as cliente:
        resposta = cliente.get("/docs")
        assert resposta.status_code == 200
