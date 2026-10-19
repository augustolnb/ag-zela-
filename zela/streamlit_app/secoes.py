from datetime import datetime

import pandas as pd
import streamlit as st

from zela.models.monitoramento import TipoLeitura
from zela.storage.alertas import listar_alertas
from zela.storage.monitoramento import aplicar_classificacao, listar_leituras_recentes
from zela.storage.rotina import listar_confirmacoes_do_dia, listar_medicamentos
from zela.streamlit_app.estilo import badge_nivel


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
        badge = badge_nivel(alerta.nivel.value)
        st.markdown(
            f"{badge} {data_hora} — {alerta.mensagem}", unsafe_allow_html=True
        )


def renderizar_grafico(conn, idoso_id: str) -> None:
    st.subheader("Atividade de hoje")
    inicio_do_dia = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    leituras = listar_leituras_recentes(conn, idoso_id, inicio_do_dia)

    leituras_presenca = [l for l in leituras if l.tipo == TipoLeitura.PRESENCA]
    if leituras_presenca:
        dados = pd.DataFrame(
            {"presença": [l.valor for l in leituras_presenca]},
            index=[l.timestamp for l in leituras_presenca],
        )
        st.line_chart(dados)
    else:
        st.write("Nenhuma leitura de presença hoje ainda.")

    _renderizar_resumo_smartwatch(leituras)


def _renderizar_resumo_smartwatch(leituras) -> None:
    leituras_frequencia = [l for l in leituras if l.tipo == TipoLeitura.FREQUENCIA_CARDIACA]
    leituras_passos = [l for l in leituras if l.tipo == TipoLeitura.PASSOS]
    leituras_sono = [l for l in leituras if l.tipo == TipoLeitura.SONO]

    if not (leituras_frequencia or leituras_passos or leituras_sono):
        return

    st.caption("Smartwatch")
    if leituras_frequencia:
        valores = [l.valor for l in leituras_frequencia]
        ultima = max(leituras_frequencia, key=lambda l: l.timestamp)
        st.write(
            f"Frequência cardíaca: {ultima.valor:.0f} bpm "
            f"(mín {min(valores):.0f} — máx {max(valores):.0f} hoje) — "
            f"última leitura às {ultima.timestamp.strftime('%H:%M')}"
        )
    if leituras_passos:
        ultima = max(leituras_passos, key=lambda l: l.timestamp)
        st.write(
            f"Passos hoje: {ultima.valor:.0f} — "
            f"atualizado às {ultima.timestamp.strftime('%H:%M')}"
        )
    if leituras_sono:
        ultima = max(leituras_sono, key=lambda l: l.timestamp)
        horas, minutos = divmod(round(ultima.valor * 60), 60)
        st.write(
            f"Sono (última noite): {horas}h{minutos:02d}min — "
            f"registrado às {ultima.timestamp.strftime('%H:%M')}"
        )
