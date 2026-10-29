# Alinhar o monitoramento do Zela ao memorial descritivo — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o Zela seguir as regras de monitoramento do memorial descritivo do kit da empresa:
- ausência de movimento por 8 h gera RISCO;
- falta de dados de uma fonte gera AVISO; de duas fontes, RISCO;
- o ESP32 envia sinal de vida a cada 5 min;
- uma regra de sono gera aviso no resumo da manhã.

**Architecture:**
- **Status AVISO:** o enum de status ganha `AVISO`, o nível mais baixo de alerta. Ele não entra na escada de escalonamento: vira uma mensagem informativa ao primeiro contato familiar, sem repetição dentro do mesmo episódio.
- **Classificador:** `classificar_por_regra` passa a olhar a última comunicação de cada fonte. O ESP32 conta presença ou sinal de vida; a pulseira conta frequência cardíaca.
- **Remoção do atalho antigo:** o caso "sem dados", hoje um ATENÇÃO identificado por prefixo de texto, deixa de existir. A falta de dados vira AVISO ou RISCO pelas regras novas.
- **Regra de sono:** roda num job diário às 09:00, separado da verificação de 15 min.

**Issue:** #51

**Tech Stack:** Python 3, Pydantic, FastAPI, APScheduler, SQLite, pytest. Firmware Arduino (ESP32).

**Spec:** a seção "8. Lógica de monitoramento" do Memorial Descritivo do kit. Os valores estão em `~/augusto-automacoes/empresa/modelos/conteudo/exemplo_zela.yaml`, chaves `memorial.regras`, `memorial.rede` e `memorial.limitacoes`. O documento gerado é `~/augusto-automacoes/empresa/saida/exemplos/pdf/AA-MD-2026-001-memorial-descritivo.pdf`.

Decisões confirmadas pelo usuário em 29/10/2026:
- status AVISO separado do ATENÇÃO;
- limites de 15 min para o ESP32 e 30 min para a pulseira;
- adicionar a regra de sono.

## Global Constraints

- Regras do memorial, nesta ordem de prioridade (vale a mais grave):
  1. **RISCO:** nenhum movimento em nenhum cômodo por **8 h** ou mais, com o ESP32 enviando sinal de vida.
  2. **RISCO:** ESP32 sem comunicação há **15 min** E pulseira sem leitura há **30 min**.
  3. **ATENÇÃO:** frequência cardíaca fora da faixa plausível (30–220 bpm).
  4. **AVISO:** só uma das fontes sem dados (ESP32 há 15 min OU pulseira há 30 min).
  5. **NORMAL:** nenhuma das condições acima.
- **Sono:** a noite anterior com duração **30%** menor ou maior que a média das **14** noites anteriores, exigindo pelo menos **7** noites de histórico, gera **AVISO**. É enviado uma vez por dia, às **09:00**.
- **Sinal de vida do ESP32:** a cada **5 min**, mesmo sem movimento.
- **AVISO** nunca entra em `aplicar_escalonamento`. Vai como `Alerta(nivel=NivelAlerta.INFO)` para `perfil.contatos_familiares[0]`, uma vez por episódio.
- Commits em PT-BR, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Fluxo do repositório: issue → branch → TDD → suíte completa → PR → squash → deploy na VPS → health check.
- `RELATORIO.docx` continua fora do git.
- Nunca citar o IP da VPS. Usar só o domínio `augustoautomacoes.com`.

## Review Focus

1. **Fusos horários misturados.** O Health Connect manda timestamps com fuso (`-03:00`); o ESP32 e o `datetime.now()` não têm fuso. Comparar os dois gera `TypeError`. Toda comparação de tempo no classificador e na regra de sono passa pelo helper `_hora_local()`, que converte para horário local sem fuso. Os testes da Task 3 e da Task 4 misturam os dois formatos.
2. **Sessões de sono duplicadas.** Cada sincronização do HC Webhook reenvia sessões já recebidas, e a ingestão só faz `INSERT`. Somar sem remover duplicatas dobraria o sono. Por isso, desduplicar por `timestamp` de fim de sessão (teste na Task 4).
3. **Primeira instalação sem nenhum dado.** Sem leitura nenhuma, as duas fontes contam como silenciosas e o resultado é RISCO, em vez do NORMAL de antes. O teste antigo `test_classifica_normal_sem_leituras` muda de expectativa. A escada de escalonamento começa perguntando à própria idosa ("Tudo bem?"), o que é aceitável. Registrar isso na PR.
4. **AVISO repetido a cada 15 min.** Sem desduplicação, o scheduler mandaria a mesma mensagem 4 vezes por hora. A chave de desduplicação é `(id_idoso, motivo)` e é limpa quando o status volta a NORMAL (teste na Task 5).
5. **Sinal de vida contado como movimento.** Se o sinal de vida virasse leitura de PRESENCA, zeraria o contador de 8 h e esconderia um RISCO real. Ele é um tipo próprio, `SINAL_DE_VIDA`, e o contador usa só PRESENCA (teste na Task 3).

---

### Task 1: Modelo — status AVISO e leitura de sinal de vida

**Files:**
- Modify: `zela/models/monitoramento.py`
- Test: `tests/test_models_monitoramento.py`

**Interfaces:**
- Produces:
  - `StatusMonitoramento.AVISO = "aviso"`;
  - `TipoLeitura.SINAL_DE_VIDA = "sinal_de_vida"`, com `FAIXAS_PLAUSIVEIS[TipoLeitura.SINAL_DE_VIDA] = (1, 1)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_status_aviso_existe():
    assert StatusMonitoramento("aviso") is StatusMonitoramento.AVISO

def test_leitura_sinal_de_vida_plausivel():
    leitura = LeituraSensor(fonte=FonteSensor.ESP32, tipo=TipoLeitura.SINAL_DE_VIDA,
                            valor=1, unidade="sinal", timestamp=datetime(2026, 10, 29, 10, 0))
    assert leitura.plausivel
```

- [ ] **Step 2:** Rodar `pytest tests/test_models_monitoramento.py -v`. Esperado: FAIL com `ValueError: 'aviso' is not a valid StatusMonitoramento`.
- [ ] **Step 3:** Adicionar os dois membros dos enums e a faixa plausível.
- [ ] **Step 4:** Rodar o mesmo comando. Esperado: PASS.
- [ ] **Step 5: Commit** — `feat: status AVISO e leitura de sinal de vida do ESP32`

### Task 2: Ingestão — `/ingest/esp32` aceita sinal de vida

**Files:**
- Modify: `zela/api/ingestao.py` (`receber_esp32`)
- Test: `tests/test_api_ingestao.py`

**Interfaces:**
- Consumes: `TipoLeitura.SINAL_DE_VIDA` (Task 1).
- Produces: o corpo `{"tipo": "sinal_de_vida", "valor": 1, "timestamp": "..."}` grava uma leitura `SINAL_DE_VIDA` com `unidade="sinal"`. Sem a chave `tipo`, ou com `"tipo": "presenca"`, o comportamento atual continua igual. Qualquer outro `tipo` → 400.

- [ ] **Step 1: Write the failing tests**
  - `test_esp32_sinal_de_vida_grava_tipo_proprio`: a leitura salva tem `tipo == TipoLeitura.SINAL_DE_VIDA`.
  - `test_esp32_sem_tipo_continua_presenca`: o corpo antigo, sem `tipo`, grava `PRESENCA`.
  - `test_esp32_tipo_desconhecido_retorna_400`: `"tipo": "temperatura"` → status 400.
- [ ] **Step 2:** Rodar `pytest tests/test_api_ingestao.py -v`. Esperado: os 3 testes novos falham, porque hoje o sinal de vida é gravado como PRESENCA.
- [ ] **Step 3:** Em `receber_esp32`, mapear `corpo.get("tipo", "presenca")` por um dicionário `{"presenca": (TipoLeitura.PRESENCA, "deteccao"), "sinal_de_vida": (TipoLeitura.SINAL_DE_VIDA, "sinal")}`. Uma chave ausente levanta `ValueError`, que já vira 400.
- [ ] **Step 4:** Rodar o mesmo comando. Esperado: PASS.
- [ ] **Step 5: Commit** — `feat: ingestão do sinal de vida do ESP32`

### Task 3: Domínio — classificador com 8 h e falta de dados por fonte

**Files:**
- Modify: `zela/domain/monitoramento.py`
- Test: `tests/test_domain_monitoramento.py` e `tests/test_agents_orchestrator_tools_monitoramento.py` (ajustar as referências a 6 h)

**Interfaces:**
- Consumes: Task 1.
- Produces:

```python
LIMITE_HORAS_SEM_PRESENCA = 8.0
LIMITE_MINUTOS_ESP32 = 15
LIMITE_MINUTOS_PULSEIRA = 30
MOTIVO_ESP32_SEM_SINAL = "O ESP32 da casa parou de enviar sinal"
MOTIVO_PULSEIRA_SEM_DADOS = "A pulseira parou de enviar leituras (pode ter sido retirada)"
MOTIVO_SEM_NENHUMA_FONTE = "ESP32 e pulseira pararam de enviar dados ao mesmo tempo"

def _hora_local(ts: datetime) -> datetime: ...
    # aware → converte para America/Sao_Paulo e remove tzinfo; naive → devolve igual

def classificar_por_regra(
    leituras: list[LeituraSensor],
    agora: datetime,
    limite_horas_sem_presenca: float = LIMITE_HORAS_SEM_PRESENCA,
    limite_minutos_esp32: float = LIMITE_MINUTOS_ESP32,
    limite_minutos_pulseira: float = LIMITE_MINUTOS_PULSEIRA,
) -> EventoMonitoramento: ...
```

As mensagens de AVISO são fixas, sem números, porque o texto é a chave de desduplicação da Task 5.

**Definições:**
- **ESP32 vivo:** a última leitura com `fonte == ESP32`, de qualquer tipo, tem até 15 min.
- **Pulseira viva:** a última leitura de `FREQUENCIA_CARDIACA` tem até 30 min.
- **Sem movimento:** a última leitura de `PRESENCA` tem 8 h ou mais. `SINAL_DE_VIDA` não conta como movimento.

Prioridade: RISCO > ATENÇÃO > AVISO > NORMAL.

- [ ] **Step 1: Write the failing tests.** `agora = datetime(2026, 10, 29, 14, 0)`; helpers `esp(min_atras, tipo)` e `fc(min_atras, bpm, aware=False)`.

| Teste | Leituras | Esperado |
|---|---|---|
| `test_risco_8h_sem_movimento_com_esp32_vivo` | presença há 8 h, sinal de vida há 2 min, FC há 5 min | RISCO, "8.0h" no motivo |
| `test_normal_7h_sem_movimento` | presença há 7 h, sinal de vida há 2 min, FC há 5 min | NORMAL |
| `test_sinal_de_vida_nao_conta_como_movimento` | presença há 9 h, sinal de vida há 1 min, FC há 5 min | RISCO |
| `test_risco_quando_as_duas_fontes_param` | sinal de vida há 20 min, FC há 40 min | RISCO, `motivo == MOTIVO_SEM_NENHUMA_FONTE` |
| `test_aviso_so_esp32_parado` | sinal de vida há 20 min, FC há 5 min | AVISO, `motivo == MOTIVO_ESP32_SEM_SINAL` |
| `test_aviso_so_pulseira_parada` | presença há 1 h, sinal de vida há 2 min, FC há 40 min | AVISO, `motivo == MOTIVO_PULSEIRA_SEM_DADOS` |
| `test_atencao_vence_aviso` | FC de 250 bpm há 1 min, sinal de vida há 20 min | ATENÇÃO |
| `test_sem_nenhuma_leitura_e_risco` | `[]` | RISCO (substitui `test_classifica_normal_sem_leituras`) |
| `test_mistura_timestamp_com_fuso_sem_erro` | FC com `-03:00` há 5 min, sinal de vida naive há 2 min, presença há 1 h | NORMAL, sem `TypeError` |

- [ ] **Step 2:** Rodar `pytest tests/test_domain_monitoramento.py -v`. Esperado: os testes novos falham (o limite atual é 6 h e não existe AVISO).
- [ ] **Step 3:** Implementar as regras na ordem de prioridade dos Global Constraints, usando `_hora_local` em toda comparação.
- [ ] **Step 4:** Rodar o mesmo comando e também `pytest tests/test_agents_orchestrator_tools_monitoramento.py tests/test_streamlit_secoes.py -v`. Ajustar as fixtures que assumem 6 h. Esperado: PASS.
- [ ] **Step 5: Commit** — `feat: regras de 8 h e de falta de dados por fonte no classificador`

### Task 4: Domínio — regra de sono

**Files:**
- Create: `zela/domain/sono.py`
- Test: `tests/test_domain_sono.py`

**Interfaces:**
- Consumes: `_hora_local` (Task 3) e `StatusMonitoramento.AVISO` (Task 1).
- Produces:

```python
DESVIO_SONO = 0.30
NOITES_BASE = 14
MIN_NOITES_HISTORICO = 7

def avaliar_sono(leituras_sono: list[LeituraSensor], agora: datetime) -> EventoMonitoramento | None: ...
```

**Regras:**
- A noite de uma data D é a soma das sessões únicas, desduplicadas por timestamp, que terminam em D, em horário local.
- "Noite anterior" é a data de `agora`. A base é a média das até 14 datas anteriores que têm registro.
- Devolve AVISO com motivo `"Sono da noite fora do habitual: Xh (média Yh)"` quando `|noite − média| / média >= 0.30`. Caso contrário, devolve `None`.
- Também devolve `None` se a noite não tem registro ou se há menos de 7 noites de histórico.

- [ ] **Step 1: Write the failing tests**
  - `test_noite_30pct_mais_curta_gera_aviso`: 14 noites de 7 h e hoje 4,9 h → AVISO.
  - `test_noite_dentro_da_faixa_nao_avisa`: 14 noites de 7 h e hoje 6 h → `None`.
  - `test_noite_muito_longa_gera_aviso`: hoje 9,1 h → AVISO.
  - `test_menos_de_7_noites_nao_avisa`: 6 noites de histórico → `None`.
  - `test_sessoes_duplicadas_nao_somam_duas_vezes`: mesma sessão de 7 h enviada 2 vezes → `None`, e não "14 h".
  - `test_cochilo_soma_na_noite`: sessão de 6 h + cochilo de 1 h no mesmo dia, com média 7 h → `None`.
- [ ] **Step 2:** Rodar `pytest tests/test_domain_sono.py -v`. Esperado: FAIL com `ModuleNotFoundError: zela.domain.sono`.
- [ ] **Step 3:** Implementar `avaliar_sono`.
- [ ] **Step 4:** Rodar o mesmo comando. Esperado: PASS.
- [ ] **Step 5: Commit** — `feat: regra de sono comparada à média pessoal de 14 noites`

### Task 5: Storage e scheduler — AVISO sem escalonamento e job diário de sono

**Files:**
- Modify: `zela/storage/monitoramento.py`, `zela/api/scheduler.py`
- Test: `tests/test_storage_monitoramento.py` e `tests/test_api_scheduler.py`

**Interfaces:**
- Consumes: Tasks 3 e 4.
- Produces:
  - `aplicar_classificacao(conn, idoso_id, agora, janela_horas=48.0)` passa a ser só `classificar_por_regra(leituras, agora)`. Removem-se o caso "sem dados" e `MOTIVO_SEM_DADOS_PREFIXO`.
  - `avaliar_sono_recente(conn, idoso_id, agora) -> EventoMonitoramento | None`: carrega 15 dias de leituras `SONO`.
  - `verificar_e_escalonar_riscos(...)`, com o status AVISO tratado à parte.
  - `verificar_sono_e_avisar(caminho_db, id_idoso, waha_client) -> list[Alerta]`.
  - Em `iniciar_scheduler`, o job `"verificar_sono"` com `"cron", hour=9, minute=0`.
  - `_avisos_ja_enviados: set[tuple[str, str]]`, em memória, como `_lembretes_ja_enviados`.

- [ ] **Step 1: Write the failing tests**
  - `test_aviso_envia_info_ao_primeiro_familiar_sem_escalonar`: o status AVISO grava um `Alerta(nivel=INFO)`, envia ao `contatos_familiares[0]` e não chama `aplicar_escalonamento` (usar monkeypatch para falhar se for chamado).
  - `test_aviso_nao_repete_no_mesmo_episodio`: duas execuções seguidas com o mesmo AVISO → `enviar_texto` chamado 1 vez.
  - `test_aviso_volta_a_avisar_apos_normalizar`: AVISO → NORMAL → AVISO → 2 envios.
  - `test_verificar_sono_envia_aviso_uma_vez_por_dia`: duas chamadas no mesmo dia → 1 envio.
  - `test_iniciar_scheduler_registra_job_de_sono`: `agendador.get_job("verificar_sono")` não é `None`.
  - Substituir `test_verificar_e_escalonar_riscos_sem_dados_envia_info_e_nao_escalona` pelo teste de AVISO acima.
- [ ] **Step 2:** Rodar `pytest tests/test_api_scheduler.py tests/test_storage_monitoramento.py -v`. Esperado: os testes novos falham.
- [ ] **Step 3:** Implementar. A chave de desduplicação é `(id_idoso, evento.motivo)`. Com o status NORMAL, remover as chaves daquele idoso. A desduplicação do sono usa a chave `(id_idoso, f"sono:{agora.date()}")`.
- [ ] **Step 4:** Rodar o mesmo comando. Esperado: PASS.
- [ ] **Step 5: Commit** — `feat: AVISO sem escalonamento e resumo diário de sono`

### Task 6: Firmware — sinal de vida a cada 5 min

**Files:**
- Modify: `firmware/zela_presenca/zela_presenca.ino`, `docs/hardware/automacao_esp32.md`

**Interfaces:**
- Consumes: o contrato da Task 2.
- Produces:
  - `const unsigned long INTERVALO_SINAL_DE_VIDA_MS = 300000UL;`
  - `bool enviarSinalDeVida()`, que manda `{"tipo": "sinal_de_vida", "valor": 1, "timestamp": "<ISO local>"}`.
  - O envio acontece no `loop()` quando `millis() - ultimoSinalDeVidaMs >= INTERVALO_SINAL_DE_VIDA_MS`, inclusive durante o aquecimento dos sensores.

Firmware não tem teste automatizado, então a verificação é manual.

- [ ] **Step 1:** Implementar. Reaproveitar a montagem de HTTP de `enviarLeitura` num helper `bool postarJson(const String& corpo)`.
- [ ] **Step 2:** Compilar com `arduino-cli compile --fqbn esp32:esp32:esp32 firmware/zela_presenca`. Esperado: sem erros.
- [ ] **Step 3:** Gravar na placa e acompanhar o monitor serial por 11 min. Esperado: pelo menos 2 linhas `POST /ingest/esp32 -> 200` sem movimento na frente dos sensores. No banco, ao menos 2 leituras `sinal_de_vida`.
- [ ] **Step 4:** Atualizar `docs/hardware/automacao_esp32.md`: o sinal de vida, o limite de 8 h no lugar de 6 h, e a recomendação de cabo Cat5e com pinagem (par laranja = OUT + GND, par azul = VCC + GND).
- [ ] **Step 5: Commit** — `feat(firmware): sinal de vida a cada 5 minutos`

### Task 7: Painel, agente e documentação

**Files:**
- Modify:
  - `zela/streamlit_app/estilo.py`: badge `.zela-badge-aviso`, em cor neutra e informativa, distinta do âmbar do ATENÇÃO;
  - `zela/streamlit_app/secoes.py`;
  - as docstrings e descriptions em `zela/agents/orchestrator.py` que listam "normal, atenção ou risco";
  - `README.md`: seção de monitoramento.
- Test: `tests/test_streamlit_secoes.py`, `tests/test_streamlit_estilo.py` e `tests/test_agents_orchestrator_tools.py`

- [ ] **Step 1: Write the failing tests**
  - O status AVISO aparece como `"AVISO"` no card de status.
  - A description da ferramenta de status do agente contém `"aviso"`.
- [ ] **Step 2:** Rodar `pytest tests/test_streamlit_secoes.py tests/test_streamlit_estilo.py tests/test_agents_orchestrator_tools.py -v`. Esperado: FAIL.
- [ ] **Step 3:** Implementar e atualizar o README.
- [ ] **Step 4:** Rodar `pytest`, a suíte completa. Esperado: tudo verde, com a contagem atualizada.
- [ ] **Step 5: Commit** — `docs: status AVISO no painel, no agente e no README`

### Task 8: PR, deploy e gravação do firmware

- [ ] Abrir a PR com `Closes #51`, citando na descrição o item 3 do Review Focus (primeira instalação sem dados gera RISCO).
- [ ] Squash merge e deploy na VPS, com health check em `https://augustoautomacoes.com`.
- [ ] **Ordem obrigatória: primeiro o backend, depois o firmware.**
  - O backend antigo gravaria o sinal de vida como PRESENCA e zeraria o contador de 8 h.
  - Já o backend novo, enquanto o firmware antigo ainda roda, só gera um AVISO "ESP32 parou de enviar sinal", que é inofensivo e enviado uma única vez.
- [ ] Gravar o firmware novo e confirmar no painel o status NORMAL em até 15 min.
- [ ] **Medir a latência real do HC Webhook.** Comparar o timestamp da última FC com a hora de chegada por 1 dia. Se a pulseira gerar AVISOs falsos, ajustar `LIMITE_MINUTOS_PULSEIRA` e atualizar o memorial do kit.
