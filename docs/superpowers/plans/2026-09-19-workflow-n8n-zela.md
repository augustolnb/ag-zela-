# Zela+ — Workflow n8n (Plano 6 de 7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar os itens 3.4/3.8 do card (workflow visual + comunicação) via um workflow n8n real, importável, que representa a fatia "mensagem recebida → classificação de urgência → roteamento" do sistema — sem reescrever a integração real WAHA→FastAPI já funcionando desde o Plano 2.

**Architecture:** Um novo endpoint `POST /api/classificar-mensagem` (FastAPI) expõe **somente** a classificação por similaridade do Plano 4 (nunca decide escalonamento). O workflow n8n (`docs/n8n/zela-classificacao-mensagem.json`) tem seu próprio webhook de entrada, chama esse endpoint via HTTP Request, e roteia a resposta em 3 ramos (risco/atenção/normal) usando 2 nós "If" encadeados. Todo o schema JSON do workflow foi verificado contra o código-fonte do n8n antes de ser escrito neste plano — nenhum node type, `typeVersion` ou nome de parâmetro é assumido sem confirmação.

**Tech Stack:** FastAPI (já usado no projeto), `zela/embeddings/*` (Plano 4, sem mudança). n8n é externo ao repositório Python — o plano produz um arquivo `.json` de workflow e documentação, não código n8n.

**Spec:** `docs/superpowers/specs/2026-09-10-cuida-mais-agente-idoso-design.md` (seção 5 e, em detalhe, a nova seção 17).

## Global Constraints

- Python 3.11+, mesmas convenções dos Planos 1-5.
- **A camada `zela/domain/` não muda neste plano** — continua pura, sem I/O.
- **O endpoint novo NUNCA chama `aplicar_escalonamento`** — preserva a propriedade central de segurança do projeto (nem o n8n, nem este endpoint, decidem escalonamento de verdade; só classificam e relatam).
- **O webhook do n8n é independente da integração real WAHA→FastAPI** (Plano 2) — não reconfigura o WAHA, não compartilha número/sessão. É um endpoint de teste separado, disparado manualmente (curl ou a ferramenta de teste do próprio n8n).
- **Nenhum node type, `typeVersion` ou nome de parâmetro do n8n é usado sem verificação prévia.** Os valores usados neste plano (documentados abaixo, task a task) foram verificados durante o brainstorming contra exemplos reais e contra o código-fonte do n8n (`n8n-io/n8n` no GitHub):
  - Webhook: `n8n-nodes-base.webhook`, `typeVersion: 1.1`, parâmetros `httpMethod`/`path`/`responseMode`/`options`. **O corpo da requisição POST fica em `$json.body.*`, não em `$json.*` direto** — confirmado no código-fonte do nó (`Webhook/utils.ts`), não é uma suposição.
  - HTTP Request: `n8n-nodes-base.httpRequest`, `typeVersion: 4.2` (mapeia para a implementação `HttpRequestV3`, que cobre 3/4/4.1/4.2/4.3/4.4/4.5). Para enviar um corpo JSON dinâmico: `sendBody: true`, `contentType: "application/json"`, `specifyBody: "json"`, `jsonBody` como uma expressão que retorna um objeto JS (`={{ {...} }}`) — não uma string com interpolação manual, para evitar bugs de escape.
  - If: `n8n-nodes-base.if`, `typeVersion: 2` (typeVersions 2.0-2.3 usam a mesma implementação `IfV2`). Parâmetros: `conditions.combinator`, `conditions.conditions[].{leftValue, rightValue, operator: {type, operation}}`.
  - Respond to Webhook: `n8n-nodes-base.respondToWebhook`, `typeVersion: 1.1`. Para responder com um corpo JSON customizado: `respondWith: "json"`, `responseBody` como uma expressão que retorna um objeto JS.
- **Sem teste automatizado para a execução do workflow n8n em si** (mesmo tratamento dado ao WAHA e ao firmware do ESP32) — verificação manual, documentada no README. O `.json` do workflow tem, porém, um teste estrutural (`tests/test_n8n_workflow.py`) que garante que o arquivo continua parseável e com os node types/conexões esperados, para pegar erros de edição futura.
- Nome do projeto: **Zela+**. Escopo de idoso único (`id_idoso = "idosa-1"`), mesma convenção dos planos anteriores — mas este endpoint não recebe `idoso_id` (só classifica texto, sem ligar a um idoso específico).

---

## Mapa de arquivos deste plano

```
zela/
  api/
    classificacao.py       # NOVO: POST /api/classificar-mensagem
    main.py                 # MODIFICADO: registra o roteador novo
docs/
  n8n/
    zela-classificacao-mensagem.json  # NOVO: workflow importável
tests/
  test_api_classificacao.py  # NOVO
  test_api_main.py            # MODIFICADO: nova rota registrada
  test_n8n_workflow.py         # NOVO: sanity check estrutural do .json
README.md                       # MODIFICADO: seção "Workflow n8n (Plano 6)"
```

---

### Task 1: Endpoint de classificação

**Files:**
- Create: `zela/api/classificacao.py`
- Create: `tests/test_api_classificacao.py`

**Interfaces:**
- Consumes: `zela.embeddings.classificador.classificar_por_similaridade` (Plano 4), `zela.embeddings.exemplos_referencia.ExemploReferencia` (Plano 4, apenas para tipagem/testes).
- Produces: `montar_roteador_classificacao(cliente_embedding, obter_exemplos_com_embedding) -> APIRouter` — monta a rota `POST /api/classificar-mensagem`, no mesmo padrão de injeção de dependência já usado por `montar_roteador_ingestao`/`montar_roteador`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_api_classificacao.py
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from zela.api.classificacao import montar_roteador_classificacao
from zela.embeddings.exemplos_referencia import ExemploReferencia
from zela.models.monitoramento import StatusMonitoramento


class _ClienteEmbeddingFalso:
    def __init__(self, vetor):
        self._vetor = vetor

    def obter_embedding(self, texto: str) -> list[float]:
        return self._vetor


class _ClienteEmbeddingComFalha:
    def obter_embedding(self, texto: str) -> list[float]:
        raise RuntimeError("Gemini fora do ar")


def _exemplos_com_embedding():
    exemplo_normal = ExemploReferencia(texto="Estou bem", status=StatusMonitoramento.NORMAL)
    exemplo_risco = ExemploReferencia(texto="Caí e não consigo levantar", status=StatusMonitoramento.RISCO)
    return [(exemplo_normal, [1.0, 0.0]), (exemplo_risco, [0.0, 1.0])]


def test_classificar_mensagem_retorna_status_e_motivo():
    app = FastAPI()
    app.include_router(
        montar_roteador_classificacao(_ClienteEmbeddingFalso([0.0, 1.0]), _exemplos_com_embedding)
    )
    cliente = TestClient(app)

    resposta = cliente.post("/api/classificar-mensagem", json={"texto": "caí no banheiro"})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "risco"
    assert "caí no banheiro" in corpo["motivo"]


def test_classificar_mensagem_corpo_invalido_retorna_400():
    app = FastAPI()
    app.include_router(
        montar_roteador_classificacao(_ClienteEmbeddingFalso([1.0, 0.0]), _exemplos_com_embedding)
    )
    cliente = TestClient(app)

    resposta = cliente.post("/api/classificar-mensagem", json={})

    assert resposta.status_code == 400


def test_classificar_mensagem_falha_de_embedding_retorna_503():
    app = FastAPI()
    app.include_router(
        montar_roteador_classificacao(_ClienteEmbeddingComFalha(), _exemplos_com_embedding)
    )
    cliente = TestClient(app)

    resposta = cliente.post("/api/classificar-mensagem", json={"texto": "oi"})

    assert resposta.status_code == 503
    assert "erro" in resposta.json()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `source .venv/bin/activate && pytest tests/test_api_classificacao.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.api.classificacao'`

- [ ] **Step 3: Implementar `classificacao.py`**

```python
# zela/api/classificacao.py
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from zela.embeddings.classificador import classificar_por_similaridade


def montar_roteador_classificacao(cliente_embedding, obter_exemplos_com_embedding) -> APIRouter:
    roteador = APIRouter()

    @roteador.post("/api/classificar-mensagem")
    async def classificar_mensagem(request: Request):
        try:
            corpo = await request.json()
            texto = corpo["texto"]
            if not isinstance(texto, str) or not texto:
                raise ValueError("campo 'texto' deve ser uma string não vazia")
        except (KeyError, TypeError, ValueError) as erro:
            return JSONResponse(status_code=400, content={"erro": f"corpo inválido: {erro}"})

        try:
            embedding = await run_in_threadpool(cliente_embedding.obter_embedding, texto)
            exemplos = await run_in_threadpool(obter_exemplos_com_embedding)
            evento = classificar_por_similaridade(embedding, exemplos, texto, datetime.now())
        except Exception as erro:
            return JSONResponse(status_code=503, content={"erro": f"falha ao classificar: {erro}"})

        return {"status": evento.status.value, "motivo": evento.motivo}

    return roteador
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_classificacao.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Rodar a suíte completa (checagem de regressão)**

Run: `pytest -q`
Expected: todos os testes continuam passando.

- [ ] **Step 6: Commit**

```bash
git add zela/api/classificacao.py tests/test_api_classificacao.py
git commit -m "feat: adiciona endpoint de classificacao de mensagem para o workflow n8n"
```

---

### Task 2: Wiring em `main.py`

**Files:**
- Modify: `zela/api/main.py`
- Modify: `tests/test_api_main.py`

**Interfaces:**
- Consumes: `montar_roteador_classificacao` (Task 1); `cliente_embedding` e `_obter_exemplos_com_embedding`, ambos já existentes em `zela/api/main.py` desde o Plano 4 (reaproveitados diretamente — nenhum novo objeto é criado).
- Produces: rota `POST /api/classificar-mensagem` registrada no app FastAPI principal.

- [ ] **Step 1: Escrever o teste que falha**

Adicione a `tests/test_api_main.py` (o arquivo já importa `TestClient`; use o padrão já existente de checar rotas registradas via `app.openapi()["paths"]`, visível em `test_app_inclui_rota_de_webhook`):

```python
def test_app_inclui_rota_de_classificacao():
    from zela.api.main import app

    caminhos = set(app.openapi()["paths"])
    assert "/api/classificar-mensagem" in caminhos
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `pytest tests/test_api_main.py -k classificacao -v`
Expected: FAIL — `/api/classificar-mensagem` não está em `caminhos`

- [ ] **Step 3: Atualizar `main.py`**

Adicione o import (junto aos outros imports de `zela.api.*`, em ordem alfabética):

```python
from zela.api.classificacao import montar_roteador_classificacao
```

E adicione a linha de registro do roteador, junto às outras chamadas `app.include_router(...)` já existentes (após a de `montar_roteador_ingestao`):

```python
app.include_router(montar_roteador_classificacao(cliente_embedding, _obter_exemplos_com_embedding))
```

Não altere mais nada em `main.py` — `cliente_embedding` e `_obter_exemplos_com_embedding` já existem no escopo do módulo desde o Plano 4.

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `pytest tests/test_api_main.py -v`
Expected: PASS — todos os testes, novos e pré-existentes.

- [ ] **Step 5: Rodar a suíte completa (checagem de regressão)**

Run: `pytest -q`
Expected: todos os testes continuam passando.

- [ ] **Step 6: Commit**

```bash
git add zela/api/main.py tests/test_api_main.py
git commit -m "feat: registra o endpoint de classificacao na API principal"
```

---

### Task 3: Workflow n8n (arquivo `.json`)

**Files:**
- Create: `docs/n8n/zela-classificacao-mensagem.json`
- Create: `tests/test_n8n_workflow.py`

**Interfaces:**
- Consumes: nenhuma interface Python — este arquivo é consumido pelo n8n (ferramenta externa), importado manualmente pelo usuário.
- Produces: um workflow n8n completo e importável, com 7 nós: `Webhook` → `HTTP Request` → `If: risco?` → (sim: `Responder: alertar familia` / não: `If: atencao?` → (sim: `Responder: verificar idosa` / não: `Responder: normal`)).

**Nota:** todo `type`/`typeVersion`/nome de parâmetro usado abaixo foi verificado durante o brainstorming contra o código-fonte do n8n — ver a seção "Global Constraints" deste plano para o resumo das fontes. Não altere esses valores sem verificar novamente.

- [ ] **Step 1: Escrever o teste estrutural que falha**

```python
# tests/test_n8n_workflow.py
import json
from pathlib import Path

CAMINHO_WORKFLOW = Path(__file__).parent.parent / "docs" / "n8n" / "zela-classificacao-mensagem.json"


def _carregar_workflow():
    with open(CAMINHO_WORKFLOW, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def test_workflow_e_json_valido_com_nos_esperados():
    workflow = _carregar_workflow()

    nomes_dos_nos = {no["name"] for no in workflow["nodes"]}
    assert nomes_dos_nos == {
        "Webhook",
        "HTTP Request",
        "If: risco?",
        "If: atencao?",
        "Responder: alertar familia",
        "Responder: verificar idosa",
        "Responder: normal",
    }


def test_workflow_usa_os_tipos_de_no_verificados():
    workflow = _carregar_workflow()
    tipos_por_nome = {no["name"]: (no["type"], no["typeVersion"]) for no in workflow["nodes"]}

    assert tipos_por_nome["Webhook"] == ("n8n-nodes-base.webhook", 1.1)
    assert tipos_por_nome["HTTP Request"] == ("n8n-nodes-base.httpRequest", 4.2)
    assert tipos_por_nome["If: risco?"] == ("n8n-nodes-base.if", 2)
    assert tipos_por_nome["If: atencao?"] == ("n8n-nodes-base.if", 2)
    for nome_resposta in ("Responder: alertar familia", "Responder: verificar idosa", "Responder: normal"):
        assert tipos_por_nome[nome_resposta] == ("n8n-nodes-base.respondToWebhook", 1.1)


def test_workflow_webhook_espera_post_e_responde_via_no_dedicado():
    workflow = _carregar_workflow()
    webhook = next(no for no in workflow["nodes"] if no["name"] == "Webhook")

    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["responseMode"] == "responseNode"


def test_workflow_conexoes_ligam_os_nos_na_ordem_esperada():
    workflow = _carregar_workflow()
    conexoes = workflow["connections"]

    def destino(nome_origem):
        return conexoes[nome_origem]["main"][0][0]["node"]

    assert destino("Webhook") == "HTTP Request"
    assert destino("HTTP Request") == "If: risco?"

    saidas_risco = conexoes["If: risco?"]["main"]
    assert saidas_risco[0][0]["node"] == "Responder: alertar familia"
    assert saidas_risco[1][0]["node"] == "If: atencao?"

    saidas_atencao = conexoes["If: atencao?"]["main"]
    assert saidas_atencao[0][0]["node"] == "Responder: verificar idosa"
    assert saidas_atencao[1][0]["node"] == "Responder: normal"
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_n8n_workflow.py -v`
Expected: FAIL — `FileNotFoundError` (o arquivo ainda não existe)

- [ ] **Step 3: Escrever `docs/n8n/zela-classificacao-mensagem.json`**

Crie o diretório `docs/n8n/` e o arquivo com exatamente este conteúdo (os `id` dos nós podem ser strings quaisquer únicas — usamos nomes descritivos abaixo por clareza; o n8n aceita isso):

```json
{
  "name": "Zela+ — Classificação de Mensagem (Plano 6)",
  "nodes": [
    {
      "id": "no-webhook",
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1.1,
      "position": [240, 300],
      "parameters": {
        "httpMethod": "POST",
        "path": "zela-classificar-mensagem",
        "responseMode": "responseNode",
        "options": {}
      }
    },
    {
      "id": "no-http-request",
      "name": "HTTP Request",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [460, 300],
      "parameters": {
        "method": "POST",
        "url": "http://localhost:8000/api/classificar-mensagem",
        "sendBody": true,
        "contentType": "application/json",
        "specifyBody": "json",
        "jsonBody": "={{ { texto: $json.body.texto } }}",
        "options": {}
      }
    },
    {
      "id": "no-if-risco",
      "name": "If: risco?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [680, 300],
      "parameters": {
        "conditions": {
          "combinator": "and",
          "conditions": [
            {
              "id": "cond-risco",
              "leftValue": "={{ $json.status }}",
              "rightValue": "risco",
              "operator": { "type": "string", "operation": "equals" }
            }
          ],
          "options": { "caseSensitive": true, "leftValue": "", "typeValidation": "strict" }
        }
      }
    },
    {
      "id": "no-if-atencao",
      "name": "If: atencao?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [680, 480],
      "parameters": {
        "conditions": {
          "combinator": "and",
          "conditions": [
            {
              "id": "cond-atencao",
              "leftValue": "={{ $json.status }}",
              "rightValue": "atencao",
              "operator": { "type": "string", "operation": "equals" }
            }
          ],
          "options": { "caseSensitive": true, "leftValue": "", "typeValidation": "strict" }
        }
      }
    },
    {
      "id": "no-resposta-risco",
      "name": "Responder: alertar familia",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1.1,
      "position": [900, 220],
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ { acao: \"alertar_familia\", mensagem_ilustrativa: \"Alertar a família: possível risco detectado, sem confirmação da idosa.\", status: $json.status, motivo: $json.motivo } }}"
      }
    },
    {
      "id": "no-resposta-atencao",
      "name": "Responder: verificar idosa",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1.1,
      "position": [900, 420],
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ { acao: \"verificar_idosa\", mensagem_ilustrativa: \"Perguntar à idosa se está tudo bem.\", status: $json.status, motivo: $json.motivo } }}"
      }
    },
    {
      "id": "no-resposta-normal",
      "name": "Responder: normal",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1.1,
      "position": [900, 600],
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ { acao: \"nenhuma\", mensagem_ilustrativa: \"Tudo normal, nenhuma ação necessária.\", status: $json.status, motivo: $json.motivo } }}"
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{ "node": "HTTP Request", "type": "main", "index": 0 }]]
    },
    "HTTP Request": {
      "main": [[{ "node": "If: risco?", "type": "main", "index": 0 }]]
    },
    "If: risco?": {
      "main": [
        [{ "node": "Responder: alertar familia", "type": "main", "index": 0 }],
        [{ "node": "If: atencao?", "type": "main", "index": 0 }]
      ]
    },
    "If: atencao?": {
      "main": [
        [{ "node": "Responder: verificar idosa", "type": "main", "index": 0 }],
        [{ "node": "Responder: normal", "type": "main", "index": 0 }]
      ]
    }
  },
  "active": false,
  "settings": { "executionOrder": "v1" },
  "pinData": {}
}
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_n8n_workflow.py -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Rodar a suíte completa (checagem de regressão)**

Run: `pytest -q`
Expected: todos os testes continuam passando.

- [ ] **Step 6: Commit**

```bash
git add docs/n8n/zela-classificacao-mensagem.json tests/test_n8n_workflow.py
git commit -m "feat: adiciona workflow n8n de classificacao de mensagem"
```

---

### Task 4: README e verificação manual

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: tudo das Tasks 1-3.
- Produces: documentação de como importar, configurar e testar o workflow n8n, e onde colocar a captura de tela exigida pelo item 3.4 do card.

- [ ] **Step 1: Rodar a suíte completa antes de editar (linha de base)**

Run: `pytest -q`
Expected: todos os testes passam (nenhuma mudança de código nesta task, só documentação).

- [ ] **Step 2: Adicionar a seção ao README**

Adicione ao `README.md`, depois da seção "## Painel Streamlit (Plano 5)" e antes de "## Limitações conhecidas do Plano 3" (ou na posição equivalente, se o arquivo tiver mudado — mantenha a ordem cronológica dos planos):

```markdown
## Workflow n8n (Plano 6)

Este workflow representa, de forma simplificada, a fatia "mensagem
recebida → classificação de urgência → roteamento" do sistema — **não**
substitui a integração real WhatsApp↔backend (WAHA→FastAPI, Plano 2), que
continua funcionando de forma independente. É um webhook próprio, só para
demonstrar a lógica de classificação/roteamento visualmente, conforme os
itens 3.4/3.8 do card.

1. Rode o backend normalmente (`uvicorn zela.api.main:app --reload`).
2. No seu n8n, importe `docs/n8n/zela-classificacao-mensagem.json`
   ("Import from File" ou colar o JSON em "Import from Clipboard").
3. Confira a URL configurada no nó **HTTP Request**
   (`http://localhost:8000/api/classificar-mensagem`) — se o n8n rodar em
   um container Docker separado do backend, troque `localhost` por
   `host.docker.internal` (ou o IP da máquina host); se rodar na mesma
   máquina fora de container, o padrão já funciona.
4. Ative o workflow (ou use "Execute Workflow"/"Listen for Test Event" no
   próprio n8n) e dispare o webhook com uma mensagem de teste:
   ```bash
   curl -X POST http://localhost:5678/webhook/zela-classificar-mensagem \
     -H "Content-Type: application/json" \
     -d '{"telefone": "+5511999999999", "texto": "caí no banheiro e não consigo levantar"}'
   ```
   (ajuste a porta `5678` se seu n8n usar outra, e use
   `/webhook-test/...` em vez de `/webhook/...` se estiver no modo de
   teste do editor, conforme a própria interface do n8n indicar).
5. Confirme que a resposta reflete o roteamento esperado (`"acao":
   "alertar_familia"` para uma mensagem de risco, por exemplo) e tire uma
   captura de tela do workflow no editor do n8n (com uma execução recente
   visível) — salve como `docs/n8n/screenshot.png` para o item 3.4 do
   card.

**Nota:** o endpoint `/api/classificar-mensagem` só classifica — nunca
decide nem dispara escalonamento de verdade (isso continua sendo
responsabilidade exclusiva do scheduler determinístico, Plano 3/4). Testar
este workflow à vontade não aciona nenhum alerta real à família.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: adiciona instrucoes do workflow n8n (Plano 6)"
```
