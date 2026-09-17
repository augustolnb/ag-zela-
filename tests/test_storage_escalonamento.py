from datetime import datetime

from zela.domain.emergencia import EstadoEscalonamento, EstagioEscalonamento
from zela.models.monitoramento import EventoMonitoramento, MetodoClassificacao, StatusMonitoramento
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.storage.db import conectar
from zela.storage.escalonamento import aplicar_escalonamento, obter_estado, salvar_estado


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511900000000",
        data_nascimento=datetime(1945, 3, 12).date(),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def test_obter_estado_sem_registro_retorna_ocioso():
    conn = conectar(":memory:")

    estado = obter_estado(conn, "idosa-1")

    assert estado.estagio == EstagioEscalonamento.OCIOSO
    assert estado.iniciado_em is None


def test_salvar_e_obter_estado():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)

    salvar_estado(
        conn, "idosa-1",
        EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=agora),
    )
    estado = obter_estado(conn, "idosa-1")

    assert estado.estagio == EstagioEscalonamento.CONTATO_IDOSO
    assert estado.iniciado_em == agora


def test_salvar_estado_atualiza_registro_existente():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)
    salvar_estado(conn, "idosa-1", EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=agora))

    salvar_estado(conn, "idosa-1", EstadoEscalonamento(estagio=EstagioEscalonamento.RESOLVIDO))

    estado = obter_estado(conn, "idosa-1")
    assert estado.estagio == EstagioEscalonamento.RESOLVIDO
    assert estado.iniciado_em is None


def test_aplicar_escalonamento_persiste_novo_estado_e_retorna_alertas():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)
    evento = EventoMonitoramento(
        status=StatusMonitoramento.RISCO,
        motivo="Sem movimentação detectada há 8.0h",
        timestamp=agora,
        metodo_classificacao=MetodoClassificacao.REGRA,
    )

    alertas = aplicar_escalonamento(conn, "idosa-1", evento, _perfil(), agora)

    assert len(alertas) == 1
    assert alertas[0].destinatario == "Maria da Silva"
    estado_persistido = obter_estado(conn, "idosa-1")
    assert estado_persistido.estagio == EstagioEscalonamento.CONTATO_IDOSO
    assert estado_persistido.iniciado_em == agora
