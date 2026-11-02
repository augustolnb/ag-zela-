import importlib
import tomllib
from pathlib import Path

import pytest

from google.adk.models.lite_llm import LiteLlm

from zela.agents.orchestrator import (
    MODELO_DEEPSEEK,
    MODELO_GEMINI,
    _montar_modelo_padrao,
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


def test_modelo_padrao_e_gemini_quando_variavel_ausente(monkeypatch):
    monkeypatch.delenv("ZELA_LLM_PROVEDOR", raising=False)
    assert _montar_modelo_padrao() == MODELO_GEMINI


def test_modelo_padrao_e_gemini_quando_variavel_explicitamente_gemini(monkeypatch):
    monkeypatch.setenv("ZELA_LLM_PROVEDOR", "gemini")
    assert _montar_modelo_padrao() == MODELO_GEMINI


def test_modelo_padrao_usa_deepseek_via_litellm_quando_configurado(monkeypatch):
    monkeypatch.setenv("ZELA_LLM_PROVEDOR", "deepseek")
    modelo = _montar_modelo_padrao()
    assert isinstance(modelo, LiteLlm)
    assert modelo.model == MODELO_DEEPSEEK


def test_modelo_padrao_aceita_deepseek_com_caixa_variada(monkeypatch):
    monkeypatch.setenv("ZELA_LLM_PROVEDOR", "DeepSeek")
    modelo = _montar_modelo_padrao()
    assert isinstance(modelo, LiteLlm)
    assert modelo.model == MODELO_DEEPSEEK


def test_provedor_deepseek_carrega_com_as_dependencias_do_extra():
    # Regressão: um litellm novo passou a importar `mcp`, ausente da imagem, e
    # toda resposta do bot falhou. Os demais testes simulam o LLM e não pegam isso.
    pytest.importorskip("litellm")
    importlib.import_module("litellm.proxy._experimental.mcp_server.catalog")
    importlib.import_module("google.adk.models.lite_llm")


def test_dependencias_do_llm_estao_fixadas():
    dependencias = tomllib.loads(Path("pyproject.toml").read_text())["project"]
    extra = dependencias["optional-dependencies"]["deepseek"]
    assert any(d.startswith("google-adk==") for d in dependencias["dependencies"])
    assert any(d.startswith("litellm==") for d in extra)
    assert any(d.startswith("mcp==") for d in extra)
