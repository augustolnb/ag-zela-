import logging
from datetime import date, datetime

from zela.api.monitoramento_mensagem import processar_risco_mensagem
from zela.embeddings.exemplos_referencia import ExemploReferencia
from zela.models.monitoramento import StatusMonitoramento
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.storage.db import conectar
from zela.storage.escalonamento import obter_estado


class _WahaFalso:
    def __init__(self):
        self.enviados = []

    def enviar_texto(self, telefone, texto):
        self.enviados.append((telefone, texto))


class _ClienteEmbeddingFalso:
    def __init__(self, vetor):
        self._vetor = vetor

    def obter_embedding(self, texto: str) -> list[float]:
        return self._vetor


class _ClienteEmbeddingComFalha:
    def obter_embedding(self, texto: str) -> list[float]:
        raise RuntimeError("Gemini fora do ar")


class _RepositorioVetorialFalso:
    def __init__(self):
        self.indexados = []

    def indexar_documento(self, idoso_id, doc_id, texto, embedding, tipo):
        self.indexados.append((idoso_id, doc_id, texto, embedding, tipo))


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def _exemplos_com_embedding():
    exemplo_normal = ExemploReferencia(texto="Estou bem", status=StatusMonitoramento.NORMAL)
    exemplo_risco = ExemploReferencia(texto="Caí e não consigo levantar", status=StatusMonitoramento.RISCO)
    return [(exemplo_normal, [1.0, 0.0]), (exemplo_risco, [0.0, 1.0])]


def test_mensagem_de_risco_inicia_escalonamento_e_indexa_mensagem():
    conn = conectar(":memory:")
    waha_falso = _WahaFalso()
    repositorio_falso = _RepositorioVetorialFalso()
    agora = datetime(2026, 9, 17, 10, 0)

    processar_risco_mensagem(
        conn, "idosa-1", _perfil(), "caí no banheiro", agora,
        _ClienteEmbeddingFalso([0.0, 1.0]), _exemplos_com_embedding(),
        repositorio_falso, waha_falso,
    )

    estado = obter_estado(conn, "idosa-1")
    assert estado.estagio.value == "contato_idoso"
    assert waha_falso.enviados == [("+5511911111111", waha_falso.enviados[0][1])]
    assert len(repositorio_falso.indexados) == 1
    assert repositorio_falso.indexados[0][0] == "idosa-1"
    assert repositorio_falso.indexados[0][2] == "caí no banheiro"
    assert repositorio_falso.indexados[0][4] == "mensagem"


def test_mensagem_normal_nao_aciona_alerta():
    conn = conectar(":memory:")
    waha_falso = _WahaFalso()
    repositorio_falso = _RepositorioVetorialFalso()

    processar_risco_mensagem(
        conn, "idosa-1", _perfil(), "estou bem", datetime(2026, 9, 17, 10, 0),
        _ClienteEmbeddingFalso([1.0, 0.0]), _exemplos_com_embedding(),
        repositorio_falso, waha_falso,
    )

    assert waha_falso.enviados == []
    assert len(repositorio_falso.indexados) == 1


def test_falha_no_embedding_e_isolada_e_nao_levanta(caplog):
    conn = conectar(":memory:")
    waha_falso = _WahaFalso()
    repositorio_falso = _RepositorioVetorialFalso()

    with caplog.at_level(logging.ERROR):
        processar_risco_mensagem(
            conn, "idosa-1", _perfil(), "estou bem", datetime(2026, 9, 17, 10, 0),
            _ClienteEmbeddingComFalha(), _exemplos_com_embedding(),
            repositorio_falso, waha_falso,
        )

    assert waha_falso.enviados == []
    assert repositorio_falso.indexados == []
    assert "Gemini fora do ar" in caplog.text or "Falha ao processar" in caplog.text
