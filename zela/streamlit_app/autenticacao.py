"""Login do painel com usuário e senha.

Antes do login a página mostra só o formulário; depois, o formulário some e
o painel aparece. A sessão vale enquanto a aba do navegador estiver aberta.
Os usuários ficam no banco (zela/storage/usuarios.py) e são criados pelo
terminal: python -m zela.streamlit_app.usuarios criar <usuário>.
"""

import time

import streamlit as st

from zela.storage.usuarios import existe_algum_usuario, verificar_credenciais

CHAVE_USUARIO = "zela_usuario"
MENSAGEM_ERRO = "Usuário ou senha incorretos."
# Espera depois de uma tentativa errada: torna tentativas em massa lentas.
ESPERA_APOS_ERRO_SEGUNDOS = 1.0


def exigir_autenticacao(conn) -> str | None:
    """Devolve o usuário conectado, ou mostra o login e devolve None."""
    usuario = st.session_state.get(CHAVE_USUARIO)
    if usuario:
        return usuario

    if not existe_algum_usuario(conn):
        st.error(
            "Nenhum usuário cadastrado. No servidor, crie o primeiro com: "
            "`python -m zela.streamlit_app.usuarios criar <usuário>`"
        )
        return None

    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        with st.form("login"):
            st.subheader("Entrar")
            nome = st.text_input("Usuário", key="login_usuario", autocomplete="username")
            senha = st.text_input("Senha", type="password", key="login_senha", autocomplete="current-password")
            enviado = st.form_submit_button("Entrar", key="login_entrar", type="primary", width="stretch")
        if not enviado:
            return None
        conectado = verificar_credenciais(conn, nome, senha)
        if conectado is None:
            time.sleep(ESPERA_APOS_ERRO_SEGUNDOS)
            st.error(MENSAGEM_ERRO)
            return None

    st.session_state[CHAVE_USUARIO] = conectado
    # Recarrega para o formulário sumir antes de o painel aparecer.
    st.rerun()


def _sair() -> None:
    st.session_state.pop(CHAVE_USUARIO, None)
    for chave in ("login_usuario", "login_senha"):
        st.session_state.pop(chave, None)


def mostrar_usuario_conectado(usuario: str) -> None:
    coluna_nome, coluna_sair = st.columns([5, 1], vertical_alignment="center")
    with coluna_nome:
        st.caption(f"Conectado como **{usuario}**")
    with coluna_sair:
        st.button("Sair", key="sair", on_click=_sair, type="tertiary", icon=":material/logout:")
