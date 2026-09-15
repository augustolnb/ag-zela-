from datetime import time

from zela.agents.orchestrator import (
    confirmar_medicamento,
    montar_agente_rotina,
    verificar_lembretes_pendentes,
)
from zela.models.rotina import Dosagem, Medicamento
from zela.storage.db import conectar
from zela.storage.rotina import salvar_medicamento


def test_agente_rotina_tem_duas_ferramentas(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    agente = montar_agente_rotina()

    assert len(agente.tools) == 2


def test_verificar_lembretes_pendentes_le_do_banco(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    conn = conectar(banco)
    medicamento = Medicamento(
        id="med-1", nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
    )
    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")

    pendentes = verificar_lembretes_pendentes("idosa-1", "2026-09-14T08:05:00")

    assert len(pendentes) == 1
    assert pendentes[0]["id"] == "med-1"


def test_confirmar_medicamento_grava_no_banco_e_remove_de_pendentes(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    conn = conectar(banco)
    medicamento = Medicamento(
        id="med-1", nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
    )
    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")

    resultado = confirmar_medicamento("idosa-1", "med-1", "2026-09-14T08:05:00", "2026-09-14T08:05:00")
    assert resultado["status"] == "confirmado"

    pendentes_depois = verificar_lembretes_pendentes("idosa-1", "2026-09-14T08:05:00")
    assert pendentes_depois == []


def test_confirmar_medicamento_inexistente_retorna_erro(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)
    conectar(banco)

    resultado = confirmar_medicamento("idosa-1", "nao-existe", "2026-09-14T08:05:00", "2026-09-14T08:05:00")

    assert "erro" in resultado


def test_verificar_lembretes_pendentes_com_agora_iso_invalido_retorna_erro_estruturado(
    monkeypatch, tmp_path
):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)
    conectar(banco)

    resultado = verificar_lembretes_pendentes("idosa-1", "não-é-uma-data")

    assert isinstance(resultado, list)
    assert "erro" in resultado[0]


def test_confirmar_medicamento_com_data_invalida_retorna_erro_estruturado(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)
    conectar(banco)

    resultado = confirmar_medicamento("idosa-1", "med-1", "não-é-uma-data", "2026-09-14T08:05:00")

    assert "erro" in resultado
