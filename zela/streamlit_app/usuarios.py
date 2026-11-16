"""Gerencia os usuários do painel pelo terminal.

Uso (no servidor, dentro do container do painel):
    python -m zela.streamlit_app.usuarios criar <usuário>
    python -m zela.streamlit_app.usuarios senha <usuário>     # redefine a senha
    python -m zela.streamlit_app.usuarios remover <usuário>
    python -m zela.streamlit_app.usuarios listar

A senha é pedida sem aparecer na tela e nunca vai para a linha de comando
(que fica no histórico do shell).
"""

import getpass
import os
import sys
from collections.abc import Callable

from zela.storage.db import conectar
from zela.storage.usuarios import criar_usuario, listar_usuarios, redefinir_senha, remover_usuario

_USO = "Uso: python -m zela.streamlit_app.usuarios {criar|senha|remover} <usuário> | listar"


def _ler_senha(perguntar: Callable[[str], str]) -> str | None:
    senha = perguntar("Senha: ")
    if senha != perguntar("Repita a senha: "):
        print("As senhas não conferem.", file=sys.stderr)
        return None
    return senha


def main(argv: list[str], perguntar: Callable[[str], str] = getpass.getpass) -> int:
    if not argv or argv[0] not in ("criar", "senha", "remover", "listar") or (argv[0] != "listar" and len(argv) != 2):
        print(_USO, file=sys.stderr)
        return 2
    conn = conectar(os.environ.get("ZELA_DB_PATH", "zela.db"))
    comando = argv[0]

    if comando == "listar":
        for usuario in listar_usuarios(conn):
            print(usuario)
        return 0

    usuario = argv[1]
    if comando == "remover":
        if remover_usuario(conn, usuario):
            print(f"Usuário '{usuario.strip().lower()}' removido.")
            return 0
        print(f"O usuário '{usuario.strip().lower()}' não existe.", file=sys.stderr)
        return 1

    senha = _ler_senha(perguntar)
    if senha is None:
        return 1
    try:
        if comando == "criar":
            nome = criar_usuario(conn, usuario, senha)
            print(f"Usuário '{nome}' criado.")
        else:
            redefinir_senha(conn, usuario, senha)
            print(f"Senha de '{usuario.strip().lower()}' redefinida.")
    except ValueError as erro:
        print(str(erro), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
