from streamlit.testing.v1 import AppTest

from zela.storage.db import conectar
from zela.storage.usuarios import criar_usuario


def _app(caminho):
    codigo = f"""
import streamlit as st
from zela.storage.db import conectar
from zela.streamlit_app.autenticacao import exigir_autenticacao, mostrar_usuario_conectado

usuario = exigir_autenticacao(conectar({caminho!r}))
if usuario:
    mostrar_usuario_conectado(usuario)
    st.write("liberado")
"""
    return AppTest.from_string(codigo, default_timeout=10)


def _com_usuario(tmp_path):
    caminho = str(tmp_path / "t.db")
    criar_usuario(conectar(caminho), "augusto", "senha-forte-1")
    return caminho


def _entrar(at, usuario, senha):
    at.text_input(key="login_usuario").set_value(usuario)
    at.text_input(key="login_senha").set_value(senha)
    at.button(key="login_entrar").click().run()


def _liberado(at):
    return any(m.value == "liberado" for m in at.markdown)


def test_sem_usuarios_cadastrados_explica_como_criar(tmp_path):
    at = _app(str(tmp_path / "t.db"))
    at.run()

    assert at.exception == []
    assert any("python -m zela.streamlit_app.usuarios criar" in e.value for e in at.error)
    assert not _liberado(at)


def test_formulario_tem_usuario_senha_e_entrar(tmp_path):
    from streamlit.proto.TextInput_pb2 import TextInput

    at = _app(_com_usuario(tmp_path))
    at.run()

    assert at.text_input(key="login_usuario").label == "Usuário"
    assert at.text_input(key="login_senha").label == "Senha"
    assert at.text_input(key="login_senha").proto.type == TextInput.PASSWORD
    assert at.error == []
    assert not _liberado(at)


def test_credencial_errada_mostra_mensagem_unica(tmp_path):
    at = _app(_com_usuario(tmp_path))
    at.run()

    _entrar(at, "augusto", "errada-123")
    assert [e.value for e in at.error] == ["Usuário ou senha incorretos."]
    assert not _liberado(at)

    _entrar(at, "ninguem", "senha-forte-1")
    assert [e.value for e in at.error] == ["Usuário ou senha incorretos."]


def test_login_certo_some_com_o_formulario_e_mostra_quem_entrou(tmp_path):
    at = _app(_com_usuario(tmp_path))
    at.run()

    _entrar(at, "Augusto", "senha-forte-1")

    assert at.exception == []
    assert _liberado(at)
    assert at.text_input == []
    assert any("augusto" in c.value for c in at.caption)
    at.run()
    assert _liberado(at)


def test_sair_volta_para_o_login(tmp_path):
    at = _app(_com_usuario(tmp_path))
    at.run()
    _entrar(at, "augusto", "senha-forte-1")

    at.button(key="sair").click().run()

    assert not _liberado(at)
    assert at.text_input(key="login_usuario").value == ""
