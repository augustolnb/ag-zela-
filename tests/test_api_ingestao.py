from fastapi import FastAPI
from fastapi.testclient import TestClient

from zela.api.ingestao import montar_roteador_ingestao
from zela.models.monitoramento import FonteSensor, TipoLeitura
from zela.storage.db import conectar
from zela.storage.monitoramento import salvar_leitura as salvar_leitura_real


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
        json={
            "heart_rate": [
                {"time": "2026-09-16T10:00:00-03:00", "bpm": 72, "avg": 72, "min": 72, "max": 72}
            ]
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "recebido", "leituras_salvas": 1, "leituras_descartadas": 0}
    leitura, idoso_id = armazenamento.salvas[0]
    assert leitura.fonte == FonteSensor.SMARTWATCH
    assert leitura.tipo == TipoLeitura.FREQUENCIA_CARDIACA
    assert leitura.valor == 72
    assert leitura.unidade == "bpm"
    assert idoso_id == "idosa-1"


def test_ingest_health_connect_salva_varias_leituras_de_frequencia_cardiaca_num_unico_payload():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/health-connect",
        json={
            "heart_rate": [
                {"time": "2026-09-16T10:00:00-03:00", "bpm": 72},
                {"time": "2026-09-16T10:10:00-03:00", "bpm": 75},
                {"time": "2026-09-16T10:20:00-03:00", "bpm": 71},
            ]
        },
    )

    assert resposta.status_code == 200
    assert resposta.json()["leituras_salvas"] == 3
    assert len(armazenamento.salvas) == 3


def test_ingest_health_connect_salva_passos():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/health-connect",
        json={
            "steps": [
                {
                    "count": 1359,
                    "start_time": "2026-09-16T00:00:00-03:00",
                    "end_time": "2026-09-16T13:37:37-03:00",
                }
            ]
        },
    )

    assert resposta.status_code == 200
    leitura, _ = armazenamento.salvas[0]
    assert leitura.tipo == TipoLeitura.PASSOS
    assert leitura.valor == 1359
    assert leitura.unidade == "passos"


def test_ingest_health_connect_salva_sono_como_horas():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/health-connect",
        json={
            "sleep": [
                {
                    "session_end_time": "2026-09-16T07:41:00-03:00",
                    "duration_seconds": 23820,
                    "stages": [
                        {"stage": "4", "start_time": "2026-09-16T01:04:00-03:00",
                         "end_time": "2026-09-16T01:29:00-03:00", "duration_seconds": 1500}
                    ],
                }
            ]
        },
    )

    assert resposta.status_code == 200
    leitura, _ = armazenamento.salvas[0]
    assert leitura.tipo == TipoLeitura.SONO
    assert leitura.valor == 23820 / 3600
    assert leitura.unidade == "horas"


def test_ingest_health_connect_item_invalido_e_descartado_sem_derrubar_o_lote():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/health-connect",
        json={
            "heart_rate": [
                {"time": "2026-09-16T10:00:00-03:00", "bpm": 72},
                {"time": "nao-e-uma-data", "bpm": 71},
                {"time": "2026-09-16T10:20:00-03:00"},
            ]
        },
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["leituras_salvas"] == 1
    assert corpo["leituras_descartadas"] == 2
    assert len(armazenamento.salvas) == 1


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
        json={"heart_rate": [{"time": "2026-09-16T10:00:00-03:00", "bpm": "nao-e-numero"}]},
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
        json={"heart_rate": [{"time": "2099-01-01T00:00:00-03:00", "bpm": 72}]},
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
        json={"heart_rate": [{"time": "nao-e-uma-data", "bpm": 72}]},
    )

    assert resposta.status_code == 400
    assert armazenamento.salvas == []


def test_ingest_esp32_com_token_configurado_sem_header_retorna_401():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar, token="segredo"))
    cliente = TestClient(app)

    resposta = cliente.post("/ingest/esp32", json={"valor": 1, "timestamp": "2026-09-16T10:00:00"})

    assert resposta.status_code == 401
    assert armazenamento.salvas == []


def test_ingest_esp32_com_token_configurado_header_errado_retorna_401():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar, token="segredo"))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/esp32",
        json={"valor": 1, "timestamp": "2026-09-16T10:00:00"},
        headers={"X-Api-Key": "errado"},
    )

    assert resposta.status_code == 401
    assert armazenamento.salvas == []


def test_ingest_esp32_com_token_configurado_header_correto_retorna_200():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar, token="segredo"))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/esp32",
        json={"valor": 1, "timestamp": "2026-09-16T10:00:00"},
        headers={"X-Api-Key": "segredo"},
    )

    assert resposta.status_code == 200
    assert len(armazenamento.salvas) == 1


def test_ingest_health_connect_com_token_configurado_sem_header_retorna_401():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar, token="segredo"))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/health-connect",
        json={"heart_rate": [{"time": "2026-09-16T10:00:00-03:00", "bpm": 72}]},
    )

    assert resposta.status_code == 401
    assert armazenamento.salvas == []


def test_ingest_health_connect_com_token_configurado_header_correto_retorna_200():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar, token="segredo"))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/health-connect",
        json={"heart_rate": [{"time": "2026-09-16T10:00:00-03:00", "bpm": 72}]},
        headers={"X-Api-Key": "segredo"},
    )

    assert resposta.status_code == 200
    assert len(armazenamento.salvas) == 1


def _cliente_esp32():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    return TestClient(app), armazenamento


def test_esp32_sinal_de_vida_grava_tipo_proprio():
    cliente, armazenamento = _cliente_esp32()

    resposta = cliente.post(
        "/ingest/esp32",
        json={"tipo": "sinal_de_vida", "valor": 1, "timestamp": "2026-09-16T10:00:00"},
    )

    assert resposta.status_code == 200
    leitura, _ = armazenamento.salvas[0]
    assert leitura.tipo == TipoLeitura.SINAL_DE_VIDA
    assert leitura.unidade == "sinal"


def test_esp32_sem_tipo_continua_presenca():
    cliente, armazenamento = _cliente_esp32()

    cliente.post("/ingest/esp32", json={"valor": 1, "timestamp": "2026-09-16T10:00:00"})

    assert armazenamento.salvas[0][0].tipo == TipoLeitura.PRESENCA


def test_esp32_tipo_desconhecido_retorna_400():
    cliente, armazenamento = _cliente_esp32()

    resposta = cliente.post(
        "/ingest/esp32",
        json={"tipo": "temperatura", "valor": 1, "timestamp": "2026-09-16T10:00:00"},
    )

    assert resposta.status_code == 400
    assert armazenamento.salvas == []


def test_health_connect_conta_so_leituras_novas_como_salvas(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    conn.close()
    caminho = str(tmp_path / "t.db")

    def salvar(leitura, idoso_id):
        return salvar_leitura_real(conectar(caminho), leitura, idoso_id)

    app = FastAPI()
    app.include_router(montar_roteador_ingestao(salvar))
    cliente = TestClient(app)
    corpo = {"heart_rate": [{"bpm": 80, "time": "2026-10-31T16:50:00-03:00"}]}

    assert cliente.post("/ingest/health-connect", json=corpo).json()["leituras_salvas"] == 1
    assert cliente.post("/ingest/health-connect", json=corpo).json()["leituras_salvas"] == 0
