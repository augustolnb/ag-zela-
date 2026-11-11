# tests/test_storage_rotina.py
from datetime import datetime, time, timedelta

from zela.models.rotina import Compromisso, Dosagem, Medicamento, TipoCompromisso
from zela.storage.db import conectar
from zela.storage.rotina import (
    aplicar_confirmacao,
    aplicar_lembretes_pendentes,
    listar_compromissos,
    listar_compromissos_pendentes_sync_google,
    listar_compromissos_removidos_pendentes_cancelamento,
    listar_medicamentos,
    listar_tipos_lembrete_enviados,
    marcar_google_sync_feito,
    registrar_lembrete_compromisso_enviado,
    remover_compromisso,
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


def test_remover_compromisso_oculta_da_listagem_mas_mantem_a_linha():
    conn = conectar(":memory:")
    salvar_compromisso(
        conn,
        Compromisso(
            id="comp-1", titulo="Exame", data_hora=datetime.now() + timedelta(days=1),
            local="Lab", tipo=TipoCompromisso.EXAME,
        ),
        idoso_id="idosa-1",
    )

    remover_compromisso(conn, "comp-1", idoso_id="idosa-1")

    assert listar_compromissos(conn, "idosa-1") == []
    linha = conn.execute("SELECT removido, google_sync_pendente FROM compromisso WHERE id = ?", ("comp-1",)).fetchone()
    assert linha["removido"] == 1
    assert linha["google_sync_pendente"] == 1


def test_salvar_compromisso_marca_sync_pendente_por_padrao():
    conn = conectar(":memory:")
    salvar_compromisso(
        conn,
        Compromisso(
            id="comp-1", titulo="Exame", data_hora=datetime.now() + timedelta(days=2),
            local="Lab", tipo=TipoCompromisso.EXAME,
        ),
        idoso_id="idosa-1",
    )
    linha = conn.execute("SELECT google_sync_pendente FROM compromisso WHERE id = ?", ("comp-1",)).fetchone()
    assert linha["google_sync_pendente"] == 1


def test_editar_data_hora_limpa_lembretes_cujo_novo_horario_ainda_esta_no_futuro():
    conn = conectar(":memory:")
    data_hora_original = datetime.now() + timedelta(hours=2)
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=data_hora_original, local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )
    # simula que o lembrete "instantaneo" e "1h" já foram enviados com o horário antigo
    registrar_lembrete_compromisso_enviado(conn, "comp-1", "instantaneo", datetime.now())
    registrar_lembrete_compromisso_enviado(conn, "comp-1", "1h", datetime.now())

    nova_data_hora = datetime.now() + timedelta(days=3)  # bem mais no futuro
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=nova_data_hora, local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )

    tipos_restantes = listar_tipos_lembrete_enviados(conn, "comp-1")
    # "1h" tinha horário-alvo recalculado (nova_data_hora - 1h) ainda no futuro -> deve ter sido limpo
    assert "1h" not in tipos_restantes
    # "instantaneo" não tem horário-alvo (sempre considerado "no passado"/já disparado) -> não é limpo
    assert "instantaneo" in tipos_restantes


def test_listar_compromissos_removidos_pendentes_cancelamento_so_retorna_nao_notificados():
    conn = conectar(":memory:")
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime.now() + timedelta(days=1), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )
    remover_compromisso(conn, "comp-1", idoso_id="idosa-1")

    pendentes = listar_compromissos_removidos_pendentes_cancelamento(conn, "idosa-1")
    assert [c.id for c in pendentes] == ["comp-1"]

    registrar_lembrete_compromisso_enviado(conn, "comp-1", "cancelamento", datetime.now())

    assert listar_compromissos_removidos_pendentes_cancelamento(conn, "idosa-1") == []


def test_listar_compromissos_pendentes_sync_google_e_marcar_feito():
    conn = conectar(":memory:")
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime.now() + timedelta(days=1), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )

    pendentes = listar_compromissos_pendentes_sync_google(conn, "idosa-1")
    assert len(pendentes) == 1
    assert pendentes[0].compromisso.id == "comp-1"
    assert pendentes[0].google_event_id is None
    assert pendentes[0].removido is False

    marcar_google_sync_feito(conn, "comp-1", google_event_id="evt-abc")

    assert listar_compromissos_pendentes_sync_google(conn, "idosa-1") == []
    linha = conn.execute("SELECT google_event_id FROM compromisso WHERE id = ?", ("comp-1",)).fetchone()
    assert linha["google_event_id"] == "evt-abc"
