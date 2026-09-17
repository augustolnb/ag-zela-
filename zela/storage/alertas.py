import sqlite3
from datetime import datetime

from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta, StatusAlerta


def salvar_alerta(conn: sqlite3.Connection, alerta: Alerta, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO alerta (idoso_id, nivel, destinatario, canal, mensagem, status, simulado, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            idoso_id,
            alerta.nivel.value,
            alerta.destinatario,
            alerta.canal.value,
            alerta.mensagem,
            alerta.status.value,
            int(alerta.simulado),
            alerta.timestamp.isoformat(),
        ),
    )
    conn.commit()


def listar_alertas(conn: sqlite3.Connection, idoso_id: str) -> list[Alerta]:
    linhas = conn.execute(
        "SELECT * FROM alerta WHERE idoso_id = ? ORDER BY timestamp", (idoso_id,)
    ).fetchall()
    return [
        Alerta(
            nivel=NivelAlerta(linha["nivel"]),
            destinatario=linha["destinatario"],
            canal=CanalAlerta(linha["canal"]),
            mensagem=linha["mensagem"],
            status=StatusAlerta(linha["status"]),
            simulado=bool(linha["simulado"]),
            timestamp=datetime.fromisoformat(linha["timestamp"]),
        )
        for linha in linhas
    ]
