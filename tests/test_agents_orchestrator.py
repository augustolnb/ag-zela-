from zela.agents.orchestrator import (
    montar_agente_comunicacao,
    montar_agente_emergencia,
    montar_agente_monitoramento,
    montar_agente_rotina,
    montar_orquestrador,
)


def test_cada_agente_especializado_tem_nome_esperado():
    assert montar_agente_rotina().name == "agente_rotina"
    assert montar_agente_monitoramento().name == "agente_monitoramento"
    assert montar_agente_comunicacao().name == "agente_comunicacao"
    assert montar_agente_emergencia().name == "agente_emergencia"


def test_orquestrador_tem_os_quatro_subagentes_e_nome_proprio():
    orquestrador = montar_orquestrador()
    assert len(orquestrador.sub_agents) == 4
    nomes_subagentes = {sub_agente.name for sub_agente in orquestrador.sub_agents}
    assert nomes_subagentes == {
        "agente_rotina",
        "agente_monitoramento",
        "agente_comunicacao",
        "agente_emergencia",
    }
    assert orquestrador.name == "orquestrador_zela"
