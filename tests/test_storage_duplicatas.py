import sqlite3
from datetime import datetime

from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura
from zela.storage.db import conectar
from zela.storage.monitoramento import salvar_leitura

T = datetime(2026, 10, 31, 16, 50)


def _fc(valor=117.0, timestamp=T):
    return LeituraSensor(
        fonte=FonteSensor.SMARTWATCH, tipo=TipoLeitura.FREQUENCIA_CARDIACA,
        valor=valor, unidade="bpm", timestamp=timestamp,
    )


def _total(conn):
    return conn.execute("SELECT COUNT(*) FROM leitura_sensor").fetchone()[0]


def test_reenvio_identico_nao_duplica(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    assert salvar_leitura(conn, _fc(), "idosa-1") is True
    assert salvar_leitura(conn, _fc(), "idosa-1") is False
    assert _total(conn) == 1


def test_mesmo_horario_com_valor_diferente_e_preservado(tmp_path):
    # Passos do dia chegam com o mesmo horário e o total crescendo.
    conn = conectar(str(tmp_path / "t.db"))
    salvar_leitura(conn, _fc(100.0), "idosa-1")
    salvar_leitura(conn, _fc(120.0), "idosa-1")
    assert _total(conn) == 2


def test_outro_idoso_nao_conta_como_duplicata(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    salvar_leitura(conn, _fc(), "idosa-1")
    assert salvar_leitura(conn, _fc(), "idosa-2") is True


def test_migracao_remove_so_copias_exatas_e_e_idempotente(tmp_path):
    caminho = str(tmp_path / "t.db")
    conn = conectar(caminho)
    conn.execute("DROP INDEX ux_leitura_sensor_unica")
    linhas = [
        ("idosa-1", "smartwatch", "frequencia_cardiaca", 117.0, "bpm", "2026-10-31T16:50:00-03:00"),
        ("idosa-1", "smartwatch", "frequencia_cardiaca", 117.0, "bpm", "2026-10-31T16:50:00-03:00"),
        ("idosa-1", "smartwatch", "frequencia_cardiaca", 117.0, "bpm", "2026-10-31T16:50:00-03:00"),
        ("idosa-1", "smartwatch", "passos", 10.0, "passos", "2026-10-31T00:00:00-03:00"),
        ("idosa-1", "smartwatch", "passos", 20.0, "passos", "2026-10-31T00:00:00-03:00"),
        ("idosa-1", "esp32", "presenca", 1.0, "deteccao", "2026-10-31T10:00:00"),
    ]
    conn.executemany(
        "INSERT INTO leitura_sensor (idoso_id, fonte, tipo, valor, unidade, timestamp) VALUES (?, ?, ?, ?, ?, ?)", linhas
    )
    conn.commit()
    conn.close()

    conn = conectar(caminho)
    assert _total(conn) == 4
    assert conn.execute("SELECT MIN(id) FROM leitura_sensor WHERE tipo = 'frequencia_cardiaca'").fetchone()[0] == 1
    conn.close()

    conn = conectar(caminho)
    assert _total(conn) == 4


def test_indice_impede_copia_mesmo_com_insert_direto(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    salvar_leitura(conn, _fc(), "idosa-1")
    try:
        conn.execute(
            "INSERT INTO leitura_sensor (idoso_id, fonte, tipo, valor, unidade, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            ("idosa-1", "smartwatch", "frequencia_cardiaca", 117.0, "bpm", T.isoformat()),
        )
    except sqlite3.IntegrityError:
        return
    raise AssertionError("deveria recusar a cópia")
