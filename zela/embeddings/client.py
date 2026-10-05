from google import genai

MODELO_PADRAO = "gemini-embedding-2"


class ClienteEmbeddingGemini:
    def __init__(self, modelo: str = MODELO_PADRAO, cliente_sdk=None):
        self._modelo = modelo
        self._cliente_sdk_injetado = cliente_sdk
        self._cliente_sdk_lazy = None

    def _obter_cliente_sdk(self):
        if self._cliente_sdk_injetado is not None:
            return self._cliente_sdk_injetado
        if self._cliente_sdk_lazy is None:
            self._cliente_sdk_lazy = genai.Client()
        return self._cliente_sdk_lazy

    def obter_embedding(self, texto: str) -> list[float]:
        resposta = self._obter_cliente_sdk().models.embed_content(model=self._modelo, contents=texto)
        return list(resposta.embeddings[0].values)
