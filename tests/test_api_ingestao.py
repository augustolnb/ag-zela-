from fastapi import FastAPI
from fastapi.testclient import TestClient

from zela.api.ingestao import montar_roteador_ingestao
from zela.models.monitoramento import FonteSensor, TipoLeitura


class _ArmazenamentoFalso:
    def __init__(self):
        self.salvas = []

    def salvar(self, leitura, idoso_id):
        self.salvas.append((leitura, idoso_id))


def test_ingest_esp32_salva_leitura_de_presenca():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post("/ingest/esp32", json={"valor": 1, "timestamp": "2026-09-16T10:00:00"})

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "recebido"}
    assert len(armazenamento.salvas) == 1
    leitura, idoso_id = armazenamento.salvas[0]
    assert leitura.fonte == FonteSensor.ESP32
    assert leitura.tipo == TipoLeitura.PRESENCA
    assert leitura.valor == 1
    assert idoso_id == "idosa-1"


def test_ingest_esp32_payload_invalido_retorna_400():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post("/ingest/esp32", json={"timestamp": "nao-e-uma-data"})

    assert resposta.status_code == 400
    assert armazenamento.salvas == []


def test_ingest_health_connect_salva_leitura_de_frequencia_cardiaca():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/health-connect",
        json={"value": 72, "unit": "bpm", "timestamp": "2026-09-16T10:00:00"},
    )

    assert resposta.status_code == 200
    leitura, idoso_id = armazenamento.salvas[0]
    assert leitura.fonte == FonteSensor.SMARTWATCH
    assert leitura.tipo == TipoLeitura.FREQUENCIA_CARDIACA
    assert leitura.valor == 72
    assert leitura.unidade == "bpm"


def test_ingest_health_connect_payload_invalido_retorna_400():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post("/ingest/health-connect", json={})

    assert resposta.status_code == 400
    assert armazenamento.salvas == []


def test_ingest_esp32_valor_com_tipo_errado_retorna_400():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/esp32", json={"valor": "abc", "timestamp": "2026-09-16T10:00:00"}
    )

    assert resposta.status_code == 400
    assert armazenamento.salvas == []


def test_ingest_esp32_timestamp_invalido_retorna_400():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post("/ingest/esp32", json={"valor": 1, "timestamp": "nao-e-uma-data"})

    assert resposta.status_code == 400
    assert armazenamento.salvas == []


def test_ingest_health_connect_value_com_tipo_errado_retorna_400():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/health-connect",
        json={"value": {"bpm": 72}, "unit": "bpm", "timestamp": "2026-09-16T10:00:00"},
    )

    assert resposta.status_code == 400
    assert armazenamento.salvas == []


def test_ingest_esp32_timestamp_no_futuro_retorna_400():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/esp32", json={"valor": 1, "timestamp": "2099-01-01T00:00:00"}
    )

    assert resposta.status_code == 400
    assert armazenamento.salvas == []


def test_ingest_health_connect_timestamp_no_futuro_retorna_400():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/health-connect",
        json={"value": 72, "unit": "bpm", "timestamp": "2099-01-01T00:00:00"},
    )

    assert resposta.status_code == 400
    assert armazenamento.salvas == []


def test_ingest_health_connect_timestamp_invalido_retorna_400():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/health-connect",
        json={"value": 72, "unit": "bpm", "timestamp": "nao-e-uma-data"},
    )

    assert resposta.status_code == 400
    assert armazenamento.salvas == []
