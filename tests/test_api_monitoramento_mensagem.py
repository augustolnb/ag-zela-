import logging
from datetime import date, datetime

from zela.api.monitoramento_mensagem import processar_risco_mensagem
from zela.embeddings.exemplos_referencia import ExemploReferencia
from zela.models.monitoramento import StatusMonitoramento
from zela.domain.emergencia import EstadoEscalonamento, EstagioEscalonamento
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.storage.alertas import listar_alertas
from zela.storage.db import conectar
from zela.storage.escalonamento import obter_estado, salvar_estado


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


def test_mensagem_de_risco_so_registra_no_painel_sem_escalar_nem_enviar():
    conn = conectar(":memory:")
    repositorio_falso = _RepositorioVetorialFalso()

    processar_risco_mensagem(
        conn, "idosa-1", _perfil(), "esqueci o remédio", datetime(2026, 9, 17, 10, 0),
        _ClienteEmbeddingFalso([0.0, 1.0]), _exemplos_com_embedding(), repositorio_falso,
    )

    assert obter_estado(conn, "idosa-1").estagio.value == "ocioso"
    alertas = listar_alertas(conn, "idosa-1")
    assert len(alertas) == 1
    assert alertas[0].canal.value == "streamlit"
    assert "esqueci o remédio" in alertas[0].mensagem
    assert repositorio_falso.indexados[0][2] == "esqueci o remédio"
    assert repositorio_falso.indexados[0][4] == "mensagem"


def test_mensagem_normal_nao_aciona_alerta():
    conn = conectar(":memory:")
    repositorio_falso = _RepositorioVetorialFalso()

    processar_risco_mensagem(
        conn, "idosa-1", _perfil(), "estou bem", datetime(2026, 9, 17, 10, 0),
        _ClienteEmbeddingFalso([1.0, 0.0]), _exemplos_com_embedding(),
        repositorio_falso,
    )

    assert listar_alertas(conn, "idosa-1") == []
    assert len(repositorio_falso.indexados) == 1


def test_falha_no_embedding_e_isolada_e_nao_levanta(caplog):
    conn = conectar(":memory:")
    repositorio_falso = _RepositorioVetorialFalso()

    with caplog.at_level(logging.ERROR):
        processar_risco_mensagem(
            conn, "idosa-1", _perfil(), "estou bem", datetime(2026, 9, 17, 10, 0),
            _ClienteEmbeddingComFalha(), _exemplos_com_embedding(),
            repositorio_falso,
        )

    assert listar_alertas(conn, "idosa-1") == []
    assert repositorio_falso.indexados == []
    assert "Gemini fora do ar" in caplog.text or "Falha ao processar" in caplog.text


def test_mensagem_normal_ainda_encerra_escalada_aberta_pelos_sensores():
    conn = conectar(":memory:")
    salvar_estado(
        conn, "idosa-1",
        EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=datetime(2026, 9, 17, 9, 55)),
    )

    processar_risco_mensagem(
        conn, "idosa-1", _perfil(), "estou bem", datetime(2026, 9, 17, 10, 0),
        _ClienteEmbeddingFalso([1.0, 0.0]), _exemplos_com_embedding(), _RepositorioVetorialFalso(),
    )

    assert obter_estado(conn, "idosa-1").estagio.value == "resolvido"


def test_mensagem_de_risco_nao_altera_escalada_aberta_pelos_sensores():
    conn = conectar(":memory:")
    inicio = datetime(2026, 9, 17, 9, 55)
    salvar_estado(conn, "idosa-1", EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=inicio))

    processar_risco_mensagem(
        conn, "idosa-1", _perfil(), "esqueci o remédio", datetime(2026, 9, 17, 10, 0),
        _ClienteEmbeddingFalso([0.0, 1.0]), _exemplos_com_embedding(), _RepositorioVetorialFalso(),
    )

    estado = obter_estado(conn, "idosa-1")
    assert estado.estagio.value == "contato_idoso" and estado.iniciado_em == inicio
