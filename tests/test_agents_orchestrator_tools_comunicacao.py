from zela.agents.orchestrator import consultar_conhecimento, montar_agente_comunicacao


class _ClienteEmbeddingFalso:
    def obter_embedding(self, texto: str) -> list[float]:
        return [1.0, 0.0]


class _ClienteEmbeddingComFalha:
    def obter_embedding(self, texto: str) -> list[float]:
        raise RuntimeError("Gemini fora do ar")


class _RepositorioVetorialFalso:
    def __init__(self, resultado):
        self._resultado = resultado
        self.chamadas = []

    def buscar_similares(self, idoso_id, embedding_consulta, k=3):
        self.chamadas.append((idoso_id, embedding_consulta, k))
        return self._resultado


class _RepositorioVetorialComFalha:
    def buscar_similares(self, idoso_id, embedding_consulta, k=3):
        raise RuntimeError("Chroma indisponível")


def test_agente_comunicacao_tem_uma_ferramenta():
    agente = montar_agente_comunicacao()

    assert len(agente.tools) == 1


def test_consultar_conhecimento_retorna_trechos_relevantes(monkeypatch):
    repositorio_falso = _RepositorioVetorialFalso(["Losartana: usado para pressão alta."])
    monkeypatch.setattr(
        "zela.agents.orchestrator._obter_cliente_embedding", lambda: _ClienteEmbeddingFalso()
    )
    monkeypatch.setattr(
        "zela.agents.orchestrator._obter_repositorio_vetorial", lambda: repositorio_falso
    )

    resultado = consultar_conhecimento("idosa-1", "para que serve a losartana?")

    assert resultado == ["Losartana: usado para pressão alta."]
    assert repositorio_falso.chamadas == [("idosa-1", [1.0, 0.0], 3)]


def test_consultar_conhecimento_retorna_lista_vazia_em_falha(monkeypatch):
    monkeypatch.setattr(
        "zela.agents.orchestrator._obter_cliente_embedding", lambda: _ClienteEmbeddingComFalha()
    )

    resultado = consultar_conhecimento("idosa-1", "para que serve a losartana?")

    assert resultado == []


def test_consultar_conhecimento_retorna_lista_vazia_quando_busca_vetorial_falha(monkeypatch):
    monkeypatch.setattr(
        "zela.agents.orchestrator._obter_cliente_embedding", lambda: _ClienteEmbeddingFalso()
    )
    monkeypatch.setattr(
        "zela.agents.orchestrator._obter_repositorio_vetorial", lambda: _RepositorioVetorialComFalha()
    )

    resultado = consultar_conhecimento("idosa-1", "para que serve a losartana?")

    assert resultado == []
