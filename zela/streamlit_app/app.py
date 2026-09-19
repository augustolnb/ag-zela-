import os

import streamlit as st

from zela.storage.db import conectar
from zela.streamlit_app.autenticacao import exigir_autenticacao
from zela.streamlit_app.formularios import formulario_compromisso, formulario_medicamento
from zela.streamlit_app.secoes import (
    renderizar_alertas,
    renderizar_grafico,
    renderizar_medicacao,
    renderizar_status,
)

CAMINHO_DB = os.environ.get("ZELA_DB_PATH", "zela.db")
ID_IDOSO = "idosa-1"

st.set_page_config(page_title="Zela+ — Painel da Família", page_icon="🩺")
st.title("Zela+ — Painel da Família")

if not exigir_autenticacao():
    st.stop()

conn = conectar(CAMINHO_DB)

renderizar_status(conn, ID_IDOSO)
renderizar_medicacao(conn, ID_IDOSO)
renderizar_alertas(conn, ID_IDOSO)
renderizar_grafico(conn, ID_IDOSO)

st.divider()

formulario_medicamento(conn, ID_IDOSO)
formulario_compromisso(conn, ID_IDOSO)
