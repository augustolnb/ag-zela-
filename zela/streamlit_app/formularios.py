import uuid
from datetime import datetime

import streamlit as st

from zela.models.rotina import Compromisso, Dosagem, Medicamento, TipoCompromisso
from zela.storage.rotina import (
    listar_compromissos,
    listar_medicamentos,
    salvar_compromisso,
    salvar_medicamento,
)


def formulario_medicamento(conn, idoso_id: str) -> None:
    st.subheader("Cadastrar ou editar medicamento")
    medicamentos = listar_medicamentos(conn, idoso_id)
    opcoes = ["Novo medicamento"] + [m.nome for m in medicamentos]
    escolha = st.selectbox("Medicamento", opcoes, key="medicamento_selecionado")

    medicamento_existente = None
    if escolha != "Novo medicamento":
        medicamento_existente = next(m for m in medicamentos if m.nome == escolha)

    if medicamento_existente is not None and len(medicamento_existente.horarios) > 1:
        st.warning(
            "Este medicamento tem mais de um horário cadastrado. Este formulário "
            "edita apenas o primeiro horário — os demais serão removidos ao salvar."
        )

    with st.form("form_medicamento"):
        nome = st.text_input(
            "Nome", value=medicamento_existente.nome if medicamento_existente else ""
        )
        quantidade = st.number_input(
            "Quantidade da dose", min_value=0.0,
            value=medicamento_existente.dosagem.quantidade if medicamento_existente else 1.0,
        )
        unidade = st.text_input(
            "Unidade (ex.: mg, comprimido)",
            value=medicamento_existente.dosagem.unidade if medicamento_existente else "",
        )
        horario = st.time_input(
            "Horário",
            value=medicamento_existente.horarios[0] if medicamento_existente else None,
        )
        dias_semana = st.multiselect(
            "Dias da semana (0=segunda ... 6=domingo)",
            options=list(range(7)),
            default=medicamento_existente.dias_semana if medicamento_existente else list(range(7)),
        )
        bula = st.text_area(
            "Bula/instruções (opcional)",
            value=(medicamento_existente.bula or "") if medicamento_existente else "",
        )
        enviado = st.form_submit_button("Salvar")

    if not enviado:
        return

    try:
        medicamento = Medicamento(
            id=medicamento_existente.id if medicamento_existente else str(uuid.uuid4()),
            nome=nome,
            dosagem=Dosagem(quantidade=quantidade, unidade=unidade),
            horarios=[horario],
            dias_semana=dias_semana,
            bula=bula or None,
        )
        salvar_medicamento(conn, medicamento, idoso_id)
        st.success(f"Medicamento '{nome}' salvo com sucesso.")
        st.rerun()
    except Exception as exc:
        st.error(f"Não foi possível salvar: {exc}")


def formulario_compromisso(conn, idoso_id: str) -> None:
    st.subheader("Cadastrar ou editar compromisso")
    compromissos = listar_compromissos(conn, idoso_id)
    opcoes = ["Novo compromisso"] + [c.titulo for c in compromissos]
    escolha = st.selectbox("Compromisso", opcoes, key="compromisso_selecionado")

    compromisso_existente = None
    if escolha != "Novo compromisso":
        compromisso_existente = next(c for c in compromissos if c.titulo == escolha)

    with st.form("form_compromisso"):
        titulo = st.text_input(
            "Título", value=compromisso_existente.titulo if compromisso_existente else ""
        )
        data = st.date_input(
            "Data", value=compromisso_existente.data_hora.date() if compromisso_existente else None
        )
        horario = st.time_input(
            "Horário", value=compromisso_existente.data_hora.time() if compromisso_existente else None
        )
        local = st.text_input(
            "Local", value=compromisso_existente.local if compromisso_existente else ""
        )
        tipos = list(TipoCompromisso)
        indice_padrao = tipos.index(compromisso_existente.tipo) if compromisso_existente else 0
        tipo = st.selectbox("Tipo", tipos, format_func=lambda t: t.value, index=indice_padrao)
        enviado = st.form_submit_button("Salvar")

    if not enviado:
        return

    try:
        compromisso = Compromisso(
            id=compromisso_existente.id if compromisso_existente else str(uuid.uuid4()),
            titulo=titulo,
            data_hora=datetime.combine(data, horario),
            local=local,
            tipo=tipo,
        )
        salvar_compromisso(conn, compromisso, idoso_id)
        st.success(f"Compromisso '{titulo}' salvo com sucesso.")
        st.rerun()
    except Exception as exc:
        st.error(f"Não foi possível salvar: {exc}")
