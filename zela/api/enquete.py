"""Voto na enquete do lembrete de remédio: confirma a dose ou agenda o reenvio, sem a IA."""

import sqlite3
from datetime import datetime

from zela.domain.enquete_remedio import (
    INTERVALO_RELEMBRAR,
    RESPOSTA_AINDA_NAO,
    RESPOSTA_AINDA_NAO_SEM_REENVIO,
    chave_da_mensagem,
    interpretar_voto,
    resposta_tomei,
)
from zela.models.rotina import StatusConfirmacao
from zela.storage.enquetes import agendar_relembrete, obter_enquete
from zela.storage.rotina import aplicar_confirmacao, listar_confirmacoes_do_dia, listar_medicamentos

_STATUS_DOSE_TOMADA = (StatusConfirmacao.CONFIRMADO, StatusConfirmacao.ATRASADO)


def processar_voto(
    conn: sqlite3.Connection, id_idoso: str, chave_enquete: str, selecionadas: list[str], agora: datetime
) -> str | None:
    """Devolve o texto a responder ao idoso, ou None quando não há o que responder."""
    escolha = interpretar_voto(selecionadas)
    if escolha is None:
        return None
    chave = chave_da_mensagem(chave_enquete)
    if not chave:
        return None
    enquete = obter_enquete(conn, chave)
    if enquete is None or enquete.idoso_id != id_idoso:
        return None
    medicamento = next((m for m in listar_medicamentos(conn, id_idoso) if m.id == enquete.medicamento_id), None)
    if medicamento is None:
        return None
    ja_tomada = any(
        c.medicamento_id == enquete.medicamento_id
        and c.horario_previsto == enquete.horario_previsto
        and c.status in _STATUS_DOSE_TOMADA
        for c in listar_confirmacoes_do_dia(conn, id_idoso, enquete.horario_previsto)
    )
    if ja_tomada:
        return None

    if escolha == "tomei":
        aplicar_confirmacao(conn, medicamento, horario_previsto=enquete.horario_previsto, agora=agora)
        return resposta_tomei(medicamento)

    quando = agora + INTERVALO_RELEMBRAR
    if quando.date() != enquete.horario_previsto.date():
        # O reenvio só vale no mesmo dia: não prometer o que não vai acontecer.
        return RESPOSTA_AINDA_NAO_SEM_REENVIO
    if agendar_relembrete(conn, enquete.chave, quando):
        return RESPOSTA_AINDA_NAO
    return None
