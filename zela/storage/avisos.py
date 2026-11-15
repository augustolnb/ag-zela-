"""Avisos à família já enviados, para não repetir a cada verificação nem a cada deploy.

Antes ficava num set em memória, apagado a cada reinício do backend: com o
ESP32 desligado, cada deploy repetia "O ESP32 da casa parou de enviar sinal".
Chave: o motivo do AVISO, ou "sono:YYYY-MM-DD" para o aviso de sono.
"""

import sqlite3
from datetime import datetime


def aviso_ja_enviado(conn: sqlite3.Connection, idoso_id: str, chave: str) -> bool:
    linha = conn.execute(
        "SELECT 1 FROM aviso_enviado WHERE idoso_id = ? AND chave = ?", (idoso_id, chave)
    ).fetchone()
    return linha is not None


def registrar_aviso(conn: sqlite3.Connection, idoso_id: str, chave: str, agora: datetime) -> None:
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO aviso_enviado (idoso_id, chave, enviado_em) VALUES (?, ?, ?)",
            (idoso_id, chave, agora.isoformat()),
        )


def limpar_avisos_de_episodio(conn: sqlite3.Connection, idoso_id: str, prefixo_preservado: str) -> None:
    """Quando tudo volta ao normal, um novo episódio pode avisar de novo; o de sono é por dia."""
    with conn:
        conn.execute(
            "DELETE FROM aviso_enviado WHERE idoso_id = ? AND chave NOT LIKE ? || '%'",
            (idoso_id, prefixo_preservado),
        )
