from datetime import datetime

from zela.storage.avisos import aviso_ja_enviado, limpar_avisos_de_episodio, registrar_aviso
from zela.storage.db import conectar

AGORA = datetime(2026, 11, 11, 2, 50)


def test_registrado_fica_marcado_so_para_a_mesma_chave_e_idoso(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    registrar_aviso(conn, "idosa-1", "O ESP32 da casa parou de enviar sinal", AGORA)

    assert aviso_ja_enviado(conn, "idosa-1", "O ESP32 da casa parou de enviar sinal")
    assert not aviso_ja_enviado(conn, "idosa-1", "outra chave")
    assert not aviso_ja_enviado(conn, "idosa-2", "O ESP32 da casa parou de enviar sinal")


def test_registrar_duas_vezes_nao_falha(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    registrar_aviso(conn, "idosa-1", "x", AGORA)
    registrar_aviso(conn, "idosa-1", "x", AGORA)
    assert aviso_ja_enviado(conn, "idosa-1", "x")


def test_sobrevive_a_um_reinicio(tmp_path):
    caminho = str(tmp_path / "t.db")
    registrar_aviso(conectar(caminho), "idosa-1", "x", AGORA)
    assert aviso_ja_enviado(conectar(caminho), "idosa-1", "x")


def test_limpar_episodio_preserva_avisos_de_sono(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    registrar_aviso(conn, "idosa-1", "O ESP32 da casa parou de enviar sinal", AGORA)
    registrar_aviso(conn, "idosa-1", "sono:2026-11-11", AGORA)
    registrar_aviso(conn, "idosa-2", "O ESP32 da casa parou de enviar sinal", AGORA)

    limpar_avisos_de_episodio(conn, "idosa-1", prefixo_preservado="sono:")

    assert not aviso_ja_enviado(conn, "idosa-1", "O ESP32 da casa parou de enviar sinal")
    assert aviso_ja_enviado(conn, "idosa-1", "sono:2026-11-11")
    assert aviso_ja_enviado(conn, "idosa-2", "O ESP32 da casa parou de enviar sinal")
