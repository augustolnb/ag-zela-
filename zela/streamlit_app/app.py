import os

import streamlit as st

from zela.storage.db import conectar
from zela.streamlit_app.autenticacao import exigir_autenticacao, mostrar_usuario_conectado
from zela.streamlit_app.estilo import ALTURA_CARD_GRADE, aplicar_estilo, icone
from zela.streamlit_app.formularios import formulario_compromisso, formulario_medicamento
from zela.streamlit_app.secoes import (
    renderizar_alertas,
    renderizar_grafico,
    renderizar_historico,
    renderizar_medicacao,
    renderizar_status,
)

CAMINHO_DB = os.environ.get("ZELA_DB_PATH", "zela.db")
ID_IDOSO = "idosa-1"


def _renderizar_secao_com_seguranca(funcao, *args) -> None:
    try:
        funcao(*args)
    except Exception as exc:
        st.error(f"Não foi possível carregar esta seção: {exc}")


def _renderizar_card(nome_icone: str, funcao, *args, altura: int | str = "content") -> None:
    # Com `altura` em pixels, o conteúdo rola dentro do card em vez de
    # esticá-lo; "content" (padrão do Streamlit) acompanha o conteúdo.
    with st.container(border=True, height=altura, key=f"cartao-{nome_icone}"):
        st.markdown(icone(nome_icone), unsafe_allow_html=True)
        _renderizar_secao_com_seguranca(funcao, *args)


st.set_page_config(page_title="Zela+ — Painel da Família", page_icon="🩺")

# Antes da senha, para o tema valer também na tela de entrada. Ligado à URL
# (?noturno=true): a escolha sobrevive a um recarregamento da página.
noturno = st.toggle(
    "Modo noturno", key="noturno", bind="query-params",
    help="Alterna entre o tema claro (diurno) e o escuro (noturno).",
)
aplicar_estilo(noturno=noturno)

st.title("Zela+ — Painel da Família")

conn = conectar(CAMINHO_DB)

# Antes do login, a página mostra só o formulário; depois, só o painel.
usuario = exigir_autenticacao(conn)
if usuario is None:
    st.stop()
mostrar_usuario_conectado(usuario)

_renderizar_card("heart-pulse", renderizar_status, conn, ID_IDOSO)

coluna_medicacao, coluna_alertas, coluna_atividade = st.columns(3)
with coluna_medicacao:
    _renderizar_card("pill", renderizar_medicacao, conn, ID_IDOSO, altura=ALTURA_CARD_GRADE)
with coluna_alertas:
    _renderizar_card("bell", renderizar_alertas, conn, ID_IDOSO, altura=ALTURA_CARD_GRADE)
with coluna_atividade:
    _renderizar_card("activity", renderizar_grafico, conn, ID_IDOSO, altura=ALTURA_CARD_GRADE)

st.divider()

with st.container(border=True, key="cartao-abas"):
    # key + on_change="rerun": as abas lembram a escolhida. Sem isso, qualquer
    # interação na página (busca do histórico, escolher um compromisso)
    # recarrega e volta para a primeira aba.
    aba_medicamento, aba_compromisso, aba_historico = st.tabs(
        ["Medicamento", "Compromisso", "Histórico"], key="aba_painel", on_change="rerun"
    )
    with aba_medicamento:
        _renderizar_secao_com_seguranca(formulario_medicamento, conn, ID_IDOSO)
    with aba_compromisso:
        _renderizar_secao_com_seguranca(formulario_compromisso, conn, ID_IDOSO)
    with aba_historico:
        _renderizar_secao_com_seguranca(renderizar_historico, conn, ID_IDOSO)
