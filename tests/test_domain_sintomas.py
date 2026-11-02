import pytest

from zela.domain.sintomas import CategoriaMensagem, classificar_mensagem


@pytest.mark.parametrize(
    "texto",
    [
        "Estou com o coração acelerado e tontura",
        "TONTURA forte agora",
        "dor no peito",
        "estou com falta de ar",
        "não consigo respirar",
        "acabei de cair, levei um tombo",
        "me sentindo mal",
        "não estou bem",
        "estou passando muito mal",
        "minha pressão subiu",
    ],
)
def test_sintoma_grave(texto):
    assert classificar_mensagem(texto).categoria == CategoriaMensagem.SINTOMA_GRAVE


def test_lista_os_sintomas_encontrados():
    resultado = classificar_mensagem("coração acelerado e tontura")
    assert set(resultado.sintomas) == {"coração acelerado", "tontura"}


@pytest.mark.parametrize(
    "texto",
    ["não estou com tontura", "sem dor no peito", "nao tenho falta de ar", "não senti tontura"],
)
def test_sintoma_negado_nao_conta(texto):
    assert classificar_mensagem(texto).categoria == CategoriaMensagem.NENHUM


def test_negacao_de_outra_coisa_nao_esconde_sintoma():
    resultado = classificar_mensagem("não aguento essa tontura")
    assert resultado.categoria == CategoriaMensagem.SINTOMA_GRAVE


@pytest.mark.parametrize(
    "texto",
    ["chame minha filha", "avisa a família por favor", "liga para o meu filho", "socorro", "preciso de ajuda", "pode contatar um familiar?"],
)
def test_pedido_de_ajuda(texto):
    assert classificar_mensagem(texto).categoria == CategoriaMensagem.PEDIDO_AJUDA


def test_sintoma_com_pedido_de_ajuda_prevalece_o_pedido_e_guarda_sintomas():
    resultado = classificar_mensagem("estou com tontura, chame um familiar")
    assert resultado.categoria == CategoriaMensagem.PEDIDO_AJUDA
    assert resultado.sintomas == ("tontura",)


@pytest.mark.parametrize(
    "texto",
    ["não avise ninguém", "NAO AVISE", "não chame minha filha", "não precisa avisar", "não preciso de ajuda", "cancela"],
)
def test_recusa(texto):
    assert classificar_mensagem(texto).categoria == CategoriaMensagem.CANCELAMENTO_RECUSA


@pytest.mark.parametrize("texto", ["estou bem", "ESTOU BEM!", "tô bem, obrigada", "sim", "tudo bem", "já passou", "estou melhor"])
def test_estou_bem(texto):
    assert classificar_mensagem(texto).categoria == CategoriaMensagem.CANCELAMENTO_ESTOU_BEM


@pytest.mark.parametrize("texto", ["estou bem mal", "não estou bem", "estou bem tonta", "estou muito mal"])
def test_ambiguidade_nao_cancela(texto):
    assert classificar_mensagem(texto).categoria not in (
        CategoriaMensagem.CANCELAMENTO_ESTOU_BEM,
        CategoriaMensagem.CANCELAMENTO_RECUSA,
    )


def test_recusa_com_sintoma_junto_nao_cancela():
    resultado = classificar_mensagem("estou com dor no peito mas não avise ninguém")
    assert resultado.categoria == CategoriaMensagem.SINTOMA_GRAVE


@pytest.mark.parametrize("texto", ["bom dia", "esqueci de tomar o remédio", "não dormi muito bem", "que horas é a consulta?"])
def test_mensagem_comum(texto):
    assert classificar_mensagem(texto).categoria == CategoriaMensagem.NENHUM


def test_frase_real_do_teste_em_producao_notifica_na_hora():
    resultado = classificar_mensagem("Estou com o coração acelerado e com tontura, pode contatar um familiar?")
    assert resultado.categoria == CategoriaMensagem.PEDIDO_AJUDA
    assert set(resultado.sintomas) == {"coração acelerado", "tontura"}
