from datetime import date

from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.storage.db import conectar
from zela.storage.perfil import obter_perfil, salvar_perfil


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def test_salvar_e_obter_perfil():
    conn = conectar(":memory:")
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")

    recuperado = obter_perfil(conn, "idosa-1")

    assert recuperado is not None
    assert recuperado.nome == "Maria da Silva"
    assert recuperado.telefone == "+5511911111111"
    assert recuperado.contatos_familiares[0].telefone == "+5511987654321"


def test_obter_perfil_inexistente_retorna_none():
    conn = conectar(":memory:")
    assert obter_perfil(conn, "nao-existe") is None


def test_salvar_perfil_atualiza_registro_existente():
    conn = conectar(":memory:")
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")

    perfil_atualizado = _perfil().model_copy(update={"nome": "Maria S. Silva"})
    salvar_perfil(conn, perfil_atualizado, idoso_id="idosa-1")

    recuperado = obter_perfil(conn, "idosa-1")
    assert recuperado.nome == "Maria S. Silva"


def test_perfil_sem_lid_whatsapp_recupera_como_none():
    conn = conectar(":memory:")
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")

    recuperado = obter_perfil(conn, "idosa-1")
    assert recuperado.lid_whatsapp is None


def test_salvar_e_obter_perfil_com_lid_whatsapp():
    conn = conectar(":memory:")
    perfil_com_lid = _perfil().model_copy(update={"lid_whatsapp": "109281332445239@lid"})
    salvar_perfil(conn, perfil_com_lid, idoso_id="idosa-1")

    recuperado = obter_perfil(conn, "idosa-1")
    assert recuperado.lid_whatsapp == "109281332445239@lid"
