import math
from datetime import datetime

from zela.embeddings.exemplos_referencia import ExemploReferencia
from zela.models.monitoramento import EventoMonitoramento, MetodoClassificacao


def similaridade_cosseno(a: list[float], b: list[float]) -> float:
    produto_escalar = sum(x * y for x, y in zip(a, b, strict=True))
    norma_a = math.sqrt(sum(x * x for x in a))
    norma_b = math.sqrt(sum(y * y for y in b))
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return produto_escalar / (norma_a * norma_b)


def classificar_por_similaridade(
    embedding_mensagem: list[float],
    exemplos_com_embedding: list[tuple[ExemploReferencia, list[float]]],
    texto_original: str,
    agora: datetime,
) -> EventoMonitoramento:
    if not exemplos_com_embedding:
        raise ValueError("exemplos_com_embedding não pode ser vazio")

    exemplo_mais_similar, _ = max(
        exemplos_com_embedding,
        key=lambda par: similaridade_cosseno(embedding_mensagem, par[1]),
    )

    return EventoMonitoramento(
        status=exemplo_mais_similar.status,
        motivo=(
            f"Mensagem do idoso classificada por similaridade a exemplo de "
            f"referência ('{exemplo_mais_similar.texto}'): \"{texto_original}\""
        ),
        timestamp=agora,
        metodo_classificacao=MetodoClassificacao.EMBEDDING,
    )
