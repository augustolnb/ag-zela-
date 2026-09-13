from datetime import datetime, timedelta

from zela.domain.emergencia import EstadoEscalonamento, EstagioEscalonamento, decidir_proxima_acao
from zela.models.monitoramento import EventoMonitoramento, MetodoClassificacao, StatusMonitoramento
from zela.models.perfil import ContatoFamiliar, PerfilIdoso


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        data_nascimento=datetime(1945, 3, 12).date(),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def _evento(status):
    return EventoMonitoramento(
        status=status,
        motivo="Sem movimentação detectada há 8.0h",
        timestamp=datetime(2026, 9, 13, 14, 0),
        metodo_classificacao=MetodoClassificacao.REGRA,
    )


def test_evento_normal_resolve_e_nao_gera_alerta():
    estado = EstadoEscalonamento()
    novo_estado, alertas = decidir_proxima_acao(
        _evento(StatusMonitoramento.NORMAL), _perfil(), estado, datetime(2026, 9, 13, 14, 0)
    )
    assert novo_estado.estagio == EstagioEscalonamento.RESOLVIDO
    assert alertas == []


def test_primeiro_evento_de_risco_contata_idoso():
    estado = EstadoEscalonamento()
    agora = datetime(2026, 9, 13, 14, 0)
    novo_estado, alertas = decidir_proxima_acao(_evento(StatusMonitoramento.RISCO), _perfil(), estado, agora)
    assert novo_estado.estagio == EstagioEscalonamento.CONTATO_IDOSO
    assert len(alertas) == 1
    assert alertas[0].destinatario == "Maria da Silva"


def test_sem_resposta_apos_janela_notifica_familia():
    inicio = datetime(2026, 9, 13, 14, 0)
    estado = EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=inicio)
    agora = inicio + timedelta(minutes=11)
    novo_estado, alertas = decidir_proxima_acao(_evento(StatusMonitoramento.RISCO), _perfil(), estado, agora)
    assert novo_estado.estagio == EstagioEscalonamento.NOTIFICAR_FAMILIA
    assert len(alertas) == 1
    assert alertas[0].destinatario == "João"


def test_ainda_dentro_da_janela_de_contato_idoso_nao_escalona():
    inicio = datetime(2026, 9, 13, 14, 0)
    estado = EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=inicio)
    agora = inicio + timedelta(minutes=5)
    novo_estado, alertas = decidir_proxima_acao(_evento(StatusMonitoramento.RISCO), _perfil(), estado, agora)
    assert novo_estado.estagio == EstagioEscalonamento.CONTATO_IDOSO
    assert alertas == []


def test_sem_resposta_da_familia_apos_janela_simula_emergencia():
    inicio = datetime(2026, 9, 13, 14, 0)
    estado = EstadoEscalonamento(estagio=EstagioEscalonamento.NOTIFICAR_FAMILIA, iniciado_em=inicio)
    agora = inicio + timedelta(minutes=16)
    novo_estado, alertas = decidir_proxima_acao(_evento(StatusMonitoramento.RISCO), _perfil(), estado, agora)
    assert novo_estado.estagio == EstagioEscalonamento.SIMULAR_EMERGENCIA
    assert len(alertas) == 1
    assert "SIMULAÇÃO" in alertas[0].mensagem
    assert alertas[0].destinatario == "servico_emergencia_simulado"


def test_evento_de_risco_apos_resolvido_reinicia_contato_idoso():
    estado = EstadoEscalonamento(estagio=EstagioEscalonamento.RESOLVIDO)
    agora = datetime(2026, 9, 13, 14, 0)
    novo_estado, alertas = decidir_proxima_acao(_evento(StatusMonitoramento.RISCO), _perfil(), estado, agora)
    assert novo_estado.estagio == EstagioEscalonamento.CONTATO_IDOSO
    assert len(alertas) == 1
    assert alertas[0].destinatario == "Maria da Silva"
