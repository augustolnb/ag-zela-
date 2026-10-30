import sqlite3
from datetime import datetime, timedelta

from zela.domain.monitoramento import classificar_por_regra
from zela.domain.sono import NOITES_BASE, avaliar_sono
from zela.models.monitoramento import (
    EventoMonitoramento,
    FonteSensor,
    TipoLeitura,
)
from zela.models.monitoramento import LeituraSensor

JANELA_LOOKBACK_HORAS = 48.0


def salvar_leitura(conn: sqlite3.Connection, leitura: LeituraSensor, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO leitura_sensor (idoso_id, fonte, tipo, valor, unidade, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            idoso_id,
            leitura.fonte.value,
            leitura.tipo.value,
            leitura.valor,
            leitura.unidade,
            leitura.timestamp.isoformat(),
        ),
    )
    conn.commit()


def listar_leituras_recentes(
    conn: sqlite3.Connection, idoso_id: str, desde: datetime
) -> list[LeituraSensor]:
    linhas = conn.execute(
        "SELECT * FROM leitura_sensor WHERE idoso_id = ? AND timestamp >= ? ORDER BY timestamp",
        (idoso_id, desde.isoformat()),
    ).fetchall()
    return [
        LeituraSensor(
            fonte=FonteSensor(linha["fonte"]),
            tipo=TipoLeitura(linha["tipo"]),
            valor=linha["valor"],
            unidade=linha["unidade"],
            timestamp=datetime.fromisoformat(linha["timestamp"]),
        )
        for linha in linhas
    ]


def aplicar_classificacao(
    conn: sqlite3.Connection,
    idoso_id: str,
    agora: datetime,
    janela_horas: float = JANELA_LOOKBACK_HORAS,
) -> EventoMonitoramento:
    desde = agora - timedelta(hours=janela_horas)
    leituras = listar_leituras_recentes(conn, idoso_id, desde)

    return classificar_por_regra(leituras, agora)


def avaliar_sono_recente(
    conn: sqlite3.Connection, idoso_id: str, agora: datetime
) -> EventoMonitoramento | None:
    desde = agora - timedelta(days=NOITES_BASE + 1)
    leituras = listar_leituras_recentes(conn, idoso_id, desde)
    return avaliar_sono([l for l in leituras if l.tipo == TipoLeitura.SONO], agora)
