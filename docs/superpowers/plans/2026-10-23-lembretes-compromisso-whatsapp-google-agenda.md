# Lembretes de Compromisso (WhatsApp + Google Agenda) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lembrete automático de `Compromisso` por WhatsApp (instantâneo, 24h, manhã, 1h antes, + cancelamento) e por Google Agenda (evento com 3 lembretes, entregue no pulso do idoso via espelhamento padrão de notificação do Android), tudo assíncrono via o scheduler que já existe no `backend`.

**Architecture:** Duas tabelas/colunas novas de bookkeeping (`google_event_id`, `google_sync_pendente`, `removido` em `compromisso`; nova tabela `lembrete_compromisso_enviado`) alimentam dois jobs novos no `BackgroundScheduler` existente (`zela/api/scheduler.py`): um dispara WhatsApp via `WahaClient` (já existente), outro sincroniza o evento via um novo `GoogleCalendarClient`. O `streamlit` nunca ganha credencial nem chamada de saída — só marca flags via `salvar_compromisso`/`remover_compromisso`.

**Tech Stack:** Python 3.11, FastAPI, APScheduler, SQLite, Pydantic, httpx, Streamlit (`streamlit.testing.v1.AppTest` para testes de UI), pytest.

**Decisão de implementação (diverge do design doc, dentro do que ele deixa a cargo do builder):** o doc de design (seção 5.2) sugeria `google-api-python-client` + `google-auth`. Este plano usa **httpx puro** contra a REST API do Google (token endpoint + Calendar v3), no mesmo espírito do `WahaClient` já existente — nenhuma dependência nova em `pyproject.toml`, e o mesmo padrão de teste (`monkeypatch.setattr(httpx, "post", ...)`) já usado em `tests/test_integrations_waha_client.py`.

**Spec:** `docs/superpowers/specs/2026-10-23-lembretes-compromisso-whatsapp-google-agenda-design.md`

## Global Constraints

- `INTERVALO_MINUTOS` do scheduler = 5 minutos (mesmo valor já usado pro lembrete de medicamento) — ambos os jobs novos usam o mesmo intervalo.
- Google Agenda recebe só **3** overrides (24h, manhã, 1h) — nunca um 4º override "instantâneo" (não existe esse conceito num evento de calendário).
- `HORARIO_LEMBRETE_MANHA` = `time(8, 0)`, constante no código — não é variável de ambiente nem campo editável no painel.
- Qualquer horário-alvo (24h/manhã/1h) já passado no momento do cálculo é descartado silenciosamente — nunca disparo retroativo (exceto o instantâneo, que sempre dispara uma vez).
- Credencial da Google Calendar API só existe como variável de ambiente no container `backend` (`ZELA_GOOGLE_CALENDAR_CLIENT_ID`, `_CLIENT_SECRET`, `_REFRESH_TOKEN`, `_CALENDAR_ID`) — o `streamlit` nunca recebe essas variáveis nem chama a API diretamente.
- Falha na Google Calendar API (qualquer operação) é logada e nunca bloqueia o salvamento do compromisso nem o envio do lembrete por WhatsApp — os dois canais são independentes.
- Estado de "lembrete já enviado" é persistido em tabela (`lembrete_compromisso_enviado`), nunca em memória de processo.
- `Medicamento` e armazenamento multi-tenant de credencial estão fora de escopo deste plano.

## Review Focus

- Compromisso criado a menos de 24h do evento → o lembrete de "24h antes" deve ser descartado silenciosamente, nunca disparado atrasado. (Task 2)
- Compromisso cujo horário é antes das 08:00 (ex.: consulta às 07:00) → o lembrete/override "manhã" não deve ser gerado (ficaria depois do próprio compromisso). (Task 2)
- Falha da Google Calendar API ao criar/atualizar/remover evento → não pode quebrar o job do scheduler nem impedir o lembrete por WhatsApp; `google_sync_pendente` deve continuar 1 pra tentar de novo no próximo tick. (Task 7)
- Edição do `data_hora` de um compromisso que já teve algum lembrete enviado → os lembretes cujo novo horário-alvo ainda está no futuro devem poder ser reenviados; os que já foram enviados e cujo novo horário já passou não devem reaparecer. (Task 3)
- Remoção de um compromisso que nunca teve `google_event_id` (nunca sincronizado) → o job de sincronização não pode tentar chamar `remover_evento` com id nulo. (Task 7)

---

## Task 1: Esquema de dados

**Files:**
- Modify: `zela/storage/db.py`
- Test: `tests/test_storage_db.py`

**Interfaces:**
- Produces: colunas `compromisso.google_event_id` (`TEXT`, nullable), `compromisso.google_sync_pendente` (`INTEGER NOT NULL DEFAULT 1`), `compromisso.removido` (`INTEGER NOT NULL DEFAULT 0`); tabela `lembrete_compromisso_enviado(id INTEGER PRIMARY KEY, compromisso_id TEXT NOT NULL, tipo_lembrete TEXT NOT NULL, enviado_em TEXT NOT NULL, UNIQUE(compromisso_id, tipo_lembrete))`.

Essas três colunas são bookkeeping de sincronização, não entram no modelo Pydantic `Compromisso` (igual `ConfirmacaoMedicacao` já é um model separado de `Medicamento`).

- [ ] **Step 1: Escrever o teste de migração (banco com schema antigo)**

Em `tests/test_storage_db.py`, seguindo o padrão de `test_conectar_migra_coluna_bula_em_banco_com_schema_antigo`:

```python
def test_conectar_migra_colunas_de_sync_em_banco_com_schema_antigo(tmp_path):
    import sqlite3

    caminho = str(tmp_path / "banco_antigo_compromisso.db")
    conn_antiga = sqlite3.connect(caminho)
    conn_antiga.execute(
        """
        CREATE TABLE compromisso (
            id TEXT PRIMARY KEY,
            idoso_id TEXT NOT NULL,
            titulo TEXT NOT NULL,
            data_hora TEXT NOT NULL,
            local TEXT NOT NULL,
            tipo TEXT NOT NULL
        )
        """
    )
    conn_antiga.commit()
    conn_antiga.close()

    conn = conectar(caminho)

    colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(compromisso)")}
    assert {"google_event_id", "google_sync_pendente", "removido"} <= colunas
```

Também atualizar `test_conectar_cria_todas_as_tabelas` para incluir `"lembrete_compromisso_enviado"` no set esperado.

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_storage_db.py -v`
Expected: FAIL (coluna/tabela não existem ainda)

- [ ] **Step 3: Implementar a migração em `zela/storage/db.py`**

Adicionar ao `ESQUEMA` a `CREATE TABLE IF NOT EXISTS lembrete_compromisso_enviado (...)` (schema exato acima). Adicionar `_migrar_colunas_compromisso(conn)` (mesmo padrão de `_migrar_coluna_bula`/`_migrar_coluna_lid_whatsapp`): verifica `PRAGMA table_info(compromisso)` e roda `ALTER TABLE compromisso ADD COLUMN ...` pra cada uma das 3 colunas que faltar, com os tipos/defaults exatos acima. Chamar essa função dentro de `conectar()`, junto das outras duas chamadas de migração.

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_storage_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add zela/storage/db.py tests/test_storage_db.py
git commit -m "feat: adiciona esquema de sincronizacao de lembretes de compromisso"
```

---

## Task 2: Domínio — cálculo dos horários de lembrete

**Files:**
- Create: `zela/domain/compromisso_lembretes.py`
- Test: `tests/test_domain_compromisso_lembretes.py`

**Interfaces:**
- Consumes: `zela.models.rotina.Compromisso` (campo `data_hora: datetime`); `zela.domain.rotina.JANELA_LEMBRETE` (`timedelta(minutes=15)`, reaproveitado — não redefinir).
- Produces:
  - `HORARIO_LEMBRETE_MANHA: time` (valor `time(8, 0)`)
  - `class TipoLembreteCompromisso(str, Enum)` com membros `INSTANTANEO="instantaneo"`, `H24="24h"`, `MANHA="manha"`, `H1="1h"`, `CANCELAMENTO="cancelamento"`
  - `calcular_horarios_lembrete_compromisso(compromisso: Compromisso) -> dict[str, datetime]` — chaves são os `.value` de `H24`/`MANHA`/`H1` (nunca `INSTANTANEO`/`CANCELAMENTO`, que não têm horário-alvo fixo); só inclui a chave se o horário calculado for `< compromisso.data_hora`.
  - `lembretes_compromisso_pendentes(compromisso: Compromisso, agora: datetime, tipos_ja_enviados: set[str]) -> list[str]` — lista de `.value` de tipos pendentes agora.
  - `calcular_overrides_minutos_google(compromisso: Compromisso, agora: datetime) -> list[int]`

- [ ] **Step 1: Escrever os testes de `calcular_horarios_lembrete_compromisso`**

```python
from datetime import datetime, time

from zela.domain.compromisso_lembretes import calcular_horarios_lembrete_compromisso
from zela.models.rotina import Compromisso, TipoCompromisso


def _compromisso(data_hora):
    return Compromisso(
        id="c1", titulo="Consulta", data_hora=data_hora, local="Clínica", tipo=TipoCompromisso.CONSULTA
    )


def test_calcular_horarios_inclui_as_tres_chaves_quando_compromisso_e_de_tarde():
    compromisso = _compromisso(datetime(2026, 11, 10, 14, 0))
    horarios = calcular_horarios_lembrete_compromisso(compromisso)
    assert set(horarios) == {"24h", "manha", "1h"}
    assert horarios["24h"] == datetime(2026, 11, 9, 14, 0)
    assert horarios["manha"] == datetime(2026, 11, 10, 8, 0)
    assert horarios["1h"] == datetime(2026, 11, 10, 13, 0)


def test_calcular_horarios_exclui_manha_quando_compromisso_e_antes_das_8h():
    compromisso = _compromisso(datetime(2026, 11, 10, 7, 0))
    horarios = calcular_horarios_lembrete_compromisso(compromisso)
    assert set(horarios) == {"24h", "1h"}
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest tests/test_domain_compromisso_lembretes.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar `calcular_horarios_lembrete_compromisso`**

Em `zela/domain/compromisso_lembretes.py`, criar `HORARIO_LEMBRETE_MANHA`, `TipoLembreteCompromisso` e a função (usa `timedelta(hours=24)`/`timedelta(hours=1)` subtraídos de `compromisso.data_hora`, e `datetime.combine(compromisso.data_hora.date(), HORARIO_LEMBRETE_MANHA)` pra "manha").

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `pytest tests/test_domain_compromisso_lembretes.py -v`
Expected: PASS (os 2 testes acima)

- [ ] **Step 5: Escrever os testes de `lembretes_compromisso_pendentes`**

```python
def test_lembretes_pendentes_inclui_instantaneo_quando_nao_enviado():
    compromisso = _compromisso(datetime(2026, 11, 10, 14, 0))
    agora = datetime(2026, 11, 1, 9, 0)
    pendentes = lembretes_compromisso_pendentes(compromisso, agora, tipos_ja_enviados=set())
    assert "instantaneo" in pendentes


def test_lembretes_pendentes_nao_repete_instantaneo_ja_enviado():
    compromisso = _compromisso(datetime(2026, 11, 10, 14, 0))
    agora = datetime(2026, 11, 1, 9, 0)
    pendentes = lembretes_compromisso_pendentes(compromisso, agora, tipos_ja_enviados={"instantaneo"})
    assert "instantaneo" not in pendentes


def test_lembretes_pendentes_detecta_1h_antes_dentro_da_janela():
    agora = datetime(2026, 11, 10, 12, 55)
    compromisso = _compromisso(datetime(2026, 11, 10, 14, 0))  # 1h antes = 13:00, fora da janela ainda
    # ajuste: usar compromisso às 13:55 -> 1h antes = 12:55 (== agora)
    compromisso = _compromisso(datetime(2026, 11, 10, 13, 55))
    pendentes = lembretes_compromisso_pendentes(compromisso, agora, tipos_ja_enviados={"instantaneo"})
    assert pendentes == ["1h"]


def test_lembretes_pendentes_ignora_tipo_ja_enviado_mesmo_na_janela():
    agora = datetime(2026, 11, 10, 12, 55)
    compromisso = _compromisso(datetime(2026, 11, 10, 13, 55))
    pendentes = lembretes_compromisso_pendentes(
        compromisso, agora, tipos_ja_enviados={"instantaneo", "1h"}
    )
    assert pendentes == []


def test_lembretes_pendentes_descarta_24h_quando_criado_a_menos_de_24h_do_evento():
    agora = datetime(2026, 11, 10, 4, 0)
    compromisso = _compromisso(datetime(2026, 11, 10, 14, 0))  # 24h antes = dia 9, 14h — já passou
    pendentes = lembretes_compromisso_pendentes(
        compromisso, agora, tipos_ja_enviados={"instantaneo"}
    )
    assert "24h" not in pendentes
```

- [ ] **Step 6: Rodar e confirmar falha, depois implementar**

Run: `pytest tests/test_domain_compromisso_lembretes.py -v` → FAIL
Implementar `lembretes_compromisso_pendentes`: sempre inclui `"instantaneo"` se não estiver em `tipos_ja_enviados` (sem checar janela); para cada `(tipo, horario_alvo)` de `calcular_horarios_lembrete_compromisso`, inclui se `tipo not in tipos_ja_enviados` e `horario_alvo <= agora <= horario_alvo + JANELA_LEMBRETE`.
Run novamente: PASS

- [ ] **Step 7: Escrever os testes de `calcular_overrides_minutos_google`**

```python
def test_calcular_overrides_minutos_google_calcula_minutos_relativos():
    agora = datetime(2026, 11, 1, 10, 0)
    compromisso = _compromisso(datetime(2026, 11, 3, 14, 0))
    minutos = calcular_overrides_minutos_google(compromisso, agora)
    assert sorted(minutos) == [60, 360, 1440]


def test_calcular_overrides_minutos_google_exclui_horarios_ja_passados():
    compromisso = _compromisso(datetime(2026, 11, 10, 14, 0))
    agora = compromisso.data_hora - timedelta(minutes=30)  # depois de 24h, manha e 1h antes
    minutos = calcular_overrides_minutos_google(compromisso, agora)
    assert minutos == []
```

- [ ] **Step 8: Rodar e confirmar falha, depois implementar**

Run: `pytest tests/test_domain_compromisso_lembretes.py -v` → FAIL
Implementar `calcular_overrides_minutos_google`: para cada `horario_alvo` em `calcular_horarios_lembrete_compromisso(compromisso).values()`, se `horario_alvo > agora`, calcula `int((compromisso.data_hora - horario_alvo).total_seconds() // 60)` e adiciona à lista.
Run novamente: PASS

- [ ] **Step 9: Commit**

```bash
git add zela/domain/compromisso_lembretes.py tests/test_domain_compromisso_lembretes.py
git commit -m "feat: calcula horarios e overrides de lembrete de compromisso"
```

---

## Task 3: Storage — remoção, rastreamento de lembretes e fila de sync

**Files:**
- Modify: `zela/storage/rotina.py`
- Test: `tests/test_storage_rotina.py`

**Interfaces:**
- Consumes: `zela.domain.compromisso_lembretes.calcular_horarios_lembrete_compromisso` (Task 2).
- Produces:
  - `salvar_compromisso(conn, compromisso, idoso_id)` — comportamento estendido (ver Step 3).
  - `listar_compromissos(conn, idoso_id) -> list[Compromisso]` — agora filtra `removido = 0`.
  - `remover_compromisso(conn, compromisso_id: str, idoso_id: str) -> None`
  - `listar_tipos_lembrete_enviados(conn, compromisso_id: str) -> set[str]`
  - `registrar_lembrete_compromisso_enviado(conn, compromisso_id: str, tipo_lembrete: str, enviado_em: datetime) -> None`
  - `listar_compromissos_removidos_pendentes_cancelamento(conn, idoso_id: str) -> list[Compromisso]`
  - `@dataclass class CompromissoPendenteSync: compromisso: Compromisso; google_event_id: str | None; removido: bool`
  - `listar_compromissos_pendentes_sync_google(conn, idoso_id: str) -> list[CompromissoPendenteSync]`
  - `marcar_google_sync_feito(conn, compromisso_id: str, google_event_id: str | None = None) -> None`

- [ ] **Step 1: Escrever o teste de `remover_compromisso`**

```python
def test_remover_compromisso_oculta_da_listagem_mas_mantem_a_linha():
    conn = conectar(":memory:")
    salvar_compromisso(
        conn,
        Compromisso(
            id="comp-1", titulo="Exame", data_hora=datetime.now() + timedelta(days=1),
            local="Lab", tipo=TipoCompromisso.EXAME,
        ),
        idoso_id="idosa-1",
    )

    remover_compromisso(conn, "comp-1", idoso_id="idosa-1")

    assert listar_compromissos(conn, "idosa-1") == []
    linha = conn.execute("SELECT removido, google_sync_pendente FROM compromisso WHERE id = ?", ("comp-1",)).fetchone()
    assert linha["removido"] == 1
    assert linha["google_sync_pendente"] == 1
```

- [ ] **Step 2: Rodar (falha), implementar `remover_compromisso`, rodar de novo (passa)**

Run: `pytest tests/test_storage_rotina.py::test_remover_compromisso_oculta_da_listagem_mas_mantem_a_linha -v`
Implementar `remover_compromisso`: `UPDATE compromisso SET removido = 1, google_sync_pendente = 1 WHERE id = ? AND idoso_id = ?`, seguido de `conn.commit()`. Modificar `listar_compromissos` pra adicionar `AND removido = 0` na cláusula `WHERE`.
Expected final: PASS

- [ ] **Step 3: Escrever o teste de `salvar_compromisso` marcando sync pendente + limpando lembretes recalculáveis**

```python
def test_salvar_compromisso_marca_sync_pendente_por_padrao():
    conn = conectar(":memory:")
    salvar_compromisso(
        conn,
        Compromisso(
            id="comp-1", titulo="Exame", data_hora=datetime.now() + timedelta(days=2),
            local="Lab", tipo=TipoCompromisso.EXAME,
        ),
        idoso_id="idosa-1",
    )
    linha = conn.execute("SELECT google_sync_pendente FROM compromisso WHERE id = ?", ("comp-1",)).fetchone()
    assert linha["google_sync_pendente"] == 1


def test_editar_data_hora_limpa_lembretes_cujo_novo_horario_ainda_esta_no_futuro():
    conn = conectar(":memory:")
    data_hora_original = datetime.now() + timedelta(hours=2)
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=data_hora_original, local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )
    # simula que o lembrete "instantaneo" e "1h" já foram enviados com o horário antigo
    registrar_lembrete_compromisso_enviado(conn, "comp-1", "instantaneo", datetime.now())
    registrar_lembrete_compromisso_enviado(conn, "comp-1", "1h", datetime.now())

    nova_data_hora = datetime.now() + timedelta(days=3)  # bem mais no futuro
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=nova_data_hora, local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )

    tipos_restantes = listar_tipos_lembrete_enviados(conn, "comp-1")
    # "1h" tinha horário-alvo recalculado (nova_data_hora - 1h) ainda no futuro -> deve ter sido limpo
    assert "1h" not in tipos_restantes
    # "instantaneo" não tem horário-alvo (sempre considerado "no passado"/já disparado) -> não é limpo
    assert "instantaneo" in tipos_restantes
```

- [ ] **Step 4: Rodar (falha), implementar, rodar de novo (passa)**

Implementar em `zela/storage/rotina.py`:
- `listar_tipos_lembrete_enviados(conn, compromisso_id)`: `SELECT tipo_lembrete FROM lembrete_compromisso_enviado WHERE compromisso_id = ?`, retorna `set`.
- `registrar_lembrete_compromisso_enviado(conn, compromisso_id, tipo_lembrete, enviado_em)`: `INSERT OR IGNORE INTO lembrete_compromisso_enviado (compromisso_id, tipo_lembrete, enviado_em) VALUES (?, ?, ?)`, commit.
- Modificar `salvar_compromisso`: adicionar `google_sync_pendente` à lista de colunas do `INSERT`/`ON CONFLICT DO UPDATE SET` (valor sempre `1`; não tocar `google_event_id`/`removido` no `UPDATE SET`). Depois do `INSERT`, para cada `(tipo, horario_alvo)` em `calcular_horarios_lembrete_compromisso(compromisso).items()`: se `horario_alvo > datetime.now()`, `DELETE FROM lembrete_compromisso_enviado WHERE compromisso_id = ? AND tipo_lembrete = ?`. Commit ao final.

Run: `pytest tests/test_storage_rotina.py -v`
Expected: PASS (os 2 testes acima)

- [ ] **Step 5: Escrever o teste de `listar_compromissos_removidos_pendentes_cancelamento`**

```python
def test_listar_compromissos_removidos_pendentes_cancelamento_so_retorna_nao_notificados():
    conn = conectar(":memory:")
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime.now() + timedelta(days=1), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )
    remover_compromisso(conn, "comp-1", idoso_id="idosa-1")

    pendentes = listar_compromissos_removidos_pendentes_cancelamento(conn, "idosa-1")
    assert [c.id for c in pendentes] == ["comp-1"]

    registrar_lembrete_compromisso_enviado(conn, "comp-1", "cancelamento", datetime.now())

    assert listar_compromissos_removidos_pendentes_cancelamento(conn, "idosa-1") == []
```

- [ ] **Step 6: Rodar (falha), implementar, rodar de novo (passa)**

Implementar `listar_compromissos_removidos_pendentes_cancelamento(conn, idoso_id)`: `SELECT c.* FROM compromisso c WHERE c.idoso_id = ? AND c.removido = 1 AND NOT EXISTS (SELECT 1 FROM lembrete_compromisso_enviado l WHERE l.compromisso_id = c.id AND l.tipo_lembrete = 'cancelamento')`, mapeia com `_linha_para_compromisso`.

Run: `pytest tests/test_storage_rotina.py -v`
Expected: PASS

- [ ] **Step 7: Escrever o teste de `listar_compromissos_pendentes_sync_google` e `marcar_google_sync_feito`**

```python
def test_listar_compromissos_pendentes_sync_google_e_marcar_feito():
    conn = conectar(":memory:")
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime.now() + timedelta(days=1), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )

    pendentes = listar_compromissos_pendentes_sync_google(conn, "idosa-1")
    assert len(pendentes) == 1
    assert pendentes[0].compromisso.id == "comp-1"
    assert pendentes[0].google_event_id is None
    assert pendentes[0].removido is False

    marcar_google_sync_feito(conn, "comp-1", google_event_id="evt-abc")

    assert listar_compromissos_pendentes_sync_google(conn, "idosa-1") == []
    linha = conn.execute("SELECT google_event_id FROM compromisso WHERE id = ?", ("comp-1",)).fetchone()
    assert linha["google_event_id"] == "evt-abc"
```

- [ ] **Step 8: Rodar (falha), implementar, rodar de novo (passa)**

Implementar `CompromissoPendenteSync` (dataclass) e `listar_compromissos_pendentes_sync_google(conn, idoso_id)`: `SELECT * FROM compromisso WHERE idoso_id = ? AND google_sync_pendente = 1`, mapeando cada linha com `_linha_para_compromisso(linha)` + `linha["google_event_id"]` + `bool(linha["removido"])`.
Implementar `marcar_google_sync_feito(conn, compromisso_id, google_event_id=None)`: se `google_event_id is not None`, `UPDATE compromisso SET google_sync_pendente = 0, google_event_id = ? WHERE id = ?`; senão `UPDATE compromisso SET google_sync_pendente = 0 WHERE id = ?`. Commit.

Run: `pytest tests/test_storage_rotina.py -v`
Expected: PASS (toda a suíte do arquivo)

- [ ] **Step 9: Commit**

```bash
git add zela/storage/rotina.py tests/test_storage_rotina.py
git commit -m "feat: adiciona remocao, rastreamento de lembretes e fila de sync do google agenda"
```

---

## Task 4: Mensagens de lembrete de compromisso

**Files:**
- Modify: `zela/domain/comunicacao.py`
- Test: `tests/test_domain_comunicacao.py`

**Interfaces:**
- Consumes: `zela.domain.compromisso_lembretes.TipoLembreteCompromisso` (Task 2); `zela.models.rotina.Compromisso`.
- Produces: `formatar_lembrete_compromisso(compromisso: Compromisso, tipo_lembrete: str) -> str`

- [ ] **Step 1: Escrever os testes**

```python
from zela.domain.comunicacao import formatar_lembrete_compromisso
from zela.models.rotina import Compromisso, TipoCompromisso
from datetime import datetime


def _compromisso():
    return Compromisso(
        id="c1", titulo="Cardiologista", data_hora=datetime(2026, 11, 10, 14, 30),
        local="Clínica Central", tipo=TipoCompromisso.CONSULTA,
    )


def test_formatar_lembrete_compromisso_instantaneo_menciona_titulo_e_data():
    texto = formatar_lembrete_compromisso(_compromisso(), "instantaneo")
    assert "Cardiologista" in texto
    assert "Clínica Central" in texto


def test_formatar_lembrete_compromisso_cancelamento_avisa_que_foi_cancelado():
    texto = formatar_lembrete_compromisso(_compromisso(), "cancelamento")
    assert "cancelado" in texto.lower()
    assert "Cardiologista" in texto
```

(Os outros tipos — `24h`, `manha`, `1h` — não têm uma asserção fixa de texto no plano; o corpo da função decide a redação exata, contanto que sempre inclua título e local.)

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest tests/test_domain_comunicacao.py -v`
Expected: FAIL com `ImportError`

- [ ] **Step 3: Implementar `formatar_lembrete_compromisso`**

Uma função com um `match`/`if` sobre `tipo_lembrete` (usando os `.value` de `TipoLembreteCompromisso`), cada ramo formatando uma mensagem em PT-BR que sempre inclui `compromisso.titulo` e `compromisso.local`; o ramo `"cancelamento"` inclui a palavra "cancelado".

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `pytest tests/test_domain_comunicacao.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add zela/domain/comunicacao.py tests/test_domain_comunicacao.py
git commit -m "feat: formata mensagens de lembrete de compromisso"
```

---

## Task 5: Scheduler — job de lembretes WhatsApp de compromisso

**Files:**
- Modify: `zela/api/scheduler.py`
- Test: `tests/test_api_scheduler.py`

**Interfaces:**
- Consumes: `zela.domain.compromisso_lembretes.lembretes_compromisso_pendentes`, `TipoLembreteCompromisso` (Task 2); `zela.domain.comunicacao.formatar_lembrete_compromisso` (Task 4); `zela.storage.rotina.listar_compromissos`, `listar_tipos_lembrete_enviados`, `registrar_lembrete_compromisso_enviado`, `listar_compromissos_removidos_pendentes_cancelamento` (Task 3).
- Produces:
  - `_enviar_para_idoso_e_familia(waha_client, perfil: PerfilIdoso, texto: str) -> None`
  - `verificar_e_enviar_lembretes_compromisso(caminho_db: str, id_idoso: str, waha_client) -> list[str]`
  - `iniciar_scheduler` ganha um novo job `"verificar_lembretes_compromisso"` (mesmo `INTERVALO_MINUTOS`).

- [ ] **Step 1: Escrever o teste do caso "dois destinatários"**

Em `tests/test_api_scheduler.py`, reaproveitando `_perfil()`/`_WahaFalso` já existentes:

```python
def test_verificar_e_enviar_lembretes_compromisso_envia_para_idoso_e_familiares(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime(2026, 11, 10, 14, 0), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )

    class _DatetimeFixo:
        @staticmethod
        def now():
            return datetime(2026, 11, 1, 9, 0)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    waha_falso = _WahaFalso()
    enviadas = verificar_e_enviar_lembretes_compromisso(caminho_db, "idosa-1", waha_falso)

    assert len(enviadas) == 1
    telefones_notificados = {telefone for telefone, _ in waha_falso.enviados}
    assert telefones_notificados == {"+5511911111111", "+5511987654321"}


def test_verificar_e_enviar_lembretes_compromisso_nao_repete_instantaneo(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime(2026, 11, 10, 14, 0), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )

    class _DatetimeFixo:
        @staticmethod
        def now():
            return datetime(2026, 11, 1, 9, 0)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    waha_falso = _WahaFalso()
    verificar_e_enviar_lembretes_compromisso(caminho_db, "idosa-1", waha_falso)
    segunda_chamada = verificar_e_enviar_lembretes_compromisso(caminho_db, "idosa-1", waha_falso)

    assert segunda_chamada == []


def test_verificar_e_enviar_lembretes_compromisso_envia_cancelamento_apos_remocao(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime(2026, 11, 10, 14, 0), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )
    remover_compromisso(conn, "comp-1", idoso_id="idosa-1")

    class _DatetimeFixo:
        @staticmethod
        def now():
            return datetime(2026, 11, 1, 9, 0)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    waha_falso = _WahaFalso()
    enviadas = verificar_e_enviar_lembretes_compromisso(caminho_db, "idosa-1", waha_falso)

    assert any("cancelado" in texto.lower() for texto in enviadas)
```

(Imports novos no topo do arquivo de teste: `Compromisso`, `TipoCompromisso` de `zela.models.rotina`; `salvar_compromisso`, `remover_compromisso` de `zela.storage.rotina`; `verificar_e_enviar_lembretes_compromisso` de `zela.api.scheduler`.)

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest tests/test_api_scheduler.py -v`
Expected: FAIL com `ImportError`

- [ ] **Step 3: Implementar `_enviar_para_idoso_e_familia` e `verificar_e_enviar_lembretes_compromisso`**

`_enviar_para_idoso_e_familia(waha_client, perfil, texto)`: chama `waha_client.enviar_texto(perfil.lid_whatsapp or perfil.telefone, texto)`, depois `waha_client.enviar_texto(contato.telefone, texto)` pra cada `contato` em `perfil.contatos_familiares`.

`verificar_e_enviar_lembretes_compromisso(caminho_db, id_idoso, waha_client) -> list[str]`: abre conexão, busca `perfil` (retorna `[]` se `None`, igual aos outros jobs), `agora = datetime.now()`. Para cada `compromisso` em `listar_compromissos(conn, id_idoso)`: calcula `tipos_ja_enviados = listar_tipos_lembrete_enviados(conn, compromisso.id)`, para cada `tipo` em `lembretes_compromisso_pendentes(compromisso, agora, tipos_ja_enviados)`: formata com `formatar_lembrete_compromisso`, chama `_enviar_para_idoso_e_familia`, `registrar_lembrete_compromisso_enviado(conn, compromisso.id, tipo, agora)`, acumula o texto. Depois, para cada `compromisso` em `listar_compromissos_removidos_pendentes_cancelamento(conn, id_idoso)`: mesmo fluxo com `tipo="cancelamento"` (sem checar janela). Retorna a lista de textos enviados.

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `pytest tests/test_api_scheduler.py -v`
Expected: PASS

- [ ] **Step 5: Escrever o teste de wiring do `iniciar_scheduler`**

```python
def test_iniciar_scheduler_registra_job_de_lembretes_compromisso(tmp_path):
    caminho_db = str(tmp_path / "teste.db")
    conectar(caminho_db)
    agendador = iniciar_scheduler(caminho_db, "idosa-1", _WahaFalso())
    ids_dos_jobs = {job.id for job in agendador.get_jobs()}
    assert "verificar_lembretes_compromisso" in ids_dos_jobs
    agendador.shutdown()
```

- [ ] **Step 6: Rodar (falha), adicionar o job em `iniciar_scheduler`, rodar de novo (passa)**

Em `iniciar_scheduler`, adicionar um `agendador.add_job(verificar_e_enviar_lembretes_compromisso, "interval", minutes=INTERVALO_MINUTOS, args=[caminho_db, id_idoso, waha_client], id="verificar_lembretes_compromisso")`.

Run: `pytest tests/test_api_scheduler.py -v`
Expected: PASS (toda a suíte)

- [ ] **Step 7: Commit**

```bash
git add zela/api/scheduler.py tests/test_api_scheduler.py
git commit -m "feat: adiciona job de lembretes de compromisso por whatsapp"
```

---

## Task 6: Cliente de integração Google Calendar

**Files:**
- Create: `zela/integrations/google_calendar_client.py`
- Test: `tests/test_integrations_google_calendar_client.py`

**Interfaces:**
- Produces:
  - `class GoogleCalendarClient`: `__init__(self, client_id: str, client_secret: str, refresh_token: str, calendar_id: str)`
  - `TOKEN_URL = "https://oauth2.googleapis.com/token"` (atributo de classe)
  - `API_BASE = "https://www.googleapis.com/calendar/v3"` (atributo de classe)
  - `FUSO_HORARIO = "America/Sao_Paulo"` (atributo de classe)
  - `criar_evento(self, titulo: str, local: str, data_hora: datetime, overrides_minutos: list[int]) -> str` (retorna o `id` do evento criado)
  - `atualizar_evento(self, event_id: str, titulo: str, local: str, data_hora: datetime, overrides_minutos: list[int]) -> None`
  - `remover_evento(self, event_id: str) -> None` (tolera 404 — evento já removido — sem levantar erro)

- [ ] **Step 1: Escrever o teste de `criar_evento`**

```python
import httpx

from zela.integrations.google_calendar_client import GoogleCalendarClient


class _RespostaFalsa:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=self)

    def json(self):
        return self._json_data


def test_criar_evento_busca_token_e_envia_payload_correto(monkeypatch):
    from datetime import datetime

    chamadas = []

    def post_falso(url, data=None, json=None, headers=None, timeout=None):
        chamadas.append((url, data, json, headers))
        if url == GoogleCalendarClient.TOKEN_URL:
            return _RespostaFalsa({"access_token": "tok-123"})
        return _RespostaFalsa({"id": "evt-1"})

    monkeypatch.setattr(httpx, "post", post_falso)

    cliente = GoogleCalendarClient(
        client_id="cid", client_secret="csecret", refresh_token="rtok", calendar_id="fam@gmail.com"
    )
    event_id = cliente.criar_evento(
        titulo="Consulta", local="Clínica X",
        data_hora=datetime(2026, 11, 1, 9, 0), overrides_minutos=[1440, 60],
    )

    assert event_id == "evt-1"
    url_token, dados_token, _, _ = chamadas[0]
    assert url_token == GoogleCalendarClient.TOKEN_URL
    assert dados_token["refresh_token"] == "rtok"
    assert dados_token["grant_type"] == "refresh_token"

    url_evento, _, payload, headers = chamadas[1]
    assert url_evento == "https://www.googleapis.com/calendar/v3/calendars/fam@gmail.com/events"
    assert headers == {"Authorization": "Bearer tok-123"}
    assert payload["summary"] == "Consulta"
    assert payload["location"] == "Clínica X"
    assert payload["start"] == {"dateTime": "2026-11-01T09:00:00", "timeZone": "America/Sao_Paulo"}
    assert payload["reminders"] == {
        "useDefault": False,
        "overrides": [{"method": "popup", "minutes": 1440}, {"method": "popup", "minutes": 60}],
    }
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest tests/test_integrations_google_calendar_client.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar `GoogleCalendarClient.__init__`, `_access_token` e `criar_evento`**

`_access_token(self) -> str`: `httpx.post(self.TOKEN_URL, data={"client_id": ..., "client_secret": ..., "refresh_token": ..., "grant_type": "refresh_token"}, timeout=30)`, `raise_for_status()`, retorna `resposta.json()["access_token"]`.
`_payload_evento(self, titulo, local, data_hora, overrides_minutos) -> dict`: monta `summary`/`location`/`start`/`end` (fim = `data_hora + timedelta(hours=1)`, mesmo formato `{"dateTime": data_hora.isoformat(), "timeZone": self.FUSO_HORARIO}`) e `reminders` (exatamente como no teste).
`criar_evento`: busca token, `httpx.post(f"{self.API_BASE}/calendars/{self.calendar_id}/events", json=self._payload_evento(...), headers={"Authorization": f"Bearer {token}"}, timeout=30)`, `raise_for_status()`, retorna `resposta.json()["id"]`.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `pytest tests/test_integrations_google_calendar_client.py -v`
Expected: PASS

- [ ] **Step 5: Escrever os testes de `atualizar_evento` e `remover_evento`**

```python
def test_atualizar_evento_chama_put_no_id_correto(monkeypatch):
    from datetime import datetime

    chamadas_post, chamadas_put = [], []
    monkeypatch.setattr(httpx, "post", lambda url, **kw: (chamadas_post.append((url, kw)), _RespostaFalsa({"access_token": "tok-123"}))[1])

    def put_falso(url, json=None, headers=None, timeout=None):
        chamadas_put.append((url, json, headers))
        return _RespostaFalsa({})

    monkeypatch.setattr(httpx, "put", put_falso)

    cliente = GoogleCalendarClient(client_id="cid", client_secret="csecret", refresh_token="rtok", calendar_id="fam@gmail.com")
    cliente.atualizar_evento("evt-1", titulo="Consulta", local="Clínica X", data_hora=datetime(2026, 11, 1, 9, 0), overrides_minutos=[60])

    url, _, headers = chamadas_put[0]
    assert url == "https://www.googleapis.com/calendar/v3/calendars/fam@gmail.com/events/evt-1"
    assert headers == {"Authorization": "Bearer tok-123"}


def test_remover_evento_tolera_404(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _RespostaFalsa({"access_token": "tok-123"}))

    def delete_falso(url, headers=None, timeout=None):
        return _RespostaFalsa({}, status_code=404)

    monkeypatch.setattr(httpx, "delete", delete_falso)

    cliente = GoogleCalendarClient(client_id="cid", client_secret="csecret", refresh_token="rtok", calendar_id="fam@gmail.com")
    cliente.remover_evento("evt-ja-sumiu")  # não deve levantar
```

- [ ] **Step 6: Rodar (falha), implementar `atualizar_evento` e `remover_evento`, rodar de novo (passa)**

`atualizar_evento`: busca token, `httpx.put(f"{self.API_BASE}/calendars/{self.calendar_id}/events/{event_id}", json=self._payload_evento(...), headers=..., timeout=30)`, `raise_for_status()`.
`remover_evento`: busca token, `resposta = httpx.delete(f"{self.API_BASE}/calendars/{self.calendar_id}/events/{event_id}", headers=..., timeout=30)`; se `resposta.status_code != 404`, `resposta.raise_for_status()`.

Run: `pytest tests/test_integrations_google_calendar_client.py -v`
Expected: PASS (toda a suíte)

- [ ] **Step 7: Commit**

```bash
git add zela/integrations/google_calendar_client.py tests/test_integrations_google_calendar_client.py
git commit -m "feat: adiciona cliente de integracao com a google calendar api"
```

---

## Task 7: Scheduler — job de sincronização com Google Agenda + wiring

**Files:**
- Modify: `zela/api/scheduler.py`
- Modify: `zela/api/main.py`
- Modify: `docker-compose.yml`
- Test: `tests/test_api_scheduler.py`

**Interfaces:**
- Consumes: `zela.storage.rotina.listar_compromissos_pendentes_sync_google`, `marcar_google_sync_feito` (Task 3); `zela.domain.compromisso_lembretes.calcular_overrides_minutos_google` (Task 2); `zela.integrations.google_calendar_client.GoogleCalendarClient` (Task 6).
- Produces:
  - `sincronizar_compromissos_google_agenda(caminho_db: str, id_idoso: str, google_calendar_client) -> list[str]` (retorna ids dos compromissos sincronizados com sucesso)
  - `iniciar_scheduler(caminho_db, id_idoso, waha_client, google_calendar_client=None)` — registra o job `"sincronizar_compromissos_google_agenda"` só se `google_calendar_client is not None`.

- [ ] **Step 1: Escrever o teste de criação de evento novo**

```python
class _GoogleCalendarFalso:
    def __init__(self, falhar=False):
        self.criados = []
        self.atualizados = []
        self.removidos = []
        self._falhar = falhar

    def criar_evento(self, titulo, local, data_hora, overrides_minutos):
        if self._falhar:
            raise RuntimeError("falha simulada")
        self.criados.append((titulo, local, data_hora, overrides_minutos))
        return "evt-novo"

    def atualizar_evento(self, event_id, titulo, local, data_hora, overrides_minutos):
        self.atualizados.append((event_id, titulo, local, data_hora, overrides_minutos))

    def remover_evento(self, event_id):
        self.removidos.append(event_id)


def test_sincronizar_compromissos_cria_evento_novo_e_salva_o_id(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime(2026, 11, 10, 14, 0), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )

    class _DatetimeFixo:
        @staticmethod
        def now():
            return datetime(2026, 11, 1, 9, 0)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    google_falso = _GoogleCalendarFalso()
    sincronizados = sincronizar_compromissos_google_agenda(caminho_db, "idosa-1", google_falso)

    assert sincronizados == ["comp-1"]
    assert len(google_falso.criados) == 1
    pendentes = listar_compromissos_pendentes_sync_google(conn, "idosa-1")
    assert pendentes == []


def test_sincronizar_compromissos_atualiza_evento_existente(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime(2026, 11, 10, 14, 0), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )
    marcar_google_sync_feito(conn, "comp-1", google_event_id="evt-existente")
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime(2026, 11, 11, 14, 0), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )  # edição marca google_sync_pendente = 1 de novo

    class _DatetimeFixo:
        @staticmethod
        def now():
            return datetime(2026, 11, 1, 9, 0)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    google_falso = _GoogleCalendarFalso()
    sincronizar_compromissos_google_agenda(caminho_db, "idosa-1", google_falso)

    assert len(google_falso.atualizados) == 1
    assert google_falso.atualizados[0][0] == "evt-existente"


def test_sincronizar_compromissos_remove_evento_e_ignora_se_nunca_sincronizado(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime(2026, 11, 10, 14, 0), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )
    remover_compromisso(conn, "comp-1", idoso_id="idosa-1")  # nunca teve google_event_id

    class _DatetimeFixo:
        @staticmethod
        def now():
            return datetime(2026, 11, 1, 9, 0)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    google_falso = _GoogleCalendarFalso()
    sincronizados = sincronizar_compromissos_google_agenda(caminho_db, "idosa-1", google_falso)

    assert sincronizados == ["comp-1"]
    assert google_falso.removidos == []  # nunca tinha id -> não chama remover_evento


def test_sincronizar_compromissos_falha_na_api_mantem_pendente(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_compromisso(
        conn,
        Compromisso(id="comp-1", titulo="Exame", data_hora=datetime(2026, 11, 10, 14, 0), local="Lab", tipo=TipoCompromisso.EXAME),
        idoso_id="idosa-1",
    )

    class _DatetimeFixo:
        @staticmethod
        def now():
            return datetime(2026, 11, 1, 9, 0)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    google_falso = _GoogleCalendarFalso(falhar=True)
    sincronizados = sincronizar_compromissos_google_agenda(caminho_db, "idosa-1", google_falso)

    assert sincronizados == []  # não quebrou, mas também não marcou como sincronizado
    assert len(listar_compromissos_pendentes_sync_google(conn, "idosa-1")) == 1
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest tests/test_api_scheduler.py -v`
Expected: FAIL com `ImportError`

- [ ] **Step 3: Implementar `sincronizar_compromissos_google_agenda`**

```python
def sincronizar_compromissos_google_agenda(caminho_db, id_idoso, google_calendar_client) -> list[str]:
    conn = conectar(caminho_db)
    agora = datetime.now()
    sincronizados = []
    for pendente in listar_compromissos_pendentes_sync_google(conn, id_idoso):
        try:
            if pendente.removido:
                if pendente.google_event_id:
                    google_calendar_client.remover_evento(pendente.google_event_id)
                marcar_google_sync_feito(conn, pendente.compromisso.id)
            else:
                minutos = calcular_overrides_minutos_google(pendente.compromisso, agora)
                if pendente.google_event_id is None:
                    event_id = google_calendar_client.criar_evento(
                        pendente.compromisso.titulo, pendente.compromisso.local,
                        pendente.compromisso.data_hora, minutos,
                    )
                    marcar_google_sync_feito(conn, pendente.compromisso.id, google_event_id=event_id)
                else:
                    google_calendar_client.atualizar_evento(
                        pendente.google_event_id, pendente.compromisso.titulo,
                        pendente.compromisso.local, pendente.compromisso.data_hora, minutos,
                    )
                    marcar_google_sync_feito(conn, pendente.compromisso.id)
            sincronizados.append(pendente.compromisso.id)
        except Exception:
            logger.exception("Falha ao sincronizar compromisso %s com o Google Agenda", pendente.compromisso.id)
    return sincronizados
```

Adicionar `import logging` e `logger = logging.getLogger(__name__)` no topo de `zela/api/scheduler.py` (ainda não existe nesse arquivo).

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `pytest tests/test_api_scheduler.py -v`
Expected: PASS (os 4 testes acima)

- [ ] **Step 5: Escrever o teste de wiring condicional do job no `iniciar_scheduler`**

```python
def test_iniciar_scheduler_so_registra_job_de_google_agenda_quando_cliente_e_passado(tmp_path):
    caminho_db = str(tmp_path / "teste.db")
    conectar(caminho_db)

    sem_google = iniciar_scheduler(caminho_db, "idosa-1", _WahaFalso())
    assert "sincronizar_compromissos_google_agenda" not in {j.id for j in sem_google.get_jobs()}
    sem_google.shutdown()

    com_google = iniciar_scheduler(caminho_db, "idosa-1", _WahaFalso(), google_calendar_client=_GoogleCalendarFalso())
    assert "sincronizar_compromissos_google_agenda" in {j.id for j in com_google.get_jobs()}
    com_google.shutdown()
```

- [ ] **Step 6: Rodar (falha), implementar o wiring, rodar de novo (passa)**

Modificar a assinatura de `iniciar_scheduler` pra `(caminho_db, id_idoso, waha_client, google_calendar_client=None)`. Se `google_calendar_client is not None`, `agendador.add_job(sincronizar_compromissos_google_agenda, "interval", minutes=INTERVALO_MINUTOS, args=[caminho_db, id_idoso, google_calendar_client], id="sincronizar_compromissos_google_agenda")` antes de `agendador.start()`.

Run: `pytest tests/test_api_scheduler.py -v`
Expected: PASS (toda a suíte)

- [ ] **Step 7: Ligar em `zela/api/main.py`**

Em `zela/api/main.py`, junto de onde `WAHA_API_KEY`/`TOKEN_INGESTAO` são lidos: ler `ZELA_GOOGLE_CALENDAR_CLIENT_ID`, `ZELA_GOOGLE_CALENDAR_CLIENT_SECRET`, `ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN`, `ZELA_GOOGLE_CALENDAR_CALENDAR_ID` via `os.environ.get`. Se as 4 estiverem presentes (não vazias — mesmo cuidado do `TOKEN_INGESTAO` com `or None`), instanciar `GoogleCalendarClient(...)`; senão, `google_calendar_client = None`. Passar pra `iniciar_scheduler(CAMINHO_DB, ID_IDOSO, waha_client, google_calendar_client=google_calendar_client)` (chamada existente — buscar onde `iniciar_scheduler` já é chamado em `main.py` e adicionar o argumento).

Não precisa de teste novo neste step — é fiação de variáveis de ambiente, mesmo padrão não testado isoladamente que já existe pra `WAHA_API_KEY`/`TOKEN_INGESTAO`.

- [ ] **Step 8: Adicionar as variáveis ao `docker-compose.yml`**

No serviço `backend`, bloco `environment`, adicionar (mesmo padrão de `ZELA_WAHA_API_KEY`):
```yaml
      - ZELA_GOOGLE_CALENDAR_CLIENT_ID=${ZELA_GOOGLE_CALENDAR_CLIENT_ID}
      - ZELA_GOOGLE_CALENDAR_CLIENT_SECRET=${ZELA_GOOGLE_CALENDAR_CLIENT_SECRET}
      - ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN=${ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN}
      - ZELA_GOOGLE_CALENDAR_CALENDAR_ID=${ZELA_GOOGLE_CALENDAR_CALENDAR_ID}
```

- [ ] **Step 9: Rodar a suíte completa**

Run: `pytest -q`
Expected: PASS (nenhuma regressão)

- [ ] **Step 10: Commit**

```bash
git add zela/api/scheduler.py zela/api/main.py docker-compose.yml tests/test_api_scheduler.py
git commit -m "feat: sincroniza compromissos com o google agenda via scheduler"
```

---

## Task 8: Painel Streamlit — remover compromisso

**Files:**
- Modify: `zela/streamlit_app/formularios.py`
- Test: `tests/test_streamlit_formularios.py`

**Interfaces:**
- Consumes: `zela.storage.rotina.remover_compromisso` (Task 3).
- Produces: `formulario_compromisso` ganha um botão "Remover" (fora do `st.form`, só visível quando `compromisso_existente is not None`).

- [ ] **Step 1: Escrever o teste**

```python
def test_formulario_compromisso_remove_existente(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conn = conectar(caminho)
    salvar_compromisso(
        conn,
        Compromisso(
            id="comp-1", titulo="Exame", data_hora=datetime.now() + timedelta(days=1),
            local="Laboratório X", tipo=TipoCompromisso.EXAME,
        ),
        idoso_id="idosa-1",
    )

    at = AppTest.from_string(_CODIGO_COMPROMISSO.format(caminho=caminho))
    at.run()

    at.selectbox[0].set_value("Exame").run()
    at.button[1].click().run()  # button[0] é "Salvar" (dentro do form); button[1] é "Remover"

    assert at.exception == []
    assert listar_compromissos(conectar(caminho), "idosa-1") == []
```

(Import novo no topo do arquivo de teste: `remover_compromisso` não é chamado diretamente no teste, só `listar_compromissos`, já importado.)

- [ ] **Step 2: Rodar e confirmar falha**

Run: `pytest tests/test_streamlit_formularios.py::test_formulario_compromisso_remove_existente -v`
Expected: FAIL (`IndexError` — não existe `button[1]` ainda)

- [ ] **Step 3: Adicionar o botão em `formulario_compromisso`**

Em `zela/streamlit_app/formularios.py`, importar `remover_compromisso` de `zela.storage.rotina`. Depois do bloco `with st.form(...)` (fora dele), se `compromisso_existente is not None`: `if st.button("Remover"): remover_compromisso(conn, compromisso_existente.id, idoso_id); st.session_state["mensagem_sucesso_compromisso"] = f"Compromisso '{compromisso_existente.titulo}' removido."; st.rerun()`.

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `pytest tests/test_streamlit_formularios.py -v`
Expected: PASS (toda a suíte do arquivo, sem regressão nos testes de criar/editar)

- [ ] **Step 5: Commit**

```bash
git add zela/streamlit_app/formularios.py tests/test_streamlit_formularios.py
git commit -m "feat: adiciona botao de remover compromisso no painel"
```

---

## Task 9: Script de comissionamento + documentação

**Files:**
- Create: `scripts/obter_refresh_token_google.py`
- Modify: `README.md`

**Interfaces:**
- Produces: script executável manualmente (fora da suíte de testes automatizados — é uma ferramenta interativa de setup, não código de produção).

- [ ] **Step 1: Escrever o script**

`scripts/obter_refresh_token_google.py`: script standalone (sem dependência do pacote `zela`) que recebe `client_id`/`client_secret` (via `input()` ou argumentos de linha de comando), abre o fluxo OAuth 2.0 "installed app" do Google (escopo `https://www.googleapis.com/auth/calendar`), e imprime o `refresh_token` obtido no final. Comentário no topo do arquivo explicando que é rodado uma única vez, manualmente, durante o comissionamento (ver seção 5.1 do design doc), e que o `refresh_token` impresso deve ir para a variável de ambiente `ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN` do deploy.

- [ ] **Step 2: Documentar o fluxo de comissionamento no README**

Em `README.md`, adicionar uma seção "Comissionamento: Google Agenda" (próxima da seção já existente sobre o smartwatch/Health Connect) cobrindo os 5 passos da seção 5.1 do design doc: criar a conta Google dedicada, criar o projeto no Google Cloud + credencial OAuth, rodar o script deste task pra obter o `refresh_token`, configurar as 4 variáveis de ambiente, e adicionar a conta como secundária no celular do idoso (com notificações do Google Agenda habilitadas e o Google Agenda whitelistado no espelhamento de notificação do Mi Fitness).

- [ ] **Step 3: Commit**

```bash
git add scripts/obter_refresh_token_google.py README.md
git commit -m "docs: adiciona script e documentacao de comissionamento do google agenda"
```

---

## Self-Review (realizado antes de entregar este plano)

1. **Cobertura do spec:** Conta Google/comissionamento → Task 9. Cliente de integração → Task 6. 3 overrides (não 4) → Task 2/6. `HORARIO_LEMBRETE_MANHA` constante → Task 2. Esquema de dados (3 colunas + tabela) → Task 1. Edição/remoção com reset de lembretes → Task 3. Scheduler assíncrono (dois jobs, nunca síncrono no Streamlit) → Tasks 5 e 7. Cancelamento por WhatsApp → Tasks 3 e 5. Falha da API não bloqueia nada → Task 7. Botão de remover no painel (não existia) → Task 8.
2. **Checagem de passos:** cada step de teste tem nome e asserts concretos; cada step de código tem assinatura exata e, quando o corpo não é óbvio pela assinatura+teste (cálculo de minutos, payload do Google, SQL dos `JOIN`/`NOT EXISTS`), o texto do step dá o algoritmo em prosa em vez de deixar em aberto.
3. **Consistência de tipos:** `TipoLembreteCompromisso` (Task 2) usado com os mesmos `.value` em Task 3 (`tipo_lembrete: str`), Task 4 (`formatar_lembrete_compromisso(..., tipo_lembrete: str)`) e Task 5. `CompromissoPendenteSync` (Task 3) consumido com os mesmos 3 campos em Task 7. `GoogleCalendarClient` (Task 6) com a mesma assinatura de `criar_evento`/`atualizar_evento`/`remover_evento` usada em Task 7.
4. **Review Focus:** as 5 entradas listadas no topo do documento têm teste nomeado na task correspondente (ver seção Review Focus, com a task já indicada em cada linha).
5. **Proporção:** o plano é mais longo que o spec (~300 linhas) porque cobre 9 tasks com passos de TDD explícitos (teste → falha → implementação → passa → commit) pra um spec que toca 6 arquivos novos/modificados e ~15 funções novas — proporção esperada para um plano de implementação desse tamanho, não um transcript do spec.
