import chromadb
from chromadb.config import Settings

NOME_COLECAO_PADRAO = "conhecimento_zela"


class RepositorioVetorial:
    def __init__(self, caminho: str = "./chroma_db", nome_colecao: str = NOME_COLECAO_PADRAO):
        self._client = chromadb.PersistentClient(
            path=caminho, settings=Settings(anonymized_telemetry=False)
        )
        self._colecao = self._client.get_or_create_collection(name=nome_colecao)

    def indexar_documento(
        self, idoso_id: str, doc_id: str, texto: str, embedding: list[float], tipo: str
    ) -> None:
        self._colecao.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[texto],
            metadatas=[{"idoso_id": idoso_id, "tipo": tipo}],
        )

    def buscar_similares(self, idoso_id: str, embedding_consulta: list[float], k: int = 3) -> list[str]:
        resultado = self._colecao.query(
            query_embeddings=[embedding_consulta],
            n_results=k,
            where={"idoso_id": idoso_id},
        )
        documentos = resultado.get("documents") or []
        return documentos[0] if documentos else []
