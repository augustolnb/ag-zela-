import os
import secrets

import streamlit as st

VARIAVEL_SENHA = "STREAMLIT_SENHA"


def exigir_autenticacao() -> bool:
    """Mostra um campo de senha e retorna True se a família já está autenticada nesta sessão.

    Recusa funcionar (retorna False e mostra um erro) se a variável de
    ambiente STREAMLIT_SENHA não estiver configurada — evita rodar o painel
    sem nenhuma senha por esquecimento.
    """
    senha_esperada = os.environ.get(VARIAVEL_SENHA)
    if not senha_esperada:
        st.error(
            f"Variável de ambiente {VARIAVEL_SENHA} não configurada. "
            "Defina uma senha antes de rodar o painel."
        )
        return False

    if st.session_state.get("zela_autenticado"):
        return True

    senha_informada = st.text_input("Senha", type="password")
    if senha_informada == "":
        return False
    if secrets.compare_digest(senha_informada, senha_esperada):
        st.session_state["zela_autenticado"] = True
        return True

    st.warning("Senha incorreta.")
    return False
