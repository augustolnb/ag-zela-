# Estratégia de Testes e Resultados — Zela+

Este documento complementa o `RELATORIO.md` (seção 4, "Resultados
obtidos") com o detalhamento completo da suíte automatizada: o que é
testado, por que foi testado dessa forma, e o resultado real da última
execução. Serve tanto como evidência técnica para o card quanto como
referência para quem for dar manutenção no projeto depois.

---

## 1. Visão geral

- **Framework:** `pytest`.
- **Tamanho da suíte:** 186 testes, em 38 arquivos, cobrindo todo o
  código de produção do repositório (`zela/`).
- **Execução:** `pytest -v` (ou `.venv/bin/pytest -v` sem ativar o
  ambiente), a partir da raiz do repositório. Tempo de execução: ~20
  segundos, sem rede nem hardware externo.
- **Princípio central:** a suíte automatizada nunca faz uma chamada real
  a LLM, rede, ou hardware. Isso foi uma decisão deliberada, justificada
  na seção 2 abaixo — o comportamento que depende dessas coisas é
  verificado manualmente (ver seção 6).

---

## 2. Decisões de design dos testes (e por quê)

### 2.1 Nenhum teste chama um LLM ou a rede de verdade

Os agentes ADK, o cliente de embeddings do Gemini, e a integração com o
WAHA (WhatsApp) nunca são exercitados com uma chamada real durante
`pytest -v`. Motivos:

1. **Determinismo:** um teste que depende da resposta de um LLM pode
   passar ou falhar de forma não-determinística, mesmo sem nenhuma
   mudança no código — isso corrompe a confiança na suíte.
2. **Velocidade e custo:** a suíte roda em ~20s sem nenhuma chamada de
   rede; chamadas reais ao Gemini custariam tempo, dinheiro (cota de
   API) e dependeriam de uma chave configurada no ambiente de CI/execução.
3. **A pergunta que a suíte automatizada responde é outra:** "a lógica de
   negócio está correta?", não "o LLM responde bem?". Essa segunda
   pergunta é verificada manualmente com `adk run zela/agents` (ver
   README, seção "Verificando o comportamento do agente"), que é por
   definição uma verificação qualitativa, não pass/fail.

Na prática, isso é obtido testando as **ferramentas** dos agentes
(`verificar_lembretes_pendentes`, `confirmar_medicamento`,
`consultar_status_atual`, `consultar_conhecimento`,
`consultar_historico_alertas` — funções Python puras que o ADK expõe ao
LLM) diretamente, e testando a **estrutura** dos agentes ADK (nomes,
hierarquia de `sub_agents`, `tools` atribuídas) sem invocar o modelo.

### 2.2 Nenhum dado é validado "confiando" na camada acima

Toda entrada externa (leitura de sensor, mensagem de WhatsApp, cadastro
de medicamento) passa por um modelo Pydantic antes de qualquer lógica de
negócio — e os testes de `tests/test_models_*.py` verificam tanto o
caminho feliz quanto a rejeição de dados inválidos (datas no passado,
enums fora do conjunto esperado, campos obrigatórios ausentes). Essa
camada é testada isoladamente da lógica de domínio, para que uma falha
de validação e uma falha de regra de negócio nunca apareçam confundidas
no mesmo teste.

### 2.3 Storage usa SQLite real, não um banco "mockado"

Os testes de `tests/test_storage_*.py` abrem uma conexão SQLite real em
memória (`conectar(":memory:")`) em vez de simular o banco com mocks.
Isso é intencional: um mock de banco de dados testa "o código chama o
método certo", mas não testa se o SQL em si está correto, se as
migrações (`ALTER TABLE` idempotente, ver `zela/storage/db.py`) funcionam,
ou se os tipos retornados pelo SQLite (strings, não objetos Python) são
convertidos corretamente de volta para os modelos Pydantic. Rodar contra
um SQLite real (ainda que em memória, então sem custo de I/O em disco)
captura esses bugs de integração sem precisar de uma rede ou de um banco
externo.

### 2.4 Streamlit é testado com execução real da interface, não mocks

`tests/test_streamlit_*.py` usa `streamlit.testing.v1.AppTest`, o
framework de testes **oficial** do próprio Streamlit — ele executa o
script da aplicação de ponta a ponta (de verdade, não uma simulação) e
inspeciona a árvore de widgets renderizada. Isso foi escolhido em vez de
simplesmente testar as funções internas isoladamente porque o
comportamento mais frágil de uma interface Streamlit costuma estar na
**composição** (ordem de renderização, `st.rerun()`, `session_state`
entre execuções) — exatamente o tipo de bug que um teste de função
isolada não captura, mas que um dos fix-waves do projeto (duplicação
silenciosa de registros em double-submit) encontrou e corrigiu.

### 2.5 O workflow n8n tem apenas teste estrutural — e isso é documentado como limitação, não escondido

`tests/test_n8n_workflow.py` valida que o arquivo
`docs/n8n/zela-classificacao-mensagem.json` é um JSON válido, com os
nós, tipos, parâmetros (`contentType`, `specifyBody`, `jsonBody`) e
conexões esperados — inclusive comparando os valores de roteamento contra
o enum real `StatusMonitoramento` do código Python, para que um rename
futuro quebre o teste em vez de passar silenciosamente. O que esse teste
**não** faz — e não pode fazer a partir de `pytest` — é executar o
workflow de verdade dentro do n8n (uma ferramenta externa, fora do
processo Python). Essa é uma limitação conhecida e documentada (README,
"Limitações conhecidas do Plano 6"), não uma omissão: a verificação de
ponta a ponta desse fluxo é manual (seção 6 abaixo).

Vale registrar que esse foi exatamente o tipo de lacuna que permitiu um
bug real passar despercebido pelos testes de task individuais durante o
desenvolvimento: um valor inválido (`"application/json"` em vez de
`"json"`) no campo `contentType` fazia o n8n descartar o corpo da
requisição silenciosamente. Só foi pego numa revisão final de escopo
mais amplo, o que motivou reforçar exatamente esses dois testes
(`test_workflow_http_request_envia_texto_como_corpo_json` e
`test_workflow_condicoes_de_roteamento_usam_valores_do_enum_real`) depois
da correção.

---

## 3. Organização da suíte por camada

| Camada | Arquivos de teste | O que valida |
|---|---|---|
| **Modelos (Pydantic)** | `test_models_rotina.py`, `test_models_monitoramento.py`, `test_models_perfil.py`, `test_models_comunicacao_alertas.py` | Validação de dados de entrada: aceita o caminho feliz, rejeita dados inválidos (datas passadas, enums fora do conjunto, campos obrigatórios) |
| **Domínio (lógica pura)** | `test_domain_rotina.py`, `test_domain_monitoramento.py`, `test_domain_emergencia.py`, `test_domain_comunicacao.py` | Regras de negócio sem I/O: cálculo de lembretes pendentes, classificação de risco por sensor, a máquina de estados de escalonamento de emergência |
| **Armazenamento (SQLite)** | `test_storage_rotina.py`, `test_storage_monitoramento.py`, `test_storage_perfil.py`, `test_storage_alertas.py`, `test_storage_escalonamento.py`, `test_storage_db.py` | Persistência real (SQLite em memória): salvar/listar, migrações idempotentes, conversão de tipos |
| **API (FastAPI)** | `test_api_webhook.py`, `test_api_ingestao.py`, `test_api_scheduler.py`, `test_api_runner.py`, `test_api_main.py`, `test_api_monitoramento_mensagem.py`, `test_api_reindexacao.py`, `test_api_classificacao.py` | Endpoints via `TestClient` (sem subir um servidor de verdade): webhook do WhatsApp, ingestão de sensores, scheduler de lembretes, ponte com o ADK Runner, classificação de mensagens |
| **Embeddings** | `test_embeddings_classificador.py`, `test_embeddings_client.py`, `test_embeddings_exemplos_referencia.py`, `test_embeddings_vetorial.py` | Classificação por similaridade (sem chamar o Gemini — vetores sintéticos), cliente preguiçoso (lazy init), vector store Chroma |
| **Agentes ADK** | `test_agents_orchestrator.py`, `test_agents_orchestrator_tools.py`, `test_agents_orchestrator_tools_comunicacao.py`, `test_agents_orchestrator_tools_monitoramento.py` | Estrutura dos 5 agentes (nomes, hierarquia, tools atribuídas) e as ferramentas Python que eles expõem ao LLM, chamadas diretamente |
| **Integrações** | `test_integrations_waha_client.py` | Cliente WAHA (montagem de payloads), sem chamar o WAHA de verdade |
| **Painel Streamlit** | `test_streamlit_app.py`, `test_streamlit_autenticacao.py`, `test_streamlit_formularios.py`, `test_streamlit_secoes.py` | Execução real da interface via `AppTest`: autenticação, as 4 seções de leitura, os 2 formulários de escrita |
| **Workflow n8n** | `test_n8n_workflow.py` | Estrutura do JSON exportado (nós, tipos, parâmetros, conexões, valores de roteamento) |
| **Simulação de ponta a ponta** | `test_simulacao.py` | Um "dia" completo do sistema simulado, sem hardware nem rede, validando a lógica de domínio integrada |

---

## 4. Cobertura por arquivo (contagem de testes)

| Arquivo | Testes |
|---|---:|
| `test_api_scheduler.py` | 10 |
| `test_api_ingestao.py` | 10 |
| `test_storage_rotina.py` | 9 |
| `test_api_webhook.py` | 9 |
| `test_streamlit_secoes.py` | 8 |
| `test_models_rotina.py` | 8 |
| `test_agents_orchestrator_tools_monitoramento.py` | 8 |
| `test_storage_monitoramento.py` | 7 |
| `test_embeddings_classificador.py` | 7 |
| `test_streamlit_formularios.py` | 6 |
| `test_n8n_workflow.py` | 6 |
| `test_domain_rotina.py` | 6 |
| `test_domain_emergencia.py` | 6 |
| `test_agents_orchestrator_tools.py` | 6 |
| `test_streamlit_autenticacao.py` | 5 |
| `test_models_perfil.py` | 5 |
| `test_api_runner.py` | 5 |
| `test_api_main.py` | 5 |
| `test_storage_escalonamento.py` | 4 |
| `test_storage_alertas.py` | 4 |
| `test_models_monitoramento.py` | 4 |
| `test_embeddings_vetorial.py` | 4 |
| `test_domain_monitoramento.py` | 4 |
| `test_domain_comunicacao.py` | 4 |
| `test_agents_orchestrator_tools_comunicacao.py` | 4 |
| `test_storage_perfil.py` | 3 |
| `test_storage_db.py` | 3 |
| `test_models_comunicacao_alertas.py` | 3 |
| `test_integrations_waha_client.py` | 3 |
| `test_embeddings_exemplos_referencia.py` | 3 |
| `test_embeddings_client.py` | 3 |
| `test_api_monitoramento_mensagem.py` | 3 |
| `test_api_classificacao.py` | 3 |
| `test_streamlit_app.py` | 2 |
| `test_simulacao.py` | 2 |
| `test_api_reindexacao.py` | 2 |
| `test_agents_orchestrator.py` | 2 |
| **Total** | **186** |

*(Não há uma ferramenta de medição de cobertura de linha, tipo
`pytest-cov`, configurada no projeto — a tabela acima mede quantidade de
testes por arquivo, não porcentagem de linhas de código exercitadas. Ver
seção 7 para essa limitação.)*

---

## 5. Resultado da última execução

```
$ pytest -v
...
186 passed, 3 warnings in 19.99s
```

- **Ambiente:** Python 3.12, dentro do `.venv` do projeto
  (`pip install -e ".[dev]"`).
- **Versões relevantes:** pytest 9.1.1, FastAPI 0.141.1, Pydantic 2.13.5,
  google-adk 2.9.0, google-genai 2.23.0, chromadb 1.5.9, APScheduler
  3.11.3, Streamlit 1.64.0.
- **Falhas:** nenhuma. 0 de 186 testes falhando.
- **Erros de coleta:** nenhum, desde que a suíte seja executada com o
  `.venv` ativado (ver nota abaixo).

**Nota operacional importante:** rodar `pytest` com o Python do sistema
em vez do `.venv` do projeto causa 14 erros de coleta
(`ModuleNotFoundError` para `chromadb`, `apscheduler` e `streamlit`) —
não é uma falha de teste, é a suíte inteira não conseguindo nem importar
os módulos porque as dependências do projeto não estão instaladas nesse
interpretador. Sempre ative o ambiente antes:
```bash
source .venv/bin/activate
pytest -v
```

### Warnings conhecidos (não indicam falha)

Três `DeprecationWarning`/`StarletteDeprecationWarning` aparecem em toda
execução, originados em bibliotecas de terceiros, não no código do
projeto:

1. `BaseAgentConfig is deprecated` — aviso interno do `google-adk` sobre
   uma mudança futura na forma de configurar agentes.
2. `Using httpx with starlette.testclient is deprecated` — o FastAPI
   avisa que uma versão futura vai preferir a lib `httpx2`.
3. `anyio.abc.BlockingPortal alias is deprecated` — aviso interno do
   Starlette sobre uma renomeação futura na biblioteca `anyio`.

Nenhum dos três afeta o resultado dos testes nem indica um bug no
projeto — são avisos de depreciação de APIs internas de dependências,
não erros.

---

## 6. O que não é coberto por testes automatizados (e como é verificado)

| Comportamento | Por que não é automatizado | Como verificar manualmente |
|---|---|---|
| Resposta/roteamento real de um LLM (Gemini) | Não-determinístico, custa cota de API | `adk run zela/agents` (ver README) |
| Execução real do workflow n8n | n8n é uma ferramenta externa ao processo Python | Importar o `.json` no n8n e disparar o webhook de teste (ver README, "Workflow n8n") |
| Integração real com o WAHA/WhatsApp | Depende de um servidor WAHA rodando e de um número de WhatsApp real | Seguir "Configurando o WAHA" no README, com um backend rodando de verdade |
| Leitura real de hardware (ESP32, smartwatch) | Depende de hardware físico | Firmware em `firmware/zela_presenca/`, app "Health Connect Webhook" (ver README) |
| Qualidade visual da interface Streamlit | `AppTest` verifica a árvore de widgets, não a aparência renderizada | Rodar `streamlit run zela/streamlit_app/app.py` e inspecionar visualmente |
| Cobertura de linha (% do código exercitado) | Nenhuma ferramenta de cobertura configurada no projeto | Não medido — ver nota abaixo |

Essas lacunas são decisões conscientes de escopo de um MVP, documentadas
também no `README.md` ("Limitações conhecidas") — não foram descobertas
depois da entrega, mas reconhecidas durante o próprio desenvolvimento.

**Nota sobre cobertura de linha:** o projeto não usa `pytest-cov` nem
nenhuma outra ferramenta de medição de cobertura. A extensão da suíte
(186 testes cobrindo toda camada do código, da validação de dados até a
interface) foi verificada por leitura e pela prática de TDD usada durante
o desenvolvimento (teste escrito antes da implementação, a cada tarefa),
não por uma métrica percentual. Adicionar `pytest-cov` é uma melhoria
simples e de baixo risco para quem quiser medir isso precisamente no
futuro — `pip install pytest-cov` e `pytest --cov=zela`.
