import sqlite3
from datetime import datetime

from zela.domain.emergencia import EstadoEscalonamento, EstagioEscalonamento, decidir_proxima_acao
from zela.models.alertas import Alerta
from zela.models.monitoramento import EventoMonitoramento
from zela.models.perfil import PerfilIdoso


def obter_estado(conn: sqlite3.Connection, idoso_id: str) -> EstadoEscalonamento:
    linha = conn.execute(
        "SELECT * FROM estado_escalonamento WHERE idoso_id = ?", (idoso_id,)
    ).fetchone()
    if linha is None:
        return EstadoEscalonamento()
    return EstadoEscalonamento(
        estagio=EstagioEscalonamento(linha["estagio"]),
        iniciado_em=datetime.fromisoformat(linha["iniciado_em"]) if linha["iniciado_em"] else None,
    )


def salvar_estado(conn: sqlite3.Connection, idoso_id: str, estado: EstadoEscalonamento) -> None:
    conn.execute(
        """
        INSERT INTO estado_escalonamento (idoso_id, estagio, iniciado_em)
        VALUES (?, ?, ?)
        ON CONFLICT(idoso_id) DO UPDATE SET
            estagio = excluded.estagio,
            iniciado_em = excluded.iniciado_em
        """,
        (
            idoso_id,
            estado.estagio.value,
            estado.iniciado_em.isoformat() if estado.iniciado_em else None,
        ),
    )
    conn.commit()


def aplicar_escalonamento(
    conn: sqlite3.Connection,
    idoso_id: str,
    evento: EventoMonitoramento,
    perfil: PerfilIdoso,
    agora: datetime,
) -> list[Alerta]:
    estado_atual = obter_estado(conn, idoso_id)
    novo_estado, alertas = decidir_proxima_acao(evento, perfil, estado_atual, agora)
    salvar_estado(conn, idoso_id, novo_estado)
    return alertas
