from datetime import datetime, time, timedelta

from zela.api.enquete import processar_voto
from zela.domain.enquete_remedio import INTERVALO_RELEMBRAR, RESPOSTA_AINDA_NAO, resposta_tomei
from zela.models.rotina import Dosagem, Medicamento, StatusConfirmacao
from zela.storage.db import conectar
from zela.storage.enquetes import EnqueteLembrete, listar_relembretes_devidos, salvar_enquete
from zela.storage.rotina import listar_confirmacoes_do_dia, salvar_medicamento

PREVISTO = datetime(2026, 11, 15, 19, 43)
AGORA = datetime(2026, 11, 15, 19, 50)


def _preparar(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    medicamento = Medicamento(
        id="m1", nome="dapagliflozina", dosagem=Dosagem(quantidade=1, unidade="comprimido"), horarios=[time(19, 43)]
    )
    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")
    salvar_enquete(
        conn, EnqueteLembrete(chave="ABC", idoso_id="idosa-1", medicamento_id="m1", horario_previsto=PREVISTO), PREVISTO
    )
    return conn, medicamento


def test_voto_tomei_registra_confirmacao_e_responde(tmp_path):
    conn, medicamento = _preparar(tmp_path)

    resposta = processar_voto(conn, "idosa-1", "ABC", ["✅ Tomei"], AGORA)

    assert resposta == resposta_tomei(medicamento)
    confirmacoes = listar_confirmacoes_do_dia(conn, "idosa-1", AGORA)
    assert len(confirmacoes) == 1
    assert confirmacoes[0].horario_previsto == PREVISTO
    assert confirmacoes[0].status == StatusConfirmacao.CONFIRMADO


def test_voto_tomei_depois_de_30_min_fica_atrasado(tmp_path):
    conn, _ = _preparar(tmp_path)

    processar_voto(conn, "idosa-1", "ABC", ["✅ Tomei"], PREVISTO + timedelta(minutes=45))

    assert listar_confirmacoes_do_dia(conn, "idosa-1", AGORA)[0].status == StatusConfirmacao.ATRASADO


def test_voto_repetido_nao_duplica_nem_responde(tmp_path):
    conn, _ = _preparar(tmp_path)

    processar_voto(conn, "idosa-1", "ABC", ["✅ Tomei"], AGORA)
    segunda = processar_voto(conn, "idosa-1", "ABC", ["✅ Tomei"], AGORA)

    assert segunda is None
    assert len(listar_confirmacoes_do_dia(conn, "idosa-1", AGORA)) == 1


def test_voto_ainda_nao_agenda_reenvio_e_responde(tmp_path):
    conn, _ = _preparar(tmp_path)

    resposta = processar_voto(conn, "idosa-1", "ABC", ["⏰ Ainda não"], AGORA)

    assert resposta == RESPOSTA_AINDA_NAO
    assert listar_confirmacoes_do_dia(conn, "idosa-1", AGORA) == []
    assert listar_relembretes_devidos(conn, "idosa-1", AGORA + INTERVALO_RELEMBRAR - timedelta(seconds=1)) == []
    assert len(listar_relembretes_devidos(conn, "idosa-1", AGORA + INTERVALO_RELEMBRAR)) == 1


def test_segundo_ainda_nao_na_mesma_enquete_nao_responde(tmp_path):
    conn, _ = _preparar(tmp_path)

    processar_voto(conn, "idosa-1", "ABC", ["⏰ Ainda não"], AGORA)
    segunda = processar_voto(conn, "idosa-1", "ABC", ["⏰ Ainda não"], AGORA + timedelta(minutes=5))

    assert segunda is None
    assert len(listar_relembretes_devidos(conn, "idosa-1", AGORA + INTERVALO_RELEMBRAR)) == 1


def test_voto_vazio_ou_enquete_desconhecida_devolve_none(tmp_path):
    conn, _ = _preparar(tmp_path)

    assert processar_voto(conn, "idosa-1", "ABC", [], AGORA) is None
    assert processar_voto(conn, "idosa-1", "XYZ", ["✅ Tomei"], AGORA) is None
    assert processar_voto(conn, "idosa-2", "ABC", ["✅ Tomei"], AGORA) is None
    assert listar_confirmacoes_do_dia(conn, "idosa-1", AGORA) == []


def test_chave_com_prefixo_encontra_a_enquete(tmp_path):
    conn, medicamento = _preparar(tmp_path)

    resposta = processar_voto(conn, "idosa-1", "true_1@lid_ABC", ["✅ Tomei"], AGORA)

    assert resposta == resposta_tomei(medicamento)


def test_voto_sem_chave_nao_confirma_nada(tmp_path):
    conn, _ = _preparar(tmp_path)
    salvar_enquete(
        conn, EnqueteLembrete(chave="", idoso_id="idosa-1", medicamento_id="m1", horario_previsto=PREVISTO), PREVISTO
    )

    assert processar_voto(conn, "idosa-1", "", ["✅ Tomei"], AGORA) is None
    assert listar_confirmacoes_do_dia(conn, "idosa-1", AGORA) == []


def test_ainda_nao_perto_da_meia_noite_nao_promete_reenvio(tmp_path):
    from zela.domain.enquete_remedio import RESPOSTA_AINDA_NAO_SEM_REENVIO

    conn, _ = _preparar(tmp_path)
    tarde = datetime(2026, 11, 15, 23, 45)

    resposta = processar_voto(conn, "idosa-1", "ABC", ["⏰ Ainda não"], tarde)

    assert resposta == RESPOSTA_AINDA_NAO_SEM_REENVIO
    assert listar_relembretes_devidos(conn, "idosa-1", tarde + timedelta(hours=2)) == []
