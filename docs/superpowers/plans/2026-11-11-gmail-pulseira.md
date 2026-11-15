# Notificações na pulseira via Gmail — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enviar ao Gmail da conta de teste, logada no celular do idoso, os lembretes de remédio, a pergunta "você está bem?" depois de um sintoma e a checagem da escada de risco, para a notificação aparecer na pulseira.

**Architecture:** Um `GmailClient` (httpx, mesmo padrão do `GoogleCalendarClient`) com dois modos (`insert` e `send`). Textos curtos para a pulseira saem de funções puras em `zela/domain/pulseira.py`, e um wrapper `notificar_pulseira` engole falhas. O scheduler e o aviso à família recebem o cliente como parâmetro opcional; sem ele, nada muda.

**Tech Stack:** Python 3.11, httpx, `email.message.EmailMessage`, Gmail API v1, APScheduler, pytest.

**Spec:** `docs/superpowers/specs/2026-11-11-gmail-pulseira-design.md`

## Global Constraints

- O Gmail nunca atrasa, bloqueia ou cancela o WhatsApp, o episódio de 60 s ou a escada; falha só gera `logger.exception`.
- Sem `ZELA_GMAIL_PULSEIRA_EMAIL` ou sem as 3 credenciais `ZELA_GOOGLE_CALENDAR_CLIENT_ID/_SECRET/_REFRESH_TOKEN`, `gmail_client` é `None` e o comportamento é idêntico ao atual.
- Assunto com no máximo 40 caracteres.
- `ZELA_GMAIL_MODO` aceita `insert` (padrão) ou `send`.
- Escopos do token: `https://www.googleapis.com/auth/calendar`, `https://www.googleapis.com/auth/gmail.insert` e `https://www.googleapis.com/auth/gmail.send`.
- Commits em PT-BR, `git add` só com caminhos explícitos, `timeout=30` nas chamadas httpx.
- Nunca imprimir tokens, client secret nem o refresh token em logs ou na saída dos scripts.

## Review Focus

1. **Gmail lento no webhook:** um relato de sintoma não pode esperar a API do Google para receber a pergunta de confirmação. A notificação roda em um `ThreadPoolExecutor`. Teste na Task 4: `triar_mensagem` só chama o callback, sem fazer I/O.
2. **Gmail com exceção:** o lembrete por WhatsApp é enviado e registrado, e a escada salva o alerta. Testes nas Tasks 4 e 5 com um cliente que lança `RuntimeError`.
3. **Acentos no assunto:** "remédio" e "você" precisam chegar corretos. Teste na Task 1 decodificando o `raw`.
4. **Variáveis ausentes ou vazias:** o docker-compose define strings vazias, e `or None` precisa desligar a função. Teste na Task 5.
5. **Notificação duplicada:** o lembrete repetido no mesmo horário não gera um segundo e-mail; um novo relato com episódio aberto não notifica. Testes nas Tasks 4 e 5.

---

### Task 0 (manual, usuário): comissionamento da conta Google

- [ ] No projeto do Google Cloud do Google Agenda, ativar também a **Gmail API**.
- [ ] Seguir "Comissionamento: Google Agenda" no README depois da Task 2, que muda os escopos do script de token, com a conta de teste.
- [ ] No celular do idoso: Gmail logado na conta de teste, notificações do Gmail ligadas para essa conta e o Gmail liberado no espelhamento de notificações do Mi Fitness.

### Task 1: Token compartilhado e `GmailClient`

**Files:**
- Create: `zela/integrations/google_oauth.py`, `zela/integrations/gmail_client.py`
- Modify: `zela/integrations/google_calendar_client.py` (o `_access_token` delega ao helper; o atributo `TOKEN_URL` continua igual)
- Test: `tests/test_integrations_gmail_client.py`

**Interfaces:**
- Produces: `obter_access_token(client_id: str, client_secret: str, refresh_token: str) -> str` e `TOKEN_URL` em `google_oauth.py`.
- Produces: `GmailClient(client_id, client_secret, refresh_token, email: str, modo: str = "insert")`, com `notificar(assunto: str, corpo: str) -> str` (devolve o id da mensagem). `modo` e `email` ficam como atributos públicos. `modo` fora de `{"insert", "send"}` gera `ValueError` no `__init__`.

- [ ] **Step 1: Write the failing tests** (mesmo `_RespostaFalsa` e `monkeypatch.setattr(httpx, "post", ...)` de `tests/test_integrations_google_calendar_client.py`):

```python
def test_modo_insert_poe_na_caixa_de_entrada_como_nao_lida(monkeypatch):
    # chamadas[1]: url == "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    # params == {"internalDateSource": "dateHeader"}
    # json["labelIds"] == ["INBOX", "UNREAD"]; headers == {"Authorization": "Bearer tok-123"}
    # retorno == "msg-1" (json da resposta: {"id": "msg-1"})

def test_modo_send_usa_endpoint_de_envio(monkeypatch):
    # url == ".../users/me/messages/send"; "labelIds" not in json

def test_raw_decodifica_com_acentos_e_remetente_zela(monkeypatch):
    # email.message_from_bytes(base64.urlsafe_b64decode(json["raw"]), policy=email.policy.default)
    # msg["Subject"] == "Zela+: hora do remédio"; msg["To"] == "teste@gmail.com"
    # msg["From"] == "Zela+ <teste@gmail.com>"; msg["Date"] is not None
    # "Dipirona" in msg.get_content()

def test_modo_invalido_falha_na_criacao():
    # pytest.raises(ValueError): GmailClient(..., modo="smtp")

def test_erro_http_propaga(monkeypatch):
    # resposta 403 na chamada da API → pytest.raises(httpx.HTTPStatusError)
```

- [ ] **Step 2:** `pytest tests/test_integrations_gmail_client.py -v` deve falhar com `ModuleNotFoundError`.
- [ ] **Step 3: Implement.** O `httpx.post` da API recebe `params=` só no modo `insert`. A mensagem é montada com `EmailMessage` (`From`, `To`, `Subject`, `Date` via `email.utils.formatdate(localtime=True)`, `set_content(corpo)`), e o `raw` é `base64.urlsafe_b64encode(msg.as_bytes()).decode()`.
- [ ] **Step 4:** `pytest tests/test_integrations_gmail_client.py tests/test_integrations_google_calendar_client.py -v` deve passar.
- [ ] **Step 5: Commit:** `feat: adiciona cliente do Gmail para notificar a pulseira`.

### Task 2: Escopos do token e script de teste na pulseira (ponto de verificação com o usuário)

**Files:**
- Modify: `scripts/obter_refresh_token_google.py` (`ESCOPO` passa a ser os 3 escopos separados por espaço)
- Create: `scripts/testar_gmail_pulseira.py`
- Modify: `README.md`, seção "Comissionamento: Google Agenda" (ativar a Gmail API e o aviso sobre escopo restrito)

**Interfaces:**
- Consumes: `GmailClient` da Task 1.
- Produces: o script lê `ZELA_GOOGLE_CALENDAR_CLIENT_ID/_SECRET/_REFRESH_TOKEN` e `ZELA_GMAIL_PULSEIRA_EMAIL` do ambiente e envia `Zela+ teste (insert)` e `Zela+ teste (send)`, com 20 s de intervalo. Para cada modo, imprime `OK` ou `FALHOU: <status HTTP>`, sem imprimir credenciais.

- [ ] **Step 1:** Mudar `ESCOPO` e conferir com `grep -n ESCOPO scripts/obter_refresh_token_google.py`. Os 3 escopos devem aparecer.
- [ ] **Step 2:** Escrever o script, com saída 1 se nenhum modo der `OK`.
- [ ] **Step 3: Commit:** `feat: script de teste do Gmail na pulseira e escopos do token`.
- [ ] **Step 4 (usuário):** fazer a Task 0, rodar `python scripts/testar_gmail_pulseira.py` e anotar qual assunto vibrou na pulseira. **Parar aqui até a resposta.** O modo que funcionou vira o padrão em `ZELA_GMAIL_MODO`. Se nenhum funcionar, rever o design: o Gmail pode não notificar mensagens da própria conta, e a alternativa é enviar de uma segunda conta.

### Task 3: Textos para a pulseira

**Files:**
- Create: `zela/domain/pulseira.py`
- Test: `tests/test_domain_pulseira.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) NotificacaoPulseira(assunto: str, corpo: str)`
- Produces: `notificacao_lembrete_remedio(medicamento: Medicamento) -> NotificacaoPulseira`, `notificacao_confirmacao_sintoma(sintomas: list[str]) -> NotificacaoPulseira`, `notificacao_checagem(mensagem: str) -> NotificacaoPulseira`

- [ ] **Step 1: Failing tests:**

```python
def test_lembrete_traz_nome_e_dose():
    n = notificacao_lembrete_remedio(medicamento_dipirona)  # 1 "comp de 500mg"
    assert n.assunto == "Zela+: hora do remédio"
    assert "dipirona" in n.corpo and "500mg" in n.corpo and "WhatsApp" in n.corpo

def test_confirmacao_de_sintoma_pede_resposta_e_cita_192():
    n = notificacao_confirmacao_sintoma(["tontura"])
    assert n.assunto == "Zela+: você está bem?"
    assert "ESTOU BEM" in n.corpo and "60" in n.corpo and "192" in n.corpo and "tontura" in n.corpo

def test_checagem_repete_a_mensagem_do_alerta():
    n = notificacao_checagem("Tudo bem? Detectamos: ...")
    assert n.assunto == "Zela+: está tudo bem?" and n.corpo.startswith("Tudo bem?")

@pytest.mark.parametrize("n", [...as três...])
def test_assunto_cabe_na_pulseira(n):
    assert len(n.assunto) <= 40
```

- [ ] **Step 2:** Os testes falham. **Step 3:** Implementar. **Step 4:** Os testes passam.
- [ ] **Step 5: Commit:** `feat: textos curtos para notificações na pulseira`.

### Task 4: `notificar_pulseira` e o sintoma no webhook

**Files:**
- Create: `zela/api/pulseira.py`
- Modify: `zela/api/aviso_familia.py` (`triar_mensagem` e `_tratar_sintoma` ganham `ao_abrir_episodio`)
- Test: `tests/test_api_pulseira.py`, `tests/test_api_aviso_familia.py`

**Interfaces:**
- Produces: `notificar_pulseira(gmail_client, notificacao: NotificacaoPulseira) -> bool`. `None` devolve `False` sem chamar nada; uma exceção vira `logger.exception` e `False`; o sucesso devolve `True`.
- Produces: `triar_mensagem(conn, idoso_id, perfil, texto, agora, waha_client, ao_abrir_episodio: Callable[[list[str]], None] | None = None)`. O callback é chamado só quando um episódio **novo** de sintoma é aberto, depois do commit, e uma exceção dele é engolida com log.

- [ ] **Step 1: Failing tests:**

```python
def test_sem_cliente_nao_notifica(): assert notificar_pulseira(None, n) is False
def test_falha_do_gmail_vira_false(): # cliente.notificar levanta RuntimeError → False
def test_sucesso_chama_notificar_com_assunto_e_corpo(): # chamadas == [(n.assunto, n.corpo)]

def test_sintoma_novo_chama_callback_com_sintomas(tmp_path):
    # "estou com tontura" → callback recebeu ["tontura"] uma vez
def test_relato_com_episodio_aberto_nao_chama_callback_de_novo(tmp_path):
def test_callback_com_excecao_nao_impede_a_resposta_nem_o_episodio(tmp_path):
    # resposta contém "60 segundos" e obter_episodio_aberto(...) is not None
```

- [ ] **Step 2:** Os testes falham. **Step 3:** Implementar. **Step 4:** Rodar `pytest tests/test_api_pulseira.py tests/test_api_aviso_familia.py -v`; deve passar.
- [ ] **Step 5: Commit:** `feat: notifica a pulseira quando um sintoma abre episódio`.

### Task 5: Scheduler, `main.py` e docker-compose

**Files:**
- Modify: `zela/api/scheduler.py`: `verificar_e_enviar_lembretes`, `despachar_alertas`, `verificar_e_escalonar_riscos` e `iniciar_scheduler` ganham `gmail_client=None`
- Modify: `zela/api/main.py`, `docker-compose.yml`
- Test: `tests/test_api_scheduler.py`, `tests/test_api_main_gmail.py`

**Interfaces:**
- Consumes: `notificar_pulseira` (Task 4), `notificacao_lembrete_remedio` e `notificacao_checagem` (Task 3).
- Lembretes: depois do `waha_client.enviar_texto` bem-sucedido e antes de marcar `_lembretes_ja_enviados`, chamar `notificar_pulseira`.
- `despachar_alertas`: se `alerta.destinatario == perfil.nome` e `not alerta.simulado`, chamar `notificar_pulseira(gmail_client, notificacao_checagem(alerta.mensagem))` depois da tentativa no WhatsApp, mesmo que ela tenha falhado.
- `main.py`: `GMAIL_PULSEIRA_EMAIL = os.environ.get("ZELA_GMAIL_PULSEIRA_EMAIL") or None`, `GMAIL_MODO = os.environ.get("ZELA_GMAIL_MODO") or "insert"`. Cria `gmail_client` quando o e-mail e as 3 credenciais existem; senão, `None`. Um `ThreadPoolExecutor(max_workers=1)` de módulo envia a notificação do sintoma: `_processar_emergencia` passa `ao_abrir_episodio=lambda s: _executor.submit(notificar_pulseira, gmail_client, notificacao_confirmacao_sintoma(s))`.
- `docker-compose.yml`, serviço `backend`: `ZELA_GMAIL_PULSEIRA_EMAIL=${ZELA_GMAIL_PULSEIRA_EMAIL}` e `ZELA_GMAIL_MODO=${ZELA_GMAIL_MODO}`.

- [ ] **Step 1: Failing tests:**

```python
def test_lembrete_vai_ao_whatsapp_e_ao_gmail(tmp_path, monkeypatch):
    # gmail_falso.chamadas == [("Zela+: hora do remédio", ...)]
def test_lembrete_repetido_no_mesmo_horario_nao_gera_segundo_email(tmp_path, monkeypatch):
def test_gmail_com_falha_nao_impede_o_lembrete(tmp_path, monkeypatch):
    # retorno tem 1 texto; waha_falso.enviados tem 1 item
def test_checagem_ao_idoso_vai_ao_gmail_mas_aviso_a_familia_nao(tmp_path):
    # alertas para perfil.nome e para "Ana" → só 1 chamada no gmail
def test_alerta_simulado_nao_vai_ao_gmail(tmp_path):
def test_montar_gmail_client_desliga_sem_email():
    # _montar_gmail_client({"ZELA_GMAIL_PULSEIRA_EMAIL": "", ...3 credenciais...}) is None
def test_montar_gmail_client_usa_modo_insert_por_padrao():
    # com e-mail e credenciais, sem ZELA_GMAIL_MODO → cliente.modo == "insert"
```

`main.py` ganha a função pura `_montar_gmail_client(env: Mapping[str, str]) -> GmailClient | None`, chamada com `os.environ`. Ela evita recarregar o módulo `main` nos testes.

- [ ] **Step 2:** Os testes falham. **Step 3:** Implementar. **Step 4:** `pytest -q` passa a suíte completa (432 testes atuais mais os novos).
- [ ] **Step 5: Commit:** `feat: envia lembretes e checagens à pulseira pelo Gmail`.

### Task 6: Documentação, PR, deploy e validação real

- [ ] README: nova seção "Notificações na pulseira (Gmail)", com as variáveis, os modos e a configuração do celular. No `RELATORIO.md`, uma linha no escopo (1.2) e uma nas saídas da arquitetura.
- [ ] PR com o resultado do script da Task 2 na descrição. O usuário faz o merge e o deploy, e preenche `ZELA_GMAIL_PULSEIRA_EMAIL` e `ZELA_GMAIL_MODO` no `.env` da VPS.
- [ ] Validação em produção com o perfil de teste:
  1. Cadastrar um remédio para 2 minutos à frente. O WhatsApp e a pulseira devem receber "Zela+: hora do remédio".
  2. Mandar "estou com tontura". A resposta no WhatsApp deve chegar sem atraso, e a pulseira deve mostrar "Zela+: você está bem?". Responder ESTOU BEM.
  3. Conferir no log do backend que não houve `Falha` do Gmail.
- [ ] Atualizar `RELATORIO_ERROS.md` com qualquer problema real encontrado.
