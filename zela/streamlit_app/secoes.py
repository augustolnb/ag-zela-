from datetime import datetime

import streamlit as st

from zela.storage.monitoramento import aplicar_classificacao


def renderizar_status(conn, idoso_id: str) -> None:
    st.subheader("Status atual")
    evento = aplicar_classificacao(conn, idoso_id, datetime.now())
    st.metric("Status", evento.status.value.upper())
    st.caption(evento.motivo)
