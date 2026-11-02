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

    def listar_documentos_de_bula(self, idoso_id: str) -> dict[str, str]:
        """Documento de bula → versão indexada."""
        resultado = self._colecao.get(
            where={"$and": [{"idoso_id": idoso_id}, {"tipo": "bula"}]}, include=["metadatas"]
        )
        return {m["documento"]: m.get("versao", "") for m in resultado["metadatas"] if m.get("documento")}

    def remover_documento(self, idoso_id: str, documento: str) -> None:
        self._colecao.delete(where={"$and": [{"idoso_id": idoso_id}, {"documento": documento}]})

    def substituir_documento(
        self, idoso_id: str, documento: str, trechos: list[str], embeddings: list[list[float]], versao: str
    ) -> None:
        self.remover_documento(idoso_id, documento)
        self._colecao.upsert(
            ids=[f"{documento}:{i}" for i in range(len(trechos))],
            embeddings=embeddings,
            documents=trechos,
            metadatas=[
                {"idoso_id": idoso_id, "tipo": "bula", "documento": documento, "versao": versao} for _ in trechos
            ],
        )

    def buscar_similares(self, idoso_id: str, embedding_consulta: list[float], k: int = 5) -> list[str]:
        resultado = self._colecao.query(
            query_embeddings=[embedding_consulta],
            n_results=k,
            where={"idoso_id": idoso_id},
        )
        documentos = resultado.get("documents") or []
        return documentos[0] if documentos else []
