import json
import sqlite3
from datetime import datetime, time

from zela.domain.rotina import calcular_lembretes_pendentes
from zela.domain.rotina import registrar_confirmacao as registrar_confirmacao_dominio
from zela.models.rotina import (
    CanalConfirmacao,
    ConfirmacaoMedicacao,
    Dosagem,
    Medicamento,
    StatusConfirmacao,
)


def salvar_medicamento(conn: sqlite3.Connection, medicamento: Medicamento, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO medicamento
            (id, idoso_id, nome, dosagem_quantidade, dosagem_unidade, horarios, dias_semana, ativo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nome = excluded.nome,
            dosagem_quantidade = excluded.dosagem_quantidade,
            dosagem_unidade = excluded.dosagem_unidade,
            horarios = excluded.horarios,
            dias_semana = excluded.dias_semana,
            ativo = excluded.ativo
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
