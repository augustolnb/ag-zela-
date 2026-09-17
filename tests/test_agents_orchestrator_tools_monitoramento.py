from datetime import datetime, timedelta

from zela.agents.orchestrator import (
    consultar_historico_alertas,
    consultar_status_atual,
    montar_agente_emergencia,
    montar_agente_monitoramento,
)
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.models.monitoramento import FonteSensor, LeituraSensor, StatusMonitoramento, TipoLeitura
from zela.storage.alertas import salvar_alerta
from zela.storage.db import conectar
from zela.storage.monitoramento import salvar_leitura


def test_agente_monitoramento_tem_uma_ferramenta(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    agente = montar_agente_monitoramento()

    assert len(agente.tools) == 1


def test_consultar_status_atual_reflete_leituras_reais(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    conn = conectar(banco)
    agora = datetime(2026, 9, 16, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora - timedelta(hours=8),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    resultado = consultar_status_atual("idosa-1", agora.isoformat())

    assert resultado["status"] == StatusMonitoramento.RISCO.value


def test_consultar_status_atual_com_data_invalida_retorna_erro(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    resultado = consultar_status_atual("idosa-1", "nao-e-uma-data")

    assert "erro" in resultado


def test_agente_emergencia_tem_uma_ferramenta(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    agente = montar_agente_emergencia()

    assert len(agente.tools) == 1


def test_consultar_historico_alertas_retorna_alertas_persistidos(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    conn = conectar(banco)
    alerta = Alerta(
        nivel=NivelAlerta.CRITICO, destinatario="João", canal=CanalAlerta.WHATSAPP,
        mensagem="Sem resposta.", timestamp=datetime(2026, 9, 16, 14, 0),
    )
    salvar_alerta(conn, alerta, idoso_id="idosa-1")

    resultado = consultar_historico_alertas("idosa-1")

    assert len(resultado) == 1
    assert resultado[0]["destinatario"] == "João"


def test_consultar_historico_alertas_sem_alertas_retorna_lista_vazia(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    resultado = consultar_historico_alertas("idosa-1")

    assert resultado == []
