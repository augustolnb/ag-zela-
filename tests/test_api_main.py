from datetime import date, datetime

from fastapi.testclient import TestClient

import zela.api.main as main_module
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.storage.perfil import salvar_perfil


def test_app_inclui_rota_de_webhook():
    from zela.api.main import app

    # NOTA: usamos app.openapi()["paths"] em vez de iterar app.routes
    # diretamente porque o FastAPI instalado (0.141.1) passou a armazenar
    # rotas incluídas via include_router() atrás de um wrapper preguiçoso
    # (_IncludedRouter), que não expõe mais `.path` como os objetos Route
    # de versões anteriores assumidas pelo brief original da task.
    caminhos = set(app.openapi()["paths"])
    assert "/webhook/whatsapp" in caminhos
    assert "/ingest/esp32" in caminhos
    assert "/ingest/health-connect" in caminhos


def test_app_inclui_rota_de_classificacao():
    from zela.api.main import app

    caminhos = set(app.openapi()["paths"])
    assert "/api/classificar-mensagem" in caminhos


def test_app_sobe_e_desce_com_lifespan(monkeypatch):
    class _AgendadorFalso:
        def shutdown(self):
            pass

    monkeypatch.setattr("zela.api.main.iniciar_scheduler", lambda *a, **k: _AgendadorFalso())
    monkeypatch.setattr("zela.api.main.reindexar_documentos", lambda *a, **k: 0)

    from zela.api.main import app

    with TestClient(app) as cliente:
        resposta = cliente.get("/docs")
        assert resposta.status_code == 200


class _WahaFalsoMain:
    def __init__(self):
        self.enviados = []

    def enviar_texto(self, telefone, texto):
        self.enviados.append((telefone, texto))


class _ClienteEmbeddingFalsoMain:
    def obter_embedding(self, texto):
        return [1.0, 0.0]


class _RepositorioVetorialFalsoMain:
    def __init__(self):
        self.indexados = []

    def indexar_documento(self, idoso_id, doc_id, texto, embedding, tipo):
        self.indexados.append((idoso_id, doc_id, texto, embedding, tipo))


def _preparar_main_com_perfil(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr(main_module, "CAMINHO_DB", banco)
    conn = main_module.conectar(banco)
    salvar_perfil(
        conn,
        PerfilIdoso(
            nome="Maria", telefone="+5511911111111", data_nascimento=date(1945, 3, 12),
            contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
        ),
        idoso_id=main_module.ID_IDOSO,
    )
    monkeypatch.setattr(main_module, "cliente_embedding", _ClienteEmbeddingFalsoMain())
    monkeypatch.setattr(main_module, "_exemplos_com_embedding_cache", None)


def test_processar_risco_ignora_mensagem_de_familiar(monkeypatch, tmp_path):
    _preparar_main_com_perfil(monkeypatch, tmp_path)
    waha_falso = _WahaFalsoMain()
    repositorio_falso = _RepositorioVetorialFalsoMain()
    monkeypatch.setattr(main_module, "waha_client", waha_falso)
    monkeypatch.setattr(main_module, "repositorio_vetorial", repositorio_falso)

    # Número do familiar (João), não o do idoso: _processar_risco deve
    # retornar antes de calcular qualquer embedding.
    main_module._processar_risco("+5511987654321", "como ela está?", datetime(2026, 9, 17, 10, 0))

    assert waha_falso.enviados == []
    assert repositorio_falso.indexados == []


def test_processar_risco_processa_mensagem_do_idoso(monkeypatch, tmp_path):
    _preparar_main_com_perfil(monkeypatch, tmp_path)
    repositorio_falso = _RepositorioVetorialFalsoMain()
    monkeypatch.setattr(main_module, "waha_client", _WahaFalsoMain())
    monkeypatch.setattr(main_module, "repositorio_vetorial", repositorio_falso)

    # Número do próprio idoso: o fluxo completo deve rodar, incluindo a
    # indexação da mensagem no vector store (fake).
    main_module._processar_risco("+5511911111111", "estou bem", datetime(2026, 9, 17, 10, 0))

    assert len(repositorio_falso.indexados) == 1


def _preparar_main_com_perfil_lid(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste_lid.db")
    monkeypatch.setattr(main_module, "CAMINHO_DB", banco)
    conn = main_module.conectar(banco)
    salvar_perfil(
        conn,
        PerfilIdoso(
            nome="Maria", telefone="+5511911111111", data_nascimento=date(1945, 3, 12),
            contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
            lid_whatsapp="109281332445239@lid",
        ),
        idoso_id=main_module.ID_IDOSO,
    )
    monkeypatch.setattr(main_module, "cliente_embedding", _ClienteEmbeddingFalsoMain())
    monkeypatch.setattr(main_module, "_exemplos_com_embedding_cache", None)


def test_processar_risco_processa_mensagem_do_idoso_via_lid(monkeypatch, tmp_path):
    _preparar_main_com_perfil_lid(monkeypatch, tmp_path)
    repositorio_falso = _RepositorioVetorialFalsoMain()
    monkeypatch.setattr(main_module, "waha_client", _WahaFalsoMain())
    monkeypatch.setattr(main_module, "repositorio_vetorial", repositorio_falso)

    # Contato cujo WhatsApp usa LID (telefone real nunca é revelado pelo
    # WAHA): o fluxo completo deve rodar igual ao de um número normal.
    main_module._processar_risco("109281332445239@lid", "estou bem", datetime(2026, 9, 17, 10, 0))

    assert len(repositorio_falso.indexados) == 1


def test_obter_lids_permitidos_retorna_none_sem_lid_cadastrado(monkeypatch, tmp_path):
    _preparar_main_com_perfil(monkeypatch, tmp_path)
    assert main_module._obter_lids_permitidos() is None


def test_obter_lids_permitidos_retorna_lid_cadastrado(monkeypatch, tmp_path):
    _preparar_main_com_perfil_lid(monkeypatch, tmp_path)
    assert main_module._obter_lids_permitidos() == ["109281332445239@lid"]
