import pytest
from datetime import date
from pydantic import ValidationError

from zela.models.perfil import ContatoFamiliar, PerfilIdoso


def test_perfil_idoso_valido():
    perfil = PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )
    assert perfil.nome == "Maria da Silva"
    assert perfil.telefone == "+5511911111111"
    assert perfil.contatos_familiares[0].telefone == "+5511987654321"


def test_perfil_idoso_exige_ao_menos_um_contato_familiar():
    with pytest.raises(ValidationError):
        PerfilIdoso(
            nome="Maria da Silva",
            telefone="+5511911111111",
            data_nascimento=date(1945, 3, 12),
            contatos_familiares=[],
        )


def test_perfil_idoso_rejeita_telefone_fora_do_padrao_e164():
    with pytest.raises(ValidationError):
        PerfilIdoso(
            nome="Maria da Silva",
            telefone="011911111111",
            data_nascimento=date(1945, 3, 12),
            contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
        )


def test_contato_familiar_rejeita_telefone_fora_do_padrao_e164():
    with pytest.raises(ValidationError):
        ContatoFamiliar(nome="João", telefone="011987654321")


def test_perfil_idoso_condicoes_medicas_e_opcional_e_vazia_por_padrao():
    perfil = PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )
    assert perfil.condicoes_medicas == []
