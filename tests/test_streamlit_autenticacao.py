from streamlit.testing.v1 import AppTest

_CODIGO_TESTE = """
import streamlit as st
from zela.streamlit_app.autenticacao import exigir_autenticacao

if exigir_autenticacao():
    st.write("liberado")
"""


def test_exigir_autenticacao_bloqueia_sem_variavel_de_ambiente(monkeypatch):
    monkeypatch.delenv("STREAMLIT_SENHA", raising=False)

    at = AppTest.from_string(_CODIGO_TESTE)
    at.run()

    assert at.exception == []
    assert any("STREAMLIT_SENHA" in erro.value for erro in at.error)
    assert at.markdown == []


def test_exigir_autenticacao_bloqueia_senha_errada(monkeypatch):
    from streamlit.proto.TextInput_pb2 import TextInput

    monkeypatch.setenv("STREAMLIT_SENHA", "correta123")

    at = AppTest.from_string(_CODIGO_TESTE)
    at.run()

    # Antes de digitar qualquer coisa, não deve mostrar "senha incorreta" --
    # o campo vazio é um estado distinto de "senha errada".
    assert at.warning == []
    assert at.text_input[0].proto.type == TextInput.PASSWORD

    at.text_input[0].set_value("errada").run()

    assert at.exception == []
    assert any("incorreta" in aviso.value.lower() for aviso in at.warning)
    assert at.markdown == []


def test_exigir_autenticacao_libera_com_senha_certa(monkeypatch):
    monkeypatch.setenv("STREAMLIT_SENHA", "correta123")

    at = AppTest.from_string(_CODIGO_TESTE)
    at.run()
    at.text_input[0].set_value("correta123").run()

    assert at.exception == []
    assert [m.value for m in at.markdown] == ["liberado"]


def test_exigir_autenticacao_mantem_liberado_apos_novo_run(monkeypatch):
    monkeypatch.setenv("STREAMLIT_SENHA", "correta123")

    at = AppTest.from_string(_CODIGO_TESTE)
    at.run()
    at.text_input[0].set_value("correta123").run()
    at.run()  # simula uma nova reexecução do script na mesma sessão

    assert at.exception == []
    assert [m.value for m in at.markdown] == ["liberado"]


def test_exigir_autenticacao_aceita_senha_com_acento(monkeypatch):
    monkeypatch.setenv("STREAMLIT_SENHA", "senha-coração")

    at = AppTest.from_string(_CODIGO_TESTE)
    at.run()
    at.text_input[0].set_value("senha-coração").run()

    assert at.exception == []
    assert [m.value for m in at.markdown] == ["liberado"]
