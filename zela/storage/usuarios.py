"""Usuários do painel da família: login com usuário e senha.

A senha nunca é guardada: só um hash scrypt com sal aleatório por usuário,
no formato "scrypt$n$r$p$<sal hex>$<hash hex>".
"""

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime

TAMANHO_MINIMO_SENHA = 8
_N, _R, _P = 2**14, 8, 1


def _normalizar(usuario: str) -> str:
    return usuario.strip().lower()


def _hash(senha: str, sal: bytes, n: int = _N, r: int = _R, p: int = _P) -> bytes:
    return hashlib.scrypt(senha.encode("utf-8"), salt=sal, n=n, r=r, p=p, dklen=32)


def _gerar_hash(senha: str) -> str:
    sal = secrets.token_bytes(16)
    return f"scrypt${_N}${_R}${_P}${sal.hex()}${_hash(senha, sal).hex()}"


def _confere(senha: str, guardado: str) -> bool:
    _, n, r, p, sal_hex, hash_hex = guardado.split("$")
    calculado = _hash(senha, bytes.fromhex(sal_hex), int(n), int(r), int(p))
    return hmac.compare_digest(calculado, bytes.fromhex(hash_hex))


def _validar_senha(senha: str) -> None:
    if len(senha) < TAMANHO_MINIMO_SENHA:
        raise ValueError(f"A senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.")


def criar_usuario(conn: sqlite3.Connection, usuario: str, senha: str) -> str:
    nome = _normalizar(usuario)
    if not nome:
        raise ValueError("O nome de usuário não pode ser vazio.")
    _validar_senha(senha)
    try:
        with conn:
            conn.execute(
                "INSERT INTO usuario_painel (usuario, senha_hash, criado_em) VALUES (?, ?, ?)",
                (nome, _gerar_hash(senha), datetime.now().isoformat()),
            )
    except sqlite3.IntegrityError as erro:
        raise ValueError(f"O usuário '{nome}' já existe.") from erro
    return nome


def redefinir_senha(conn: sqlite3.Connection, usuario: str, senha: str) -> None:
    _validar_senha(senha)
    with conn:
        cursor = conn.execute(
            "UPDATE usuario_painel SET senha_hash = ? WHERE usuario = ?", (_gerar_hash(senha), _normalizar(usuario))
        )
    if cursor.rowcount == 0:
        raise ValueError(f"O usuário '{_normalizar(usuario)}' não existe.")


def remover_usuario(conn: sqlite3.Connection, usuario: str) -> bool:
    with conn:
        cursor = conn.execute("DELETE FROM usuario_painel WHERE usuario = ?", (_normalizar(usuario),))
    return cursor.rowcount == 1


def listar_usuarios(conn: sqlite3.Connection) -> list[str]:
    return [linha[0] for linha in conn.execute("SELECT usuario FROM usuario_painel ORDER BY usuario")]


def existe_algum_usuario(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM usuario_painel LIMIT 1").fetchone() is not None


def verificar_credenciais(conn: sqlite3.Connection, usuario: str, senha: str) -> str | None:
    """Devolve o usuário (normalizado) se a senha confere; senão None."""
    nome = _normalizar(usuario)
    linha = conn.execute("SELECT senha_hash FROM usuario_painel WHERE usuario = ?", (nome,)).fetchone()
    if linha is None:
        # Calcula um hash mesmo assim: o tempo de resposta não revela se o usuário existe.
        _confere(senha, _HASH_FICTICIO)
        return None
    return nome if _confere(senha, linha[0]) else None


_HASH_FICTICIO = _gerar_hash(secrets.token_hex(16))
