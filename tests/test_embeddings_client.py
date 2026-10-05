from zela.embeddings.client import ClienteEmbeddingGemini


class _EmbeddingFalso:
    def __init__(self, values):
        self.values = values


class _RespostaFalsa:
    def __init__(self, values):
        self.embeddings = [_EmbeddingFalso(values)]


class _ModelsFalso:
    def __init__(self, values):
        self._values = values
        self.chamadas = []

    def embed_content(self, model, contents):
        self.chamadas.append((model, contents))
        return _RespostaFalsa(self._values)


class _ClienteSdkFalso:
    def __init__(self, values):
        self.models = _ModelsFalso(values)


def test_obter_embedding_usa_o_sdk_injetado():
    sdk_falso = _ClienteSdkFalso([0.1, 0.2, 0.3])
    cliente = ClienteEmbeddingGemini(cliente_sdk=sdk_falso)

    resultado = cliente.obter_embedding("estou bem hoje")

    assert resultado == [0.1, 0.2, 0.3]
    assert sdk_falso.models.chamadas == [("gemini-embedding-2", "estou bem hoje")]


def test_obter_embedding_usa_modelo_customizado():
    sdk_falso = _ClienteSdkFalso([0.5])
    cliente = ClienteEmbeddingGemini(modelo="outro-modelo", cliente_sdk=sdk_falso)

    cliente.obter_embedding("oi")

    assert sdk_falso.models.chamadas == [("outro-modelo", "oi")]


def test_construtor_nao_instancia_sdk_real_sem_chave_de_api(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Não deve levantar exceção: a construção do genai.Client() real é
    # adiada até a primeira chamada a obter_embedding, não acontece aqui.
    cliente = ClienteEmbeddingGemini()

    assert cliente is not None
    assert cliente._cliente_sdk_lazy is None
