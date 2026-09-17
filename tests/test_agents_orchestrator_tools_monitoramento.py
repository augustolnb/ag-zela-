from datetime import datetime, timedelta

from zela.agents.orchestrator import (
    consultar_historico_alertas,
    consultar_status_atual,
    montar_agente_emergencia,
    montar_agente_monitoramento,
)
from zela.domain.emergencia import EstadoEscalonamento, EstagioEscalonamento
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.models.monitoramento import FonteSensor, LeituraSensor, StatusMonitoramento, TipoLeitura
from zela.storage.alertas import salvar_alerta
from zela.storage.db import conectar
from zela.storage.escalonamento import obter_estado, salvar_estado
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

    # `consultar_status_atual` ignora deliberadamente o valor de `agora_iso`
    # fornecido pelo LLM para a classificação em si (só o valida) e usa
    # `datetime.now()` de verdade — por isso fixamos `datetime.now()` aqui em
    # vez de confiar no argumento passado à função.
    class _DatetimeFixo:
        @staticmethod
        def now():
            return agora

        @staticmethod
        def fromisoformat(valor):
            return datetime.fromisoformat(valor)

    monkeypatch.setattr("zela.agents.orchestrator.datetime", _DatetimeFixo)

    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora - timedelta(hours=8),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    resultado = consultar_status_atual("idosa-1", agora.isoformat())

    assert resultado["status"] == StatusMonitoramento.RISCO.value


def test_consultar_status_atual_ignora_agora_iso_do_llm_para_classificacao(monkeypatch, tmp_path):
    # Mesmo que o LLM informe um `agora_iso` sob o qual a leitura pareceria
    # NORMAL (poucas horas de diferença), a classificação real deve usar
    # `datetime.now()` — aqui fixado para o instante em que a leitura já
    # indicaria RISCO (mais de 6h sem presença).
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    conn = conectar(banco)
    agora_real = datetime(2026, 9, 16, 14, 0)
    ultima_presenca = agora_real - timedelta(hours=8)

    class _DatetimeFixo:
        @staticmethod
        def now():
            return agora_real

        @staticmethod
        def fromisoformat(valor):
            return datetime.fromisoformat(valor)

    monkeypatch.setattr("zela.agents.orchestrator.datetime", _DatetimeFixo)

    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=ultima_presenca,
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    # `agora_iso` "mentiroso": só 1h depois da última presença -> pareceria
    # NORMAL se fosse de fato usado para a classificação.
    agora_iso_hallucinado = (ultima_presenca + timedelta(hours=1)).isoformat()

    resultado = consultar_status_atual("idosa-1", agora_iso_hallucinado)

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


def test_ferramentas_de_consulta_nao_alteram_estado_de_escalonamento(monkeypatch, tmp_path):
    # Propriedade central de segurança do plano: as ferramentas de consulta
    # do LLM (status atual, histórico de alertas) são somente-leitura e
    # NUNCA podem avançar/alterar a escada de escalonamento, que só pode ser
    # decidida pelo processo determinístico do scheduler.
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    conn = conectar(banco)
    estado_semeado = EstadoEscalonamento(
        estagio=EstagioEscalonamento.CONTATO_IDOSO,
        iniciado_em=datetime(2026, 9, 16, 13, 50),
    )
    salvar_estado(conn, "idosa-1", estado_semeado)

    agora = datetime(2026, 9, 16, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora - timedelta(hours=8),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")
    salvar_alerta(
        conn,
        Alerta(
            nivel=NivelAlerta.CRITICO, destinatario="João", canal=CanalAlerta.WHATSAPP,
            mensagem="Sem resposta.", timestamp=agora,
        ),
        idoso_id="idosa-1",
    )

    consultar_status_atual("idosa-1", agora.isoformat())
    consultar_historico_alertas("idosa-1")

    estado_depois = obter_estado(conn, "idosa-1")
    assert estado_depois == estado_semeado
