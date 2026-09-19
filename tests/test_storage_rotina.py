# tests/test_storage_rotina.py
from datetime import datetime, time, timedelta

from zela.models.rotina import Compromisso, Dosagem, Medicamento, TipoCompromisso
from zela.storage.db import conectar
from zela.storage.rotina import (
    aplicar_confirmacao,
    aplicar_lembretes_pendentes,
    listar_compromissos,
    listar_medicamentos,
    salvar_compromisso,
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


def test_salvar_e_listar_compromisso_futuro():
    conn = conectar(":memory:")
    compromisso = Compromisso(
        id="comp-1",
        titulo="Consulta cardiologista",
        data_hora=datetime.now() + timedelta(days=1),
        local="Clínica Central",
        tipo=TipoCompromisso.CONSULTA,
    )

    salvar_compromisso(conn, compromisso, idoso_id="idosa-1")
    compromissos = listar_compromissos(conn, "idosa-1")

    assert len(compromissos) == 1
    assert compromissos[0].titulo == "Consulta cardiologista"
    assert compromissos[0].tipo == TipoCompromisso.CONSULTA
    assert compromissos[0].local == "Clínica Central"


def test_listar_compromisso_ja_passado_nao_levanta_erro():
    conn = conectar(":memory:")
    # Insere direto via SQL (não via Compromisso(...), que rejeitaria uma data
    # no passado) para simular um compromisso já registrado que já aconteceu.
    # listar_compromissos precisa conseguir reconstruí-lo sem levantar erro.
    conn.execute(
        "INSERT INTO compromisso (id, idoso_id, titulo, data_hora, local, tipo) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            "comp-2", "idosa-1", "Exame de sangue",
            (datetime.now() - timedelta(days=1)).isoformat(),
            "Laboratório X", "exame",
        ),
    )
    conn.commit()

    compromissos = listar_compromissos(conn, "idosa-1")

    assert len(compromissos) == 1
    assert compromissos[0].titulo == "Exame de sangue"
    assert compromissos[0].tipo == TipoCompromisso.EXAME


def test_salvar_compromisso_atualiza_existente():
    conn = conectar(":memory:")
    original = Compromisso(
        id="comp-3", titulo="Consulta", data_hora=datetime.now() + timedelta(days=1),
        local="Local A", tipo=TipoCompromisso.CONSULTA,
    )
    salvar_compromisso(conn, original, idoso_id="idosa-1")

    atualizado = Compromisso(
        id="comp-3", titulo="Consulta (remarcada)", data_hora=datetime.now() + timedelta(days=2),
        local="Local B", tipo=TipoCompromisso.CONSULTA,
    )
    salvar_compromisso(conn, atualizado, idoso_id="idosa-1")

    compromissos = listar_compromissos(conn, "idosa-1")

    assert len(compromissos) == 1
    assert compromissos[0].titulo == "Consulta (remarcada)"
    assert compromissos[0].local == "Local B"


def test_listar_compromissos_ordena_por_data_hora():
    conn = conectar(":memory:")
    salvar_compromisso(
        conn,
        Compromisso(
            id="comp-tarde", titulo="Compromisso à tarde",
            data_hora=datetime.now() + timedelta(days=2),
            local="Local", tipo=TipoCompromisso.OUTRO,
        ),
        idoso_id="idosa-1",
    )
    salvar_compromisso(
        conn,
        Compromisso(
            id="comp-cedo", titulo="Compromisso mais cedo",
            data_hora=datetime.now() + timedelta(days=1),
            local="Local", tipo=TipoCompromisso.OUTRO,
        ),
        idoso_id="idosa-1",
    )

    compromissos = listar_compromissos(conn, "idosa-1")

    assert [c.id for c in compromissos] == ["comp-cedo", "comp-tarde"]
