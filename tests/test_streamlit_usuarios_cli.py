from zela.storage.db import conectar
from zela.storage.usuarios import listar_usuarios, verificar_credenciais
from zela.streamlit_app.usuarios import main


def _perguntas(*respostas):
    fila = list(respostas)
    return lambda _rotulo: fila.pop(0)


def test_criar_pede_a_senha_duas_vezes(tmp_path, monkeypatch, capsys):
    caminho = str(tmp_path / "t.db")
    monkeypatch.setenv("ZELA_DB_PATH", caminho)

    codigo = main(["criar", "Ana"], perguntar=_perguntas("senha-forte-1", "senha-forte-1"))

    assert codigo == 0
    assert verificar_credenciais(conectar(caminho), "ana", "senha-forte-1") == "ana"
    assert "senha-forte-1" not in capsys.readouterr().out


def test_criar_recusa_senhas_diferentes_ou_curtas(tmp_path, monkeypatch, capsys):
    caminho = str(tmp_path / "t.db")
    monkeypatch.setenv("ZELA_DB_PATH", caminho)

    assert main(["criar", "ana"], perguntar=_perguntas("senha-forte-1", "outra-senha-1")) == 1
    assert main(["criar", "ana"], perguntar=_perguntas("curta", "curta")) == 1
    assert listar_usuarios(conectar(caminho)) == []
    assert "não conferem" in capsys.readouterr().err


def test_listar_senha_e_remover(tmp_path, monkeypatch, capsys):
    caminho = str(tmp_path / "t.db")
    monkeypatch.setenv("ZELA_DB_PATH", caminho)
    main(["criar", "ana"], perguntar=_perguntas("senha-forte-1", "senha-forte-1"))

    assert main(["listar"]) == 0
    assert "ana" in capsys.readouterr().out

    assert main(["senha", "ana"], perguntar=_perguntas("senha-nova-12", "senha-nova-12")) == 0
    assert verificar_credenciais(conectar(caminho), "ana", "senha-nova-12") == "ana"

    assert main(["remover", "ana"]) == 0
    assert main(["remover", "ana"]) == 1
    assert listar_usuarios(conectar(caminho)) == []


def test_sem_argumentos_mostra_o_uso(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ZELA_DB_PATH", str(tmp_path / "t.db"))
    assert main([]) == 2
    assert "criar" in capsys.readouterr().err
