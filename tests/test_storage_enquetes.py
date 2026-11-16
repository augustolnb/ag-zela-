from datetime import datetime, timedelta

from zela.storage.db import conectar
from zela.storage.enquetes import (
    EnqueteLembrete,
    agendar_relembrete,
    listar_relembretes_devidos,
    marcar_relembrado,
    obter_enquete,
    salvar_enquete,
)

AGORA = datetime(2026, 11, 15, 19, 44)
PREVISTO = datetime(2026, 11, 15, 19, 43)


def _enquete(chave="ABC", idoso="idosa-1"):
    return EnqueteLembrete(chave=chave, idoso_id=idoso, medicamento_id="m1", horario_previsto=PREVISTO)


def test_salva_e_obtem_enquete_pela_chave(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    salvar_enquete(conn, _enquete(), AGORA)
    assert obter_enquete(conn, "ABC") == _enquete()


def test_obter_enquete_desconhecida_devolve_none(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    assert obter_enquete(conn, "XYZ") is None


def test_salvar_a_mesma_chave_duas_vezes_nao_falha(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    salvar_enquete(conn, _enquete(), AGORA)
    salvar_enquete(conn, _enquete(), AGORA)
    assert obter_enquete(conn, "ABC") == _enquete()


def test_agendar_relembrete_so_uma_vez(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    salvar_enquete(conn, _enquete(), AGORA)
    assert agendar_relembrete(conn, "ABC", AGORA + timedelta(minutes=30)) is True
    assert agendar_relembrete(conn, "ABC", AGORA + timedelta(minutes=60)) is False
    assert listar_relembretes_devidos(conn, "idosa-1", AGORA + timedelta(minutes=30)) == [_enquete()]
    assert agendar_relembrete(conn, "desconhecida", AGORA) is False


def test_lista_relembretes_devidos_e_marca_relembrado(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    salvar_enquete(conn, _enquete(), AGORA)
    salvar_enquete(conn, _enquete("OUTRA", idoso="idosa-2"), AGORA)
    agendar_relembrete(conn, "ABC", AGORA + timedelta(minutes=30))
    agendar_relembrete(conn, "OUTRA", AGORA + timedelta(minutes=30))

    assert listar_relembretes_devidos(conn, "idosa-1", AGORA + timedelta(minutes=29)) == []
    assert listar_relembretes_devidos(conn, "idosa-1", AGORA + timedelta(minutes=31)) == [_enquete()]

    marcar_relembrado(conn, "ABC")
    assert listar_relembretes_devidos(conn, "idosa-1", AGORA + timedelta(minutes=31)) == []
