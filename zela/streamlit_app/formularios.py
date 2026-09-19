import uuid

import streamlit as st

from zela.models.rotina import Dosagem, Medicamento
from zela.storage.rotina import listar_medicamentos, salvar_medicamento


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
