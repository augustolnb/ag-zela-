import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, time

from zela.domain.compromisso_lembretes import calcular_horarios_lembrete_compromisso
from zela.domain.rotina import calcular_lembretes_pendentes
from zela.domain.rotina import registrar_confirmacao as registrar_confirmacao_dominio
from zela.models.rotina import (
    CanalConfirmacao,
    Compromisso,
    ConfirmacaoMedicacao,
    Dosagem,
    Medicamento,
    StatusConfirmacao,
    TipoCompromisso,
)


def salvar_medicamento(conn: sqlite3.Connection, medicamento: Medicamento, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO medicamento
            (id, idoso_id, nome, dosagem_quantidade, dosagem_unidade, horarios, dias_semana, ativo, bula)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nome = excluded.nome,
            dosagem_quantidade = excluded.dosagem_quantidade,
            dosagem_unidade = excluded.dosagem_unidade,
            horarios = excluded.horarios,
            dias_semana = excluded.dias_semana,
            ativo = excluded.ativo,
            bula = excluded.bula
        """,
        (
            medicamento.id,
            idoso_id,
            medicamento.nome,
            medicamento.dosagem.quantidade,
            medicamento.dosagem.unidade,
            json.dumps([h.isoformat() for h in medicamento.horarios]),
            json.dumps(medicamento.dias_semana),
            int(medicamento.ativo),
            medicamento.bula,
        ),
    )
    conn.commit()


def _linha_para_medicamento(linha: sqlite3.Row) -> Medicamento:
    return Medicamento(
        id=linha["id"],
        nome=linha["nome"],
        dosagem=Dosagem(quantidade=linha["dosagem_quantidade"], unidade=linha["dosagem_unidade"]),
        horarios=[time.fromisoformat(h) for h in json.loads(linha["horarios"])],
        dias_semana=json.loads(linha["dias_semana"]),
        ativo=bool(linha["ativo"]),
        bula=linha["bula"],
    )


def listar_medicamentos(conn: sqlite3.Connection, idoso_id: str) -> list[Medicamento]:
    linhas = conn.execute("SELECT * FROM medicamento WHERE idoso_id = ?", (idoso_id,)).fetchall()
    return [_linha_para_medicamento(linha) for linha in linhas]


def salvar_confirmacao(conn: sqlite3.Connection, confirmacao: ConfirmacaoMedicacao) -> None:
    conn.execute(
        """
        INSERT INTO confirmacao_medicacao
            (medicamento_id, horario_previsto, horario_confirmado, status, canal)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            confirmacao.medicamento_id,
            confirmacao.horario_previsto.isoformat(),
            confirmacao.horario_confirmado.isoformat() if confirmacao.horario_confirmado else None,
            confirmacao.status.value,
            confirmacao.canal.value,
        ),
    )
    conn.commit()


def listar_confirmacoes_do_dia(
    conn: sqlite3.Connection, idoso_id: str, dia: datetime
) -> list[ConfirmacaoMedicacao]:
    linhas = conn.execute(
        """
        SELECT cm.* FROM confirmacao_medicacao cm
        JOIN medicamento m ON m.id = cm.medicamento_id
        WHERE m.idoso_id = ? AND date(cm.horario_previsto) = date(?)
        """,
        (idoso_id, dia.isoformat()),
    ).fetchall()
    return [
        ConfirmacaoMedicacao(
            medicamento_id=linha["medicamento_id"],
            horario_previsto=datetime.fromisoformat(linha["horario_previsto"]),
            horario_confirmado=(
                datetime.fromisoformat(linha["horario_confirmado"])
                if linha["horario_confirmado"]
                else None
            ),
            status=StatusConfirmacao(linha["status"]),
            canal=CanalConfirmacao(linha["canal"]),
        )
        for linha in linhas
    ]


def aplicar_lembretes_pendentes(
    conn: sqlite3.Connection, idoso_id: str, agora: datetime
) -> list[Medicamento]:
    medicamentos = listar_medicamentos(conn, idoso_id)
    confirmacoes = listar_confirmacoes_do_dia(conn, idoso_id, agora)
    return calcular_lembretes_pendentes(medicamentos, confirmacoes, agora)


def aplicar_confirmacao(
    conn: sqlite3.Connection,
    medicamento: Medicamento,
    horario_previsto: datetime,
    agora: datetime,
    canal: CanalConfirmacao = CanalConfirmacao.WHATSAPP,
) -> ConfirmacaoMedicacao:
    confirmacao = registrar_confirmacao_dominio(medicamento, horario_previsto, agora, canal)
    salvar_confirmacao(conn, confirmacao)
    return confirmacao


def salvar_compromisso(conn: sqlite3.Connection, compromisso: Compromisso, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO compromisso (id, idoso_id, titulo, data_hora, local, tipo, google_sync_pendente)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(id) DO UPDATE SET
            titulo = excluded.titulo,
            data_hora = excluded.data_hora,
            local = excluded.local,
            tipo = excluded.tipo,
            google_sync_pendente = 1
        """,
        (
            compromisso.id,
            idoso_id,
            compromisso.titulo,
            compromisso.data_hora.isoformat(),
            compromisso.local,
            compromisso.tipo.value,
        ),
    )
    agora = datetime.now()
    for tipo, horario_alvo in calcular_horarios_lembrete_compromisso(compromisso).items():
        if horario_alvo > agora:
            conn.execute(
                "DELETE FROM lembrete_compromisso_enviado WHERE compromisso_id = ? AND tipo_lembrete = ?",
                (compromisso.id, tipo),
            )
    conn.commit()


def _linha_para_compromisso(linha: sqlite3.Row) -> Compromisso:
    # model_construct pula a validação Pydantic (inclusive o validador que
    # rejeita data_hora no passado) — correto aqui porque um compromisso já
    # registrado pode legitimamente estar no passado, e reconstruí-lo a
    # partir do storage não deve falhar por causa disso. A validação
    # continua valendo normalmente na criação, via Compromisso(...) direto.
    return Compromisso.model_construct(
        id=linha["id"],
        titulo=linha["titulo"],
        data_hora=datetime.fromisoformat(linha["data_hora"]),
        local=linha["local"],
        tipo=TipoCompromisso(linha["tipo"]),
    )


def listar_compromissos(conn: sqlite3.Connection, idoso_id: str) -> list[Compromisso]:
    linhas = conn.execute(
        "SELECT * FROM compromisso WHERE idoso_id = ? AND removido = 0 ORDER BY data_hora",
        (idoso_id,),
    ).fetchall()
    return [_linha_para_compromisso(linha) for linha in linhas]


def remover_compromisso(conn: sqlite3.Connection, compromisso_id: str, idoso_id: str) -> None:
    conn.execute(
        "UPDATE compromisso SET removido = 1, google_sync_pendente = 1 WHERE id = ? AND idoso_id = ?",
        (compromisso_id, idoso_id),
    )
    conn.commit()


def listar_tipos_lembrete_enviados(conn: sqlite3.Connection, compromisso_id: str) -> set[str]:
    linhas = conn.execute(
        "SELECT tipo_lembrete FROM lembrete_compromisso_enviado WHERE compromisso_id = ?",
        (compromisso_id,),
    ).fetchall()
    return {linha["tipo_lembrete"] for linha in linhas}


def registrar_lembrete_compromisso_enviado(
    conn: sqlite3.Connection, compromisso_id: str, tipo_lembrete: str, enviado_em: datetime
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO lembrete_compromisso_enviado (compromisso_id, tipo_lembrete, enviado_em) "
        "VALUES (?, ?, ?)",
        (compromisso_id, tipo_lembrete, enviado_em.isoformat()),
    )
    conn.commit()


def listar_compromissos_removidos_pendentes_cancelamento(
    conn: sqlite3.Connection, idoso_id: str
) -> list[Compromisso]:
    linhas = conn.execute(
        """
        SELECT c.* FROM compromisso c
        WHERE c.idoso_id = ? AND c.removido = 1
        AND NOT EXISTS (
            SELECT 1 FROM lembrete_compromisso_enviado l
            WHERE l.compromisso_id = c.id AND l.tipo_lembrete = 'cancelamento'
        )
        """,
        (idoso_id,),
    ).fetchall()
    return [_linha_para_compromisso(linha) for linha in linhas]


@dataclass
class CompromissoPendenteSync:
    compromisso: Compromisso
    google_event_id: str | None
    removido: bool


def listar_compromissos_pendentes_sync_google(
    conn: sqlite3.Connection, idoso_id: str
) -> list[CompromissoPendenteSync]:
    linhas = conn.execute(
        "SELECT * FROM compromisso WHERE idoso_id = ? AND google_sync_pendente = 1", (idoso_id,)
    ).fetchall()
    return [
        CompromissoPendenteSync(
            compromisso=_linha_para_compromisso(linha),
            google_event_id=linha["google_event_id"],
            removido=bool(linha["removido"]),
        )
        for linha in linhas
    ]


def marcar_google_sync_feito(
    conn: sqlite3.Connection, compromisso_id: str, google_event_id: str | None = None
) -> None:
    if google_event_id is not None:
        conn.execute(
            "UPDATE compromisso SET google_sync_pendente = 0, google_event_id = ? WHERE id = ?",
            (google_event_id, compromisso_id),
        )
    else:
        conn.execute(
            "UPDATE compromisso SET google_sync_pendente = 0 WHERE id = ?", (compromisso_id,)
        )
    conn.commit()
