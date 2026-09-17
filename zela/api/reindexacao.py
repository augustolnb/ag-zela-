import sqlite3

from zela.storage.rotina import listar_medicamentos


def reindexar_documentos(
    conn: sqlite3.Connection,
    idoso_id: str,
    repositorio_vetorial,
    cliente_embedding,
) -> int:
    """Reindexa no vector store todos os medicamentos cadastrados que têm bula.

    Chamado no boot da API (zela/api/main.py, no ciclo de vida) para manter
    o RAG sincronizado com o que já está persistido no SQLite. Retorna a
    quantidade de documentos (re)indexados.
    """
    medicamentos_com_bula = [m for m in listar_medicamentos(conn, idoso_id) if m.bula]
    for medicamento in medicamentos_com_bula:
        texto = f"{medicamento.nome}: {medicamento.bula}"
        embedding = cliente_embedding.obter_embedding(texto)
        repositorio_vetorial.indexar_documento(
            idoso_id=idoso_id,
            doc_id=f"medicamento:{medicamento.id}",
            texto=texto,
            embedding=embedding,
            tipo="bula",
        )
    return len(medicamentos_com_bula)
