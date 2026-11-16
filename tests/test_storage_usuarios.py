import pytest

from zela.storage.db import conectar
from zela.storage.usuarios import (
    criar_usuario,
    existe_algum_usuario,
    listar_usuarios,
    redefinir_senha,
    remover_usuario,
    verificar_credenciais,
)


def _conn(tmp_path):
    return conectar(str(tmp_path / "u.db"))


def test_cria_e_verifica_credenciais(tmp_path):
    conn = _conn(tmp_path)
    assert existe_algum_usuario(conn) is False

    criar_usuario(conn, "Augusto", "senha-forte-1")

    assert existe_algum_usuario(conn) is True
    assert verificar_credenciais(conn, "augusto", "senha-forte-1") == "augusto"
    assert verificar_credenciais(conn, "  AUGUSTO ", "senha-forte-1") == "augusto"
    assert verificar_credenciais(conn, "augusto", "senha-errada") is None
    assert verificar_credenciais(conn, "outro", "senha-forte-1") is None


def test_senha_guardada_com_hash_e_sal(tmp_path):
    conn = _conn(tmp_path)
    criar_usuario(conn, "ana", "mesma-senha-123")
    criar_usuario(conn, "bia", "mesma-senha-123")

    hashes = [linha[0] for linha in conn.execute("SELECT senha_hash FROM usuario_painel ORDER BY usuario")]

    assert all("mesma-senha-123" not in h for h in hashes)
    assert all(h.startswith("scrypt$") for h in hashes)
    assert hashes[0] != hashes[1]


def test_usuario_repetido_ou_dados_invalidos_sao_recusados(tmp_path):
    conn = _conn(tmp_path)
    criar_usuario(conn, "ana", "senha-forte-1")

    with pytest.raises(ValueError):
        criar_usuario(conn, "ANA", "outra-senha-1")
    with pytest.raises(ValueError):
        criar_usuario(conn, "   ", "senha-forte-1")
    with pytest.raises(ValueError):
        criar_usuario(conn, "carla", "curta")


def test_redefinir_senha_e_remover(tmp_path):
    conn = _conn(tmp_path)
    criar_usuario(conn, "ana", "senha-antiga-1")

    redefinir_senha(conn, "ana", "senha-nova-12")
    assert verificar_credenciais(conn, "ana", "senha-antiga-1") is None
    assert verificar_credenciais(conn, "ana", "senha-nova-12") == "ana"
    with pytest.raises(ValueError):
        redefinir_senha(conn, "ninguem", "senha-nova-12")

    criar_usuario(conn, "bia", "senha-forte-1")
    assert listar_usuarios(conn) == ["ana", "bia"]
    assert remover_usuario(conn, "ana") is True
    assert remover_usuario(conn, "ana") is False
    assert listar_usuarios(conn) == ["bia"]
