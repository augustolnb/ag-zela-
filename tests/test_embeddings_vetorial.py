from zela.embeddings.vetorial import RepositorioVetorial


def test_buscar_similares_filtra_por_idoso(tmp_path):
    repo = RepositorioVetorial(caminho=str(tmp_path / "chroma"))
    repo.indexar_documento(
        idoso_id="idosa-1", doc_id="doc-a", texto="bula da losartana",
        embedding=[1.0, 0.0], tipo="bula",
    )
    repo.indexar_documento(
        idoso_id="idosa-2", doc_id="doc-b", texto="bula de outro idoso",
        embedding=[1.0, 0.0], tipo="bula",
    )

    resultados = repo.buscar_similares(idoso_id="idosa-1", embedding_consulta=[1.0, 0.0], k=5)

    assert resultados == ["bula da losartana"]


def test_indexar_documento_e_idempotente_por_id(tmp_path):
    repo = RepositorioVetorial(caminho=str(tmp_path / "chroma"))
    repo.indexar_documento(
        idoso_id="idosa-1", doc_id="doc-a", texto="versão antiga",
        embedding=[1.0, 0.0], tipo="bula",
    )
    repo.indexar_documento(
        idoso_id="idosa-1", doc_id="doc-a", texto="versão nova",
        embedding=[1.0, 0.0], tipo="bula",
    )

    resultados = repo.buscar_similares(idoso_id="idosa-1", embedding_consulta=[1.0, 0.0], k=5)

    assert resultados == ["versão nova"]


def test_buscar_similares_sem_documentos_retorna_lista_vazia(tmp_path):
    repo = RepositorioVetorial(caminho=str(tmp_path / "chroma"))

    resultados = repo.buscar_similares(idoso_id="idosa-1", embedding_consulta=[1.0, 0.0], k=5)

    assert resultados == []


def test_buscar_similares_respeita_k(tmp_path):
    repo = RepositorioVetorial(caminho=str(tmp_path / "chroma"))
    for i in range(5):
        repo.indexar_documento(
            idoso_id="idosa-1", doc_id=f"doc-{i}", texto=f"mensagem {i}",
            embedding=[1.0, 0.0], tipo="mensagem",
        )

    resultados = repo.buscar_similares(idoso_id="idosa-1", embedding_consulta=[1.0, 0.0], k=2)

    assert len(resultados) == 2
