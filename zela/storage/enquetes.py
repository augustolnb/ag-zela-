"""Enquetes de lembrete de remédio enviadas, para ligar cada voto ao remédio e ao horário."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EnqueteLembrete:
    chave: str
    idoso_id: str
    medicamento_id: str
    horario_previsto: datetime


def _de_linha(linha) -> EnqueteLembrete:
    return EnqueteLembrete(
        chave=linha[0],
        idoso_id=linha[1],
        medicamento_id=linha[2],
        horario_previsto=datetime.fromisoformat(linha[3]),
    )


_COLUNAS = "chave, idoso_id, medicamento_id, horario_previsto"


def salvar_enquete(conn: sqlite3.Connection, enquete: EnqueteLembrete, enviada_em: datetime) -> None:
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO enquete_lembrete "
            "(chave, idoso_id, medicamento_id, horario_previsto, enviada_em) VALUES (?, ?, ?, ?, ?)",
            (
                enquete.chave,
                enquete.idoso_id,
                enquete.medicamento_id,
                enquete.horario_previsto.isoformat(),
                enviada_em.isoformat(),
            ),
        )


def obter_enquete(conn: sqlite3.Connection, chave: str) -> EnqueteLembrete | None:
    linha = conn.execute(f"SELECT {_COLUNAS} FROM enquete_lembrete WHERE chave = ?", (chave,)).fetchone()
    return _de_linha(linha) if linha else None


def agendar_relembrete(conn: sqlite3.Connection, chave: str, quando: datetime) -> bool:
    """Agenda o reenvio uma única vez por enquete; devolve se agendou agora."""
    with conn:
        cursor = conn.execute(
            "UPDATE enquete_lembrete SET relembrar_em = ? WHERE chave = ? AND relembrar_em IS NULL",
            (quando.isoformat(), chave),
        )
    return cursor.rowcount == 1


def listar_relembretes_devidos(
    conn: sqlite3.Connection, idoso_id: str, agora: datetime
) -> list[EnqueteLembrete]:
    linhas = conn.execute(
        f"SELECT {_COLUNAS} FROM enquete_lembrete "
        "WHERE idoso_id = ? AND relembrado = 0 AND relembrar_em IS NOT NULL AND relembrar_em <= ? "
        "ORDER BY relembrar_em",
        (idoso_id, agora.isoformat()),
    ).fetchall()
    return [_de_linha(linha) for linha in linhas]


def marcar_relembrado(conn: sqlite3.Connection, chave: str) -> None:
    with conn:
        conn.execute("UPDATE enquete_lembrete SET relembrado = 1 WHERE chave = ?", (chave,))
