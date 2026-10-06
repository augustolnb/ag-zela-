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


def test_conectar_migra_coluna_lid_whatsapp_em_banco_com_schema_antigo(tmp_path):
    import sqlite3

    caminho = str(tmp_path / "banco_antigo_perfil.db")
    conn_antiga = sqlite3.connect(caminho)
    conn_antiga.execute(
        """
        CREATE TABLE perfil_idoso (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            telefone TEXT NOT NULL,
            data_nascimento TEXT NOT NULL,
            condicoes_medicas TEXT NOT NULL,
            contatos_familiares TEXT NOT NULL
        )
        """
    )
    conn_antiga.commit()
    conn_antiga.close()

    conn = conectar(caminho)

    colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(perfil_idoso)")}
    assert "lid_whatsapp" in colunas


def test_conectar_migra_coluna_bula_em_banco_com_schema_antigo(tmp_path):
    import sqlite3

    caminho = str(tmp_path / "banco_antigo.db")
    conn_antiga = sqlite3.connect(caminho)
    conn_antiga.execute(
        """
        CREATE TABLE medicamento (
            id TEXT PRIMARY KEY,
            idoso_id TEXT NOT NULL,
            nome TEXT NOT NULL,
            dosagem_quantidade REAL NOT NULL,
            dosagem_unidade TEXT NOT NULL,
            horarios TEXT NOT NULL,
            dias_semana TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn_antiga.commit()
    conn_antiga.close()

    conn = conectar(caminho)

    colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(medicamento)")}
    assert "bula" in colunas
