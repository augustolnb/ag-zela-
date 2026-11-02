import hashlib
import logging
import sqlite3
from collections.abc import Iterable

from zela.embeddings.bulas import Bula, dividir_em_trechos, trechos_de_bula
from zela.storage.rotina import listar_medicamentos

logger = logging.getLogger(__name__)


def _documentos_de_bula(conn, idoso_id: str, bulas: Iterable[Bula]) -> dict[str, list[str]]:
    documentos = {f"bula:{bula.id}": trechos_de_bula(bula) for bula in bulas}
    for medicamento in listar_medicamentos(conn, idoso_id):
        if medicamento.bula:
            documentos[f"medicamento:{medicamento.id}"] = dividir_em_trechos(f"{medicamento.nome}: {medicamento.bula}")
    return documentos


def reindexar_documentos(
    conn: sqlite3.Connection,
    idoso_id: str,
    repositorio_vetorial,
    cliente_embedding,
    bulas: Iterable[Bula] = (),
) -> int:
    """Sincroniza o vector store com o catálogo de bulas e as bulas cadastradas.

    Roda periodicamente porque o painel salva no SQLite e não tem acesso ao
    Chroma. Só gera embeddings do que mudou; se um documento falhar, a versão
    anterior continua valendo e a próxima execução tenta de novo. Retorna a
    quantidade de documentos (re)indexados.
    """
    documentos = _documentos_de_bula(conn, idoso_id, bulas)
    existentes = repositorio_vetorial.listar_documentos_de_bula(idoso_id)

    for documento in existentes.keys() - documentos.keys():
        repositorio_vetorial.remover_documento(idoso_id, documento)

    atualizados = 0
    for documento, trechos in documentos.items():
        versao = hashlib.sha256("\0".join(trechos).encode()).hexdigest()
        if existentes.get(documento) == versao:
            continue
        try:
            embeddings = [cliente_embedding.obter_embedding(trecho) for trecho in trechos]
        except Exception:
            logger.exception("Falha ao gerar embeddings de %s; nova tentativa na próxima execução", documento)
            continue
        repositorio_vetorial.substituir_documento(idoso_id, documento, trechos, embeddings, versao)
        atualizados += 1
    return atualizados
