"""Episódios de sintoma e fila de notificações à família.

As funções de escrita não fazem commit: quem chama agrupa em `with conn:`, para
que encerrar um episódio e enfileirar seus avisos seja uma única transação.
"""
import json
import sqlite3
from datetime import datetime

from zela.models.episodio import (
    EpisodioSintoma,
    EstadoEpisodio,
    NotificacaoFamilia,
    StatusNotificacao,
    TipoEpisodio,
    TipoNotificacao,
)


def _para_episodio(linha: sqlite3.Row) -> EpisodioSintoma:
    return EpisodioSintoma(
        id=linha["id"],
        idoso_id=linha["idoso_id"],
        tipo=TipoEpisodio(linha["tipo"]),
        texto=linha["texto"],
        sintomas=json.loads(linha["sintomas"]),
        iniciado_em=datetime.fromisoformat(linha["iniciado_em"]),
        prazo_em=datetime.fromisoformat(linha["prazo_em"]),
        estado=EstadoEpisodio(linha["estado"]),
        encerrado_em=datetime.fromisoformat(linha["encerrado_em"]) if linha["encerrado_em"] else None,
    )


def abrir_episodio(
    conn: sqlite3.Connection,
    idoso_id: str,
    tipo: TipoEpisodio,
    texto: str,
    sintomas: list[str],
    iniciado_em: datetime,
    prazo_em: datetime,
    estado: EstadoEpisodio = EstadoEpisodio.AGUARDANDO,
    encerrado_em: datetime | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO episodio_sintoma
            (idoso_id, tipo, texto, sintomas, iniciado_em, prazo_em, estado, encerrado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            idoso_id,
            tipo.value,
            texto,
            json.dumps(sintomas, ensure_ascii=False),
            iniciado_em.isoformat(),
            prazo_em.isoformat(),
            estado.value,
            encerrado_em.isoformat() if encerrado_em else None,
        ),
    )
    return cursor.lastrowid


def obter_episodio_aberto(conn: sqlite3.Connection, idoso_id: str) -> EpisodioSintoma | None:
    linha = conn.execute(
        "SELECT * FROM episodio_sintoma WHERE idoso_id = ? AND estado = ? ORDER BY id DESC LIMIT 1",
        (idoso_id, EstadoEpisodio.AGUARDANDO.value),
    ).fetchone()
    return _para_episodio(linha) if linha else None


def acrescentar_relato(conn: sqlite3.Connection, episodio: EpisodioSintoma, texto: str, sintomas: list[str]) -> None:
    combinados = episodio.sintomas + [s for s in sintomas if s not in episodio.sintomas]
    conn.execute(
        "UPDATE episodio_sintoma SET texto = ?, sintomas = ? WHERE id = ?",
        (f"{episodio.texto} / {texto}", json.dumps(combinados, ensure_ascii=False), episodio.id),
    )


def encerrar_episodio(conn: sqlite3.Connection, episodio_id: int, estado: EstadoEpisodio, agora: datetime) -> bool:
    cursor = conn.execute(
        "UPDATE episodio_sintoma SET estado = ?, encerrado_em = ? WHERE id = ? AND estado = ?",
        (estado.value, agora.isoformat(), episodio_id, EstadoEpisodio.AGUARDANDO.value),
    )
    return cursor.rowcount == 1


def listar_vencidos(conn: sqlite3.Connection, idoso_id: str, agora: datetime) -> list[EpisodioSintoma]:
    linhas = conn.execute(
        "SELECT * FROM episodio_sintoma WHERE idoso_id = ? AND estado = ? AND prazo_em <= ?",
        (idoso_id, EstadoEpisodio.AGUARDANDO.value, agora.isoformat()),
    ).fetchall()
    return [_para_episodio(linha) for linha in linhas]


def houve_notificacao_desde(conn: sqlite3.Connection, idoso_id: str, desde: datetime) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM episodio_sintoma WHERE idoso_id = ? AND estado = ? AND encerrado_em >= ? LIMIT 1",
            (idoso_id, EstadoEpisodio.NOTIFICADO.value, desde.isoformat()),
        ).fetchone()
        is not None
    )


def listar_cancelados_desde(conn: sqlite3.Connection, idoso_id: str, desde: datetime) -> list[EpisodioSintoma]:
    linhas = conn.execute(
        """
        SELECT * FROM episodio_sintoma
        WHERE idoso_id = ? AND estado IN (?, ?) AND encerrado_em >= ?
        ORDER BY encerrado_em
        """,
        (
            idoso_id,
            EstadoEpisodio.CANCELADO_ESTOU_BEM.value,
            EstadoEpisodio.CANCELADO_RECUSA.value,
            desde.isoformat(),
        ),
    ).fetchall()
    return [_para_episodio(linha) for linha in linhas]


def enfileirar_notificacao(
    conn: sqlite3.Connection,
    episodio_id: int,
    tipo: TipoNotificacao,
    destinatario: str,
    telefone: str,
    mensagem: str,
    agora: datetime,
) -> None:
    conn.execute(
        """
        INSERT INTO notificacao_familia
            (episodio_id, tipo, destinatario, telefone, mensagem, status, tentativas, proxima_tentativa_em)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (episodio_id, tipo.value, destinatario, telefone, mensagem, StatusNotificacao.PENDENTE.value, agora.isoformat()),
    )


def listar_notificacoes_devidas(conn: sqlite3.Connection, idoso_id: str, agora: datetime) -> list[NotificacaoFamilia]:
    linhas = conn.execute(
        """
        SELECT n.* FROM notificacao_familia n
        JOIN episodio_sintoma e ON e.id = n.episodio_id
        WHERE e.idoso_id = ? AND n.status = ? AND n.proxima_tentativa_em <= ?
        ORDER BY n.id
        """,
        (idoso_id, StatusNotificacao.PENDENTE.value, agora.isoformat()),
    ).fetchall()
    return [
        NotificacaoFamilia(
            id=linha["id"],
            episodio_id=linha["episodio_id"],
            tipo=TipoNotificacao(linha["tipo"]),
            destinatario=linha["destinatario"],
            telefone=linha["telefone"],
            mensagem=linha["mensagem"],
            tentativas=linha["tentativas"],
        )
        for linha in linhas
    ]


def atualizar_notificacao(
    conn: sqlite3.Connection, notificacao_id: int, status: StatusNotificacao, tentativas: int, proxima_tentativa: datetime
) -> None:
    conn.execute(
        "UPDATE notificacao_familia SET status = ?, tentativas = ?, proxima_tentativa_em = ? WHERE id = ?",
        (status.value, tentativas, proxima_tentativa.isoformat(), notificacao_id),
    )


def ninguem_recebeu_aviso(conn: sqlite3.Connection, episodio_id: int) -> bool:
    linha = conn.execute(
        """
        SELECT COUNT(*) FROM notificacao_familia
        WHERE episodio_id = ? AND tipo = ? AND status != ?
        """,
        (episodio_id, TipoNotificacao.AVISO.value, StatusNotificacao.FALHOU.value),
    ).fetchone()
    return linha[0] == 0


def marcar_paciente_orientado(conn: sqlite3.Connection, episodio_id: int) -> bool:
    cursor = conn.execute(
        "UPDATE episodio_sintoma SET paciente_orientado = 1 WHERE id = ? AND paciente_orientado = 0",
        (episodio_id,),
    )
    return cursor.rowcount == 1
