from datetime import time

from zela.api.reindexacao import reindexar_documentos
from zela.embeddings.vetorial import RepositorioVetorial
from zela.models.rotina import Dosagem, Medicamento
from zela.storage.db import conectar
from zela.storage.rotina import salvar_medicamento


class _ClienteEmbeddingFalso:
    def obter_embedding(self, texto: str) -> list[float]:
        return [float(len(texto)), 0.0]


def test_reindexar_documentos_indexa_apenas_medicamentos_com_bula(tmp_path):
    conn = conectar(":memory:")
    salvar_medicamento(
        conn,
        Medicamento(
            id="med-1", nome="Losartana",
            dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
            bula="Usado para pressão alta.",
        ),
        idoso_id="idosa-1",
    )
    salvar_medicamento(
        conn,
        Medicamento(
            id="med-2", nome="Vitamina D",
            dosagem=Dosagem(quantidade=1, unidade="comprimido"), horarios=[time(9, 0)],
        ),
        idoso_id="idosa-1",
    )
    repositorio = RepositorioVetorial(caminho=str(tmp_path / "chroma"))
    cliente_embedding = _ClienteEmbeddingFalso()

    quantidade = reindexar_documentos(conn, "idosa-1", repositorio, cliente_embedding)

    assert quantidade == 1
    texto_esperado = "Losartana: Usado para pressão alta."
    resultados = repositorio.buscar_similares(
        idoso_id="idosa-1",
        embedding_consulta=[float(len(texto_esperado)), 0.0],
        k=5,
    )
    assert texto_esperado in resultados


def test_reindexar_documentos_sem_nenhum_medicamento_com_bula_retorna_zero(tmp_path):
    conn = conectar(":memory:")
    salvar_medicamento(
        conn,
        Medicamento(
            id="med-3", nome="Vitamina C",
            dosagem=Dosagem(quantidade=1, unidade="comprimido"), horarios=[time(10, 0)],
        ),
        idoso_id="idosa-1",
    )
    repositorio = RepositorioVetorial(caminho=str(tmp_path / "chroma"))

    quantidade = reindexar_documentos(conn, "idosa-1", repositorio, _ClienteEmbeddingFalso())

    assert quantidade == 0
