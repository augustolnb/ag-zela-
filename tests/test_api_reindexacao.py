from datetime import time

from zela.api.reindexacao import reindexar_documentos
from zela.embeddings.bulas import Bula
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


class _EmbeddingContando(_ClienteEmbeddingFalso):
    def __init__(self):
        self.chamadas = 0
        self.falhar = False

    def obter_embedding(self, texto):
        if self.falhar:
            raise RuntimeError("limite de requisições")
        self.chamadas += 1
        return super().obter_embedding(texto)


def _bula_catalogo(texto="## USO\n\nTrata dor."):
    return Bula(id="dor", nome="Remedio", laboratorio="Lab", registro="1", aprovada_em="01/01/2025", fonte="u", texto=texto)


def _med(bula):
    return Medicamento(
        id="med-1", nome="Losartana", dosagem=Dosagem(quantidade=50, unidade="mg"),
        horarios=[time(8, 0)], bula=bula,
    )


def _busca(repo):
    return repo.buscar_similares(idoso_id="idosa-1", embedding_consulta=[1.0, 0.0], k=50)


def test_catalogo_e_indexado_e_nao_gasta_embedding_se_nada_mudou(tmp_path):
    conn = conectar(":memory:")
    repo = RepositorioVetorial(caminho=str(tmp_path / "c"))
    emb = _EmbeddingContando()

    assert reindexar_documentos(conn, "idosa-1", repo, emb, bulas=[_bula_catalogo()]) == 1
    assert any("Trata dor." in t for t in _busca(repo))
    chamadas = emb.chamadas

    assert reindexar_documentos(conn, "idosa-1", repo, emb, bulas=[_bula_catalogo()]) == 0
    assert emb.chamadas == chamadas


def test_bula_alterada_substitui_trechos_antigos(tmp_path):
    conn = conectar(":memory:")
    repo = RepositorioVetorial(caminho=str(tmp_path / "c"))
    emb = _EmbeddingContando()
    salvar_medicamento(conn, _med("Versão antiga."), idoso_id="idosa-1")
    reindexar_documentos(conn, "idosa-1", repo, emb)

    salvar_medicamento(conn, _med("Versão nova."), idoso_id="idosa-1")
    assert reindexar_documentos(conn, "idosa-1", repo, emb) == 1

    textos = " ".join(_busca(repo))
    assert "Versão nova." in textos and "Versão antiga." not in textos


def test_bula_removida_sai_do_indice_e_mensagens_ficam(tmp_path):
    conn = conectar(":memory:")
    repo = RepositorioVetorial(caminho=str(tmp_path / "c"))
    emb = _EmbeddingContando()
    repo.indexar_documento("idosa-1", "mensagem:1", "disse bom dia", [1.0, 0.0], "mensagem")
    salvar_medicamento(conn, _med("Texto da bula."), idoso_id="idosa-1")
    reindexar_documentos(conn, "idosa-1", repo, emb)

    salvar_medicamento(conn, _med(None), idoso_id="idosa-1")
    reindexar_documentos(conn, "idosa-1", repo, emb)

    assert _busca(repo) == ["disse bom dia"]


def test_falha_de_embedding_mantem_versao_antiga_e_tenta_de_novo(tmp_path):
    conn = conectar(":memory:")
    repo = RepositorioVetorial(caminho=str(tmp_path / "c"))
    emb = _EmbeddingContando()
    reindexar_documentos(conn, "idosa-1", repo, emb, bulas=[_bula_catalogo("## USO\n\nAntiga.")])

    emb.falhar = True
    nova = _bula_catalogo("## USO\n\nNova.")
    assert reindexar_documentos(conn, "idosa-1", repo, emb, bulas=[nova]) == 0
    assert any("Antiga." in t for t in _busca(repo))

    emb.falhar = False
    assert reindexar_documentos(conn, "idosa-1", repo, emb, bulas=[nova]) == 1
    assert any("Nova." in t for t in _busca(repo))
