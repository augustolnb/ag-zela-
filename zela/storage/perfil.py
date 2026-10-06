import json
import sqlite3

from zela.models.perfil import ContatoFamiliar, PerfilIdoso


def salvar_perfil(conn: sqlite3.Connection, perfil: PerfilIdoso, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO perfil_idoso (
            id, nome, telefone, data_nascimento, condicoes_medicas, contatos_familiares, lid_whatsapp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nome = excluded.nome,
            telefone = excluded.telefone,
            data_nascimento = excluded.data_nascimento,
            condicoes_medicas = excluded.condicoes_medicas,
            contatos_familiares = excluded.contatos_familiares,
            lid_whatsapp = excluded.lid_whatsapp
        """,
        (
            idoso_id,
            perfil.nome,
            perfil.telefone,
            perfil.data_nascimento.isoformat(),
            json.dumps(perfil.condicoes_medicas),
            json.dumps([c.model_dump() for c in perfil.contatos_familiares]),
            perfil.lid_whatsapp,
        ),
    )
    conn.commit()


def obter_perfil(conn: sqlite3.Connection, idoso_id: str) -> PerfilIdoso | None:
    linha = conn.execute("SELECT * FROM perfil_idoso WHERE id = ?", (idoso_id,)).fetchone()
    if linha is None:
        return None
    return PerfilIdoso(
        nome=linha["nome"],
        telefone=linha["telefone"],
        data_nascimento=linha["data_nascimento"],
        condicoes_medicas=json.loads(linha["condicoes_medicas"]),
        contatos_familiares=[
            ContatoFamiliar(**c) for c in json.loads(linha["contatos_familiares"])
        ],
        lid_whatsapp=linha["lid_whatsapp"],
    )
