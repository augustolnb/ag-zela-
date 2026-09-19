from datetime import datetime

import streamlit as st

from zela.storage.alertas import listar_alertas
from zela.storage.monitoramento import aplicar_classificacao
from zela.storage.rotina import listar_confirmacoes_do_dia, listar_medicamentos


def renderizar_status(conn, idoso_id: str) -> None:
    st.subheader("Status atual")
    evento = aplicar_classificacao(conn, idoso_id, datetime.now())
    st.metric("Status", evento.status.value.upper())
    st.caption(evento.motivo)


def renderizar_medicacao(conn, idoso_id: str) -> None:
    st.subheader("Medicação de hoje")
    agora = datetime.now()
    medicamentos = {m.id: m for m in listar_medicamentos(conn, idoso_id)}
    confirmacoes = listar_confirmacoes_do_dia(conn, idoso_id, agora)
    if not confirmacoes:
        st.write("Nenhum registro de medicação hoje ainda.")
        return
    for confirmacao in confirmacoes:
        medicamento = medicamentos.get(confirmacao.medicamento_id)
        nome = medicamento.nome if medicamento else confirmacao.medicamento_id
        horario = confirmacao.horario_previsto.strftime("%H:%M")
        st.write(f"{nome} — {horario} — {confirmacao.status.value}")


MAXIMO_ALERTAS_EXIBIDOS = 10


def renderizar_alertas(conn, idoso_id: str) -> None:
    st.subheader("Últimos alertas")
    alertas = listar_alertas(conn, idoso_id)
    if not alertas:
        st.write("Nenhum alerta registrado.")
        return
    for alerta in reversed(alertas[-MAXIMO_ALERTAS_EXIBIDOS:]):
        data_hora = alerta.timestamp.strftime("%d/%m %H:%M")
        st.write(f"[{alerta.nivel.value.upper()}] {data_hora} — {alerta.mensagem}")
