# Zela+ — Agente de IA de Apoio ao Idoso que Mora Sozinho

Trabalho final de pós-graduação em Agentes de IA. Zela+ é um agente
multiagente (ADK) que ajuda idosos que moram sozinhos a não esquecer
medicamentos e compromissos, monitora sinais de risco (saúde e
presença/movimento) via smartwatch e ESP32, e mantém a família informada,
podendo escalar alertas até simular contato com serviço de emergência.

## Status do projeto

Este repositório está sendo construído em fases (planos sequenciais):

1. **Fundação** (este plano) — modelos Pydantic + lógica de domínio dos 5
   agentes + esqueleto de orquestração ADK. Tudo testável com `pytest`,
   sem hardware nem APIs externas.
2. Comunicação real (WhatsApp/Twilio + áudio) — em andamento.
3. Ingestão de sensores reais (ESP32 + Health Connect/Mi Band 9).
4. Embeddings (classificação de urgência + RAG).
5. Painel Streamlit para a família.
6. Fluxo visual em n8n (substitui Langflow, citado no enunciado original
   do curso — o curso migrou de ferramenta).
7. Empacotamento final, documentação e vídeo pitch.

O design completo está em
`docs/superpowers/specs/2026-09-10-cuida-mais-agente-idoso-design.md`.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Rodando os testes

```bash
pytest -v
```

## Estrutura do código

- `zela/models/` — contratos de dados Pydantic (validação de entrada).
- `zela/domain/` — regras de negócio de cada agente, puras e testáveis
  sem dependências externas.
- `zela/agents/` — definição dos agentes ADK (orquestrador + 4
  especializados).
- `zela/simulacao.py` — simulação de um "dia" completo do sistema, sem
  hardware nem APIs externas, usada para validar a lógica de domínio de
  ponta a ponta.
