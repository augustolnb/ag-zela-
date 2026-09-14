from zela.storage.db import ESQUEMA, conectar


def test_conectar_cria_todas_as_tabelas():
    conn = conectar(":memory:")
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tabelas = {linha["name"] for linha in cursor.fetchall()}
    assert tabelas == {
        "perfil_idoso",
        "medicamento",
        "confirmacao_medicacao",
        "compromisso",
        "leitura_sensor",
        "alerta",
        "estado_escalonamento",
    }


def test_conectar_e_idempotente():
    conn = conectar(":memory:")
    conn.executescript(ESQUEMA)  # não deve levantar erro ao rodar de novo
