# Lembrete de remédio com enquete: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O lembrete de remédio sai como enquete "✅ Tomei / ⏰ Ainda não" no WhatsApp, e o voto "Tomei" registra a dose sem passar pela IA.

**Architecture:** O `WahaClient` ganha `enviar_enquete`. Um módulo de domínio puro guarda os textos, as opções e a normalização da chave. Uma tabela nova liga cada enquete ao remédio e ao horário. O scheduler envia a enquete, com o texto como reserva. O webhook desvia `poll.vote` para um callback, `processar_voto`, que confirma a dose de forma idempotente.

**Tech Stack:** FastAPI, APScheduler, SQLite, httpx, WAHA (WEBJS), pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-enquete-remedio-design.md`

## Global Constraints

- Opções exatas: `"✅ Tomei"` e `"⏰ Ainda não"`; enquete de escolha única (`multipleAnswers: false`).
- Pergunta: `f"Hora de tomar {nome} ({quantidade} {unidade}). Já tomou?"`.
- Respostas: `"Anotado! ✅ Dose de {nome} registrada."` e `"Tudo bem! Quando tomar, é só tocar em ✅ Tomei ou me escrever 'tomei'."`.
- Falha da enquete nunca deixa o idoso sem lembrete: cai no `formatar_lembrete` atual.
- O webhook nunca devolve 500 por causa de um voto, porque o WAHA repetiria o evento.
- Commits em PT-BR, `git add` com caminhos explícitos, sem push.

## Review Focus

1. **`poll.id` do voto com prefixo diferente da resposta do `sendPoll`:** a chave normalizada (depois do último `_`) precisa coincidir. Teste em Task 1 e Task 4 com os dois formatos.
2. **Voto repetido ou trocado depois de confirmado:** não grava outra confirmação nem responde de novo. Teste em Task 4.
3. **Voto de um número fora da lista de permitidos**, por exemplo um familiar ou um estranho num grupo: é ignorado. Teste em Task 5.
4. **WAHA sem `enviar_enquete` funcionando** (exceção HTTP): o texto antigo é enviado e nada é gravado em `enquete_lembrete`. Teste em Task 3.
5. **`poll.vote.failed` e voto com `selectedOptions` vazio:** respondem 200, sem confirmar nem quebrar. Teste em Task 5.

---

### Task 1: Domínio da enquete e envio pelo WAHA

**Files:**
- Create: `zela/domain/enquete_remedio.py`
- Modify: `zela/integrations/waha_client.py`
- Test: `tests/test_domain_enquete_remedio.py`, `tests/test_integrations_waha_client.py`

**Interfaces:**
- Produces:
  - `OPCAO_TOMEI = "✅ Tomei"`, `OPCAO_AINDA_NAO = "⏰ Ainda não"`, `OPCOES = [OPCAO_TOMEI, OPCAO_AINDA_NAO]`
  - `pergunta_lembrete(medicamento: Medicamento) -> str`
  - `chave_da_mensagem(identificador: str | dict) -> str`: com dict, usa `["_serialized"]`; devolve o trecho depois do último `_` (ou o texto inteiro se não houver `_`).
  - `interpretar_voto(selecionadas: list[str]) -> str | None`: `"tomei"`, `"ainda_nao"` ou `None` (lista vazia ou opção desconhecida).
  - `resposta_tomei(medicamento: Medicamento) -> str`, `RESPOSTA_AINDA_NAO: str`
  - `WahaClient.enviar_enquete(telefone: str, pergunta: str, opcoes: list[str]) -> str`: POST `/api/sendPoll` com `{"session", "chatId": resolver_chat_id(telefone), "poll": {"name", "options", "multipleAnswers": False}}`, `raise_for_status`, devolve `chave_da_mensagem(resposta["id"])`.

- [ ] **Step 1: Write the failing tests**

```python
def test_pergunta_lembrete_usa_nome_e_dose(): ...  # == "Hora de tomar dipirona (1.0 comprimido). Já tomou?"
def test_chave_da_mensagem_ignora_prefixo():
    assert chave_da_mensagem("true_123@lid_3EB047657A643465") == "3EB047657A643465"
    assert chave_da_mensagem({"_serialized": "true_123@lid_3EB047657A643465"}) == "3EB047657A643465"
    assert chave_da_mensagem("3EB047657A643465") == "3EB047657A643465"
def test_interpretar_voto():
    assert interpretar_voto(["✅ Tomei"]) == "tomei"
    assert interpretar_voto(["⏰ Ainda não"]) == "ainda_nao"
    assert interpretar_voto([]) is None
    assert interpretar_voto(["outra"]) is None
def test_resposta_tomei_cita_o_remedio(): ...  # == "Anotado! ✅ Dose de dipirona registrada."
def test_enviar_enquete_monta_payload_e_devolve_chave(monkeypatch):
    # monkeypatch de httpx.post como em test_enviar_texto_monta_payload_correto;
    # assert url termina em "/api/sendPoll", json["poll"] == {"name": "P?", "options": OPCOES, "multipleAnswers": False}
    # resposta fake {"id": {"_serialized": "true_1@lid_ABC"}} → retorno == "ABC"
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_domain_enquete_remedio.py tests/test_integrations_waha_client.py`
Expected: FAIL (`ModuleNotFoundError: zela.domain.enquete_remedio` e `AttributeError: enviar_enquete`).

- [ ] **Step 3: Implement the module and the method** as in Interfaces.

- [ ] **Step 4: Run to verify they pass** (same command, PASS).

- [ ] **Step 5: Commit**

```bash
git add zela/domain/enquete_remedio.py zela/integrations/waha_client.py tests/test_domain_enquete_remedio.py tests/test_integrations_waha_client.py
git commit -m "feat: enquete de lembrete de remédio no WAHA"
```

### Task 2: Tabela de enquetes

**Files:**
- Modify: `zela/storage/db.py` (nova tabela no schema)
- Create: `zela/storage/enquetes.py`
- Test: `tests/test_storage_enquetes.py`, `tests/test_storage_db.py` (lista de tabelas)

**Interfaces:**
- Produces:
  - Tabela `enquete_lembrete (chave TEXT PRIMARY KEY, idoso_id TEXT NOT NULL, medicamento_id TEXT NOT NULL, horario_previsto TEXT NOT NULL, enviada_em TEXT NOT NULL)`
  - `EnqueteLembrete` (dataclass frozen em `zela/storage/enquetes.py`): `chave: str, idoso_id: str, medicamento_id: str, horario_previsto: datetime`
  - `salvar_enquete(conn, enquete: EnqueteLembrete, enviada_em: datetime) -> None` (`INSERT OR IGNORE`)
  - `obter_enquete(conn, chave: str) -> EnqueteLembrete | None`

- [ ] **Step 1: Write the failing tests**: `test_salva_e_obtem_enquete_pela_chave` (ida e volta preserva `horario_previsto`), `test_obter_enquete_desconhecida_devolve_none`, `test_salvar_a_mesma_chave_duas_vezes_nao_falha`, e `"enquete_lembrete"` na lista esperada de `tests/test_storage_db.py`.
- [ ] **Step 2: Run, verify FAIL**: `.venv/bin/python -m pytest -q tests/test_storage_enquetes.py tests/test_storage_db.py`
- [ ] **Step 3: Implement** the table and the functions.
- [ ] **Step 4: Run, verify PASS.**
- [ ] **Step 5: Commit**: `git add zela/storage/db.py zela/storage/enquetes.py tests/test_storage_enquetes.py tests/test_storage_db.py && git commit -m "feat: guarda as enquetes de lembrete no banco"`

### Task 3: Scheduler envia a enquete

**Files:**
- Modify: `zela/api/scheduler.py` (`verificar_e_enviar_lembretes`)
- Test: `tests/test_api_scheduler.py`

**Interfaces:**
- Consumes: `pergunta_lembrete`, `OPCOES`, `WahaClient.enviar_enquete`, `salvar_enquete`, `EnqueteLembrete` (Tasks 1–2).
- Produces: `verificar_e_enviar_lembretes` mantém a assinatura e o retorno (`list[str]` com o texto enviado: a pergunta quando foi enquete, o texto antigo quando caiu no reserva).

Comportamento: para cada remédio pendente, tenta `waha_client.enviar_enquete(destino, pergunta_lembrete(m), OPCOES)`. Se der certo, `salvar_enquete` com `horario_previsto = datetime.combine(agora.date(), horario)`. Se levantar exceção, loga e chama `enviar_texto(destino, formatar_lembrete(m))`. O Gmail e a desduplicação ficam como estão.

- [ ] **Step 1: Write the failing tests**
  - Dar ao `_WahaFalso` um `enviar_enquete` que grava `(telefone, pergunta, opcoes)` em `self.enquetes` e devolve `"CHAVE1"`.
  - `test_lembrete_sai_como_enquete_e_fica_guardado`: uma enquete enviada com `OPCOES`, nenhum `enviar_texto` e `obter_enquete(conn, "CHAVE1")` com o remédio e o horário previsto certos.
  - `test_lembrete_cai_no_texto_se_a_enquete_falhar`: o fake levanta `httpx.HTTPError`; sai um texto igual a `formatar_lembrete(m)` e nada é gravado.
  - Ajustar os testes de lembrete existentes que esperam texto, se houver.
- [ ] **Step 2: Run, verify FAIL**: `.venv/bin/python -m pytest -q tests/test_api_scheduler.py -k lembrete`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, verify PASS**, then the full suite (`.venv/bin/python -m pytest -q`).
- [ ] **Step 5: Commit**: `git add zela/api/scheduler.py tests/test_api_scheduler.py && git commit -m "feat: lembrete de remédio sai como enquete, com texto de reserva"`

### Task 4: Tratar o voto

**Files:**
- Create: `zela/api/enquete.py`
- Test: `tests/test_api_enquete.py`

**Interfaces:**
- Consumes: `obter_enquete`, `interpretar_voto`, `chave_da_mensagem`, `resposta_tomei`, `RESPOSTA_AINDA_NAO`, `listar_medicamentos`, `listar_confirmacoes_do_dia`, `aplicar_confirmacao`.
- Produces: `processar_voto(conn, id_idoso: str, chave_enquete: str, selecionadas: list[str], agora: datetime) -> str | None`. Devolve o texto a responder ao idoso, ou `None` quando não há o que responder: enquete desconhecida, de outro idoso, voto vazio, remédio removido ou dose já confirmada para aquele `horario_previsto` (status CONFIRMADO ou ATRASADO).

- [ ] **Step 1: Write the failing tests**
  - `test_voto_tomei_registra_confirmacao_e_responde`: confirmação gravada com o `horario_previsto` da enquete, status CONFIRMADO e resposta igual a `resposta_tomei(m)`.
  - `test_voto_tomei_depois_de_30_min_fica_atrasado`
  - `test_voto_repetido_nao_duplica_nem_responde`: segunda chamada devolve `None`, e há 1 confirmação.
  - `test_voto_ainda_nao_nao_registra_e_responde`: nenhuma confirmação; resposta igual a `RESPOSTA_AINDA_NAO`.
  - `test_voto_vazio_ou_enquete_desconhecida_devolve_none`
  - `test_chave_com_prefixo_encontra_a_enquete`: a enquete é salva com a chave `"ABC"` e o voto chega com `"true_1@lid_ABC"`. O callback normaliza com `chave_da_mensagem`.
- [ ] **Step 2: Run, verify FAIL**: `.venv/bin/python -m pytest -q tests/test_api_enquete.py`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, verify PASS.**
- [ ] **Step 5: Commit**: `git add zela/api/enquete.py tests/test_api_enquete.py && git commit -m "feat: voto 'Tomei' na enquete confirma a dose"`

### Task 5: Webhook e ligação no app

**Files:**
- Modify: `zela/api/webhook.py`, `zela/api/main.py`
- Test: `tests/test_api_webhook.py`

**Interfaces:**
- Consumes: `processar_voto` (Task 4).
- Produces: `montar_roteador(..., processar_voto: Callable[[str, list[str], datetime], str | None] | None = None)`. O callback recebe `(chave_enquete, selecionadas, agora)`; `main.py` fecha sobre a conexão e o `ID_IDOSO`.

Comportamento no webhook, depois da checagem do token e antes de `_extrair_telefone_e_texto`:
- `event == "poll.vote.failed"`: `logger.warning(...)` e devolve `{"status": "ignorado"}`.
- `event == "poll.vote"`: lê `payload.vote.from`, `payload.vote.fromMe`, `payload.vote.selectedOptions` e `payload.poll.id`.
  - Votos próprios (`fromMe`) e remetentes fora da lista de permitidos (a mesma regra de telefone e LID das mensagens) são ignorados.
  - Os demais vão para `processar_voto` em threadpool. Se ele devolver texto, envia com `waha_client.enviar_texto(vote.from, texto)`.
  - Exceções viram log, e a resposta é `{"status": "voto"}`.

- [ ] **Step 1: Write the failing tests** (payload no formato observado em produção: `{"event": "poll.vote", "payload": {"vote": {"from": "<lid>@lid", "fromMe": false, "selectedOptions": ["✅ Tomei"], ...}, "poll": {"id": "true_x@lid_ABC", ...}}}`):
  - `test_voto_chama_processar_voto_e_responde_quem_votou`: o fake recebe `("true_x@lid_ABC", ["✅ Tomei"], <datetime>)` e o WAHA fake envia a resposta para o mesmo JID.
  - `test_voto_fora_da_lista_permitida_e_ignorado`
  - `test_voto_falho_so_gera_log` (`poll.vote.failed` → 200, sem chamar o callback)
  - `test_voto_com_erro_no_callback_responde_200_sem_enviar`
  - `test_voto_nao_vai_para_o_llm`: `processar_mensagem` não é chamado.
- [ ] **Step 2: Run, verify FAIL**: `.venv/bin/python -m pytest -q tests/test_api_webhook.py`
- [ ] **Step 3: Implement** in the webhook and wire it in `main.py`.
- [ ] **Step 4: Run, verify PASS**, then the full suite.
- [ ] **Step 5: Commit**: `git add zela/api/webhook.py zela/api/main.py tests/test_api_webhook.py && git commit -m "feat: webhook trata votos de enquete"`

### Task 6: Documentação e passo de deploy

**Files:**
- Modify: `README.md` (seção de lembretes/WhatsApp), `docs/deploy/vps.md` (configuração do webhook do WAHA), `RELATORIO.md` (escopo e resultados, só o que já for verdade), `RELATORIO.pdf` (regenerar com `scripts/gerar_relatorio_pdf.py`)

- [ ] **Step 1:** README: o lembrete chega como enquete; "tomei" por texto continua; o WAHA precisa dos eventos `message`, `poll.vote` e `poll.vote.failed`.
- [ ] **Step 2:** `vps.md`: passo de deploy para atualizar os eventos do webhook da sessão `default`. Primeiro guardar a configuração atual em arquivo `600`. Depois fazer `PUT /api/sessions/default` com a mesma lista de webhooks e os 3 eventos, esperar `WORKING` e conferir. A reversão é o `PUT` da cópia.
- [ ] **Step 3:** RELATORIO.md: uma linha no escopo (lembrete com enquete) e a limitação dos botões (só API oficial). Regenerar o PDF.
- [ ] **Step 4: Commit**: `git add README.md docs/deploy/vps.md RELATORIO.md RELATORIO.pdf && git commit -m "docs: lembrete de remédio com enquete"`

## Validação em produção (depois do merge, com o usuário)

1. Deploy do backend e, em seguida, configuração dos eventos do WAHA (Task 6, com cópia de segurança).
2. Cadastrar um remédio para 2 a 3 min à frente; a enquete chega e a pulseira vibra com "Zela+: hora do remédio".
3. Votar "✅ Tomei"; chega "Anotado! ✅ …", e o painel mostra a dose como confirmada.
4. Votar de novo; nada novo acontece.
