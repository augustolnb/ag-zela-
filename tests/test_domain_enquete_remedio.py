from datetime import time, timedelta

from zela.domain.enquete_remedio import (
    INTERVALO_RELEMBRAR,
    OPCAO_AINDA_NAO,
    OPCAO_TOMEI,
    OPCOES,
    RESPOSTA_AINDA_NAO,
    chave_da_mensagem,
    interpretar_voto,
    pergunta_lembrete,
    resposta_tomei,
)
from zela.models.rotina import Dosagem, Medicamento


def _dipirona():
    return Medicamento(
        id="m1", nome="dipirona", dosagem=Dosagem(quantidade=1, unidade="comprimido"), horarios=[time(8, 0)]
    )


def test_opcoes_da_enquete():
    assert OPCAO_TOMEI == "✅ Tomei"
    assert OPCAO_AINDA_NAO == "⏰ Ainda não"
    assert OPCOES == [OPCAO_TOMEI, OPCAO_AINDA_NAO]


def test_pergunta_lembrete_usa_nome_e_dose():
    assert pergunta_lembrete(_dipirona()) == "Hora de tomar dipirona (1.0 comprimido). Já tomou?"


def test_chave_da_mensagem_ignora_prefixo():
    assert chave_da_mensagem("true_123@lid_3EB047657A643465") == "3EB047657A643465"
    assert chave_da_mensagem({"_serialized": "true_123@lid_3EB047657A643465"}) == "3EB047657A643465"
    assert chave_da_mensagem("3EB047657A643465") == "3EB047657A643465"


def test_interpretar_voto():
    assert interpretar_voto(["✅ Tomei"]) == "tomei"
    assert interpretar_voto(["⏰ Ainda não"]) == "ainda_nao"
    assert interpretar_voto([]) is None
    assert interpretar_voto(["outra"]) is None


def test_respostas():
    assert resposta_tomei(_dipirona()) == "Anotado! ✅ Dose de dipirona registrada."
    assert RESPOSTA_AINDA_NAO == "Tudo bem! Te lembro de novo em 30 minutos."
    assert INTERVALO_RELEMBRAR == timedelta(minutes=30)
