from datetime import datetime

import pytest

from zela.embeddings.classificador import classificar_por_similaridade, similaridade_cosseno
from zela.embeddings.exemplos_referencia import ExemploReferencia
from zela.models.monitoramento import MetodoClassificacao, StatusMonitoramento


def test_similaridade_cosseno_vetores_identicos_e_um():
    assert similaridade_cosseno([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_similaridade_cosseno_vetores_ortogonais_e_zero():
    assert similaridade_cosseno([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_similaridade_cosseno_vetor_nulo_retorna_zero():
    assert similaridade_cosseno([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_classifica_pelo_exemplo_mais_similar():
    exemplo_normal = ExemploReferencia(texto="Estou bem", status=StatusMonitoramento.NORMAL)
    exemplo_risco = ExemploReferencia(texto="Caí e não consigo levantar", status=StatusMonitoramento.RISCO)
    exemplos_com_embedding = [
        (exemplo_normal, [1.0, 0.0, 0.0]),
        (exemplo_risco, [0.0, 1.0, 0.0]),
    ]
    agora = datetime(2026, 9, 17, 10, 0)

    evento = classificar_por_similaridade(
        embedding_mensagem=[0.05, 0.95, 0.0],
        exemplos_com_embedding=exemplos_com_embedding,
        texto_original="acabei de cair no chão",
        agora=agora,
    )

    assert evento.status == StatusMonitoramento.RISCO
    assert evento.metodo_classificacao == MetodoClassificacao.EMBEDDING
    assert evento.timestamp == agora
    assert "acabei de cair no chão" in evento.motivo
    assert evento.leituras_relacionadas == []


def test_classifica_como_normal_quando_mais_proximo_do_exemplo_normal():
    exemplo_normal = ExemploReferencia(texto="Estou bem", status=StatusMonitoramento.NORMAL)
    exemplo_risco = ExemploReferencia(texto="Caí e não consigo levantar", status=StatusMonitoramento.RISCO)
    exemplos_com_embedding = [
        (exemplo_normal, [1.0, 0.0, 0.0]),
        (exemplo_risco, [0.0, 1.0, 0.0]),
    ]

    evento = classificar_por_similaridade(
        embedding_mensagem=[0.95, 0.05, 0.0],
        exemplos_com_embedding=exemplos_com_embedding,
        texto_original="tudo bem por aqui",
        agora=datetime(2026, 9, 17, 10, 0),
    )

    assert evento.status == StatusMonitoramento.NORMAL


def test_lista_de_exemplos_vazia_levanta_erro():
    with pytest.raises(ValueError):
        classificar_por_similaridade(
            embedding_mensagem=[1.0, 0.0],
            exemplos_com_embedding=[],
            texto_original="oi",
            agora=datetime(2026, 9, 17, 10, 0),
        )
