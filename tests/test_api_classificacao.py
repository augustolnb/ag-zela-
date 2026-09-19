from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from zela.api.classificacao import montar_roteador_classificacao
from zela.embeddings.exemplos_referencia import ExemploReferencia
from zela.models.monitoramento import StatusMonitoramento


class _ClienteEmbeddingFalso:
    def __init__(self, vetor):
        self._vetor = vetor

    def obter_embedding(self, texto: str) -> list[float]:
        return self._vetor


class _ClienteEmbeddingComFalha:
    def obter_embedding(self, texto: str) -> list[float]:
        raise RuntimeError("Gemini fora do ar")


def _exemplos_com_embedding():
    exemplo_normal = ExemploReferencia(texto="Estou bem", status=StatusMonitoramento.NORMAL)
    exemplo_risco = ExemploReferencia(texto="Caí e não consigo levantar", status=StatusMonitoramento.RISCO)
    return [(exemplo_normal, [1.0, 0.0]), (exemplo_risco, [0.0, 1.0])]


def test_classificar_mensagem_retorna_status_e_motivo():
    app = FastAPI()
    app.include_router(
        montar_roteador_classificacao(_ClienteEmbeddingFalso([0.0, 1.0]), _exemplos_com_embedding)
    )
    cliente = TestClient(app)

    resposta = cliente.post("/api/classificar-mensagem", json={"texto": "caí no banheiro"})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "risco"
    assert "caí no banheiro" in corpo["motivo"]


def test_classificar_mensagem_corpo_invalido_retorna_400():
    app = FastAPI()
    app.include_router(
        montar_roteador_classificacao(_ClienteEmbeddingFalso([1.0, 0.0]), _exemplos_com_embedding)
    )
    cliente = TestClient(app)

    resposta = cliente.post("/api/classificar-mensagem", json={})

    assert resposta.status_code == 400


def test_classificar_mensagem_falha_de_embedding_retorna_503():
    app = FastAPI()
    app.include_router(
        montar_roteador_classificacao(_ClienteEmbeddingComFalha(), _exemplos_com_embedding)
    )
    cliente = TestClient(app)

    resposta = cliente.post("/api/classificar-mensagem", json={"texto": "oi"})

    assert resposta.status_code == 503
    assert "erro" in resposta.json()
