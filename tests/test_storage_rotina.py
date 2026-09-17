# tests/test_storage_rotina.py
from datetime import datetime, time

from zela.models.rotina import Dosagem, Medicamento
from zela.storage.db import conectar
from zela.storage.rotina import (
    aplicar_confirmacao,
    aplicar_lembretes_pendentes,
    listar_medicamentos,
    salvar_medicamento,
)


def _medicamento():
    return Medicamento(
        id="med-1",
        nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"),
        horarios=[time(8, 0)],
    )


def test_salvar_e_listar_medicamentos():
    conn = conectar(":memory:")
    salvar_medicamento(conn, _medicamento(), idoso_id="idosa-1")

    medicamentos = listar_medicamentos(conn, "idosa-1")

    assert len(medicamentos) == 1
    assert medicamentos[0].nome == "Losartana"
    assert medicamentos[0].horarios == [time(8, 0)]
    assert medicamentos[0].dosagem.quantidade == 50


def test_aplicar_lembretes_pendentes_encontra_medicamento_na_janela():
    conn = conectar(":memory:")
    salvar_medicamento(conn, _medicamento(), idoso_id="idosa-1")
    agora = datetime(2026, 9, 14, 8, 5)

    pendentes = aplicar_lembretes_pendentes(conn, "idosa-1", agora)

    assert len(pendentes) == 1
    assert pendentes[0].id == "med-1"


def test_aplicar_confirmacao_persiste_e_exclui_de_lembretes_futuros():
    conn = conectar(":memory:")
    medicamento = _medicamento()
    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")
    agora = datetime(2026, 9, 14, 8, 5)

    confirmacao = aplicar_confirmacao(conn, medicamento, horario_previsto=agora, agora=agora)
    assert confirmacao.medicamento_id == "med-1"
    assert confirmacao.status.value == "confirmado"

    pendentes_depois = aplicar_lembretes_pendentes(conn, "idosa-1", agora)
    assert pendentes_depois == []


def test_salvar_e_listar_medicamento_com_bula():
    conn = conectar(":memory:")
    medicamento = Medicamento(
        id="med-1", nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
        bula="Usado para pressão alta. Tomar em jejum.",
    )

    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")
    medicamentos = listar_medicamentos(conn, "idosa-1")

    assert len(medicamentos) == 1
    assert medicamentos[0].bula == "Usado para pressão alta. Tomar em jejum."


def test_salvar_e_listar_medicamento_sem_bula():
    conn = conectar(":memory:")
    medicamento = Medicamento(
        id="med-2", nome="Vitamina D",
        dosagem=Dosagem(quantidade=1, unidade="comprimido"), horarios=[time(9, 0)],
    )

    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")
    medicamentos = listar_medicamentos(conn, "idosa-1")

    assert medicamentos[0].bula is None
