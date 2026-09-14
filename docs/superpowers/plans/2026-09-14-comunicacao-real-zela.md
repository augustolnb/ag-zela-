# Zela+ — Comunicação Real via WAHA (Plano 2 de 7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar a conversa com o idoso real: mensagens de WhatsApp (via WAHA) chegam por um webhook FastAPI, são processadas pelo agente orquestrador ADK (agora com ferramentas de verdade no Agente de Rotina, lendo/gravando em SQLite), e um scheduler dispara lembretes de medicação periodicamente. A camada `zela/domain/` do Plano 1 não muda.

**Architecture:** Uma nova camada `zela/storage/` (repositórios SQLite) faz a ponte entre o banco e as funções puras de `zela/domain/`. O Agente de Rotina ganha `tools=[...]` reais apontando para essa camada. Um webhook FastAPI recebe mensagens do WAHA, chama o ADK Runner (via uma função `processar_mensagem` injetável, isolando o risco de integração), e responde via um cliente HTTP do WAHA. Um scheduler (APScheduler) roda em paralelo checando lembretes pendentes.

**Tech Stack:** Python 3.11+, `google-adk` (já instalado), `fastapi`, `uvicorn`, `httpx`, `apscheduler`, SQLite (via `sqlite3`, biblioteca padrão).

**Spec:** `docs/superpowers/specs/2026-09-10-cuida-mais-agente-idoso-design.md` (seção 13 detalha este plano).

## Global Constraints

- Python 3.11+, mesmas convenções do Plano 1 (enums para campos categóricos, `list[X]`/`X | None` nativos).
- **A camada `zela/domain/` não muda neste plano** — continua pura, testada sem I/O. Toda leitura/escrita de banco fica em `zela/storage/`.
- Persistência: SQLite local (arquivo único, `sqlite3` da biblioteca padrão — sem ORM).
- **Nenhum teste automatizado pode exigir um servidor WAHA real, uma chave de API do Gemini, nem acesso de rede.** Toda integração externa (WAHA, ADK Runner) é testada com fakes/mocks; a verificação manual real fica documentada no README, fora da suíte automatizada.
- Escopo de idoso: um único idoso "hardcoded" (`ID_IDOSO = "idosa-1"`) é aceitável para este MVP — o schema SQLite não impede múltiplos idosos no futuro, mas nenhuma tela/fluxo de cadastro múltiplo é construída agora.
- **Risco real de API externa (leia antes de implementar as Tasks 8 e 9):** o formato exato do webhook do WAHA e a API exata do `InMemoryRunner`/`Runner` do `google-adk` foram escritos a partir de conhecimento de treinamento, não verificados contra uma instância/versão real. Cada task que toca isso tem uma nota explícita de verificação — trate como a Task 10 do Plano 1 tratou a API do `google-adk` (que, naquele caso, bateu exatamente).
- Nome do projeto: **Zela+**. n8n **não** entra neste plano (fica para o Plano 6) — o FastAPI fala direto com o WAHA.

---

## Mapa de arquivos deste plano

```
zela/
  models/
    perfil.py            # MODIFICADO: adiciona campo `telefone` a PerfilIdoso
  storage/
    __init__.py
    db.py                 # conexão SQLite + schema completo
    perfil.py             # CRUD de PerfilIdoso
    rotina.py             # CRUD de Medicamento/ConfirmacaoMedicacao + aplicar_lembretes_pendentes/aplicar_confirmacao
  integrations/
    __init__.py
    waha_client.py        # WahaClient: enviar_texto, enviar_audio
  agents/
    orchestrator.py        # MODIFICADO: agente_rotina ganha tools=[...] reais
  api/
    __init__.py
    webhook.py             # roteador FastAPI /webhook/whatsapp (dependências injetáveis)
    runner.py              # processar_mensagem + obter_runner_zela (wrapping do ADK Runner)
    scheduler.py           # verificar_e_enviar_lembretes + iniciar_scheduler (APScheduler)
    main.py                # monta o FastAPI app final (lifespan, rotas, scheduler)
tests/
  test_models_perfil.py                # MODIFICADO: adiciona telefone nos fixtures
  test_domain_emergencia.py            # MODIFICADO: adiciona telefone no helper _perfil()
  test_simulacao.py                    # MODIFICADO: adiciona telefone no helper _perfil()
  test_storage_db.py
  test_storage_perfil.py
  test_storage_rotina.py
  test_agents_orchestrator_tools.py
  test_integrations_waha_client.py
  test_api_webhook.py
  test_api_runner.py
  test_api_scheduler.py
  test_api_main.py
docker-compose.yml           # serviço WAHA
pyproject.toml                # MODIFICADO: novas dependências
README.md                     # MODIFICADO: setup do WAHA, variáveis de ambiente, como rodar
```

---

### Task 1: Scaffolding — novas dependências e diretórios

**Files:**
- Modify: `pyproject.toml`
- Create: `zela/storage/__init__.py`
- Create: `zela/integrations/__init__.py`
- Create: `zela/api/__init__.py`

**Interfaces:**
- Produces: pacotes `zela.storage`, `zela.integrations`, `zela.api` importáveis; dependências `fastapi`, `httpx`, `apscheduler` instaladas.

- [ ] **Step 1: Criar os diretórios/arquivos vazios**

```bash
mkdir -p zela/storage zela/integrations zela/api
touch zela/storage/__init__.py zela/integrations/__init__.py zela/api/__init__.py
```

- [ ] **Step 2: Atualizar `pyproject.toml`** — adicionar ao array `dependencies`:

```toml
dependencies = [
    "pydantic>=2.6,<3",
    "google-adk>=1.0.0",
    "fastapi>=0.115",
    "httpx>=0.27",
    "apscheduler>=3.10,<4",
]
```

- [ ] **Step 3: Reinstalar o projeto com as novas dependências**

```bash
pip install -e ".[dev]"
```

- [ ] **Step 4: Verificar que tudo ainda importa e os testes do Plano 1 continuam passando**

Run: `pytest -q`
Expected: 43 passed (nada mudou ainda no código, só dependências novas)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml zela/storage zela/integrations zela/api
git commit -m "chore: scaffolding do Plano 2 (storage, integrations, api) e novas dependencias"
```

---

### Task 2: Adicionar telefone do idoso ao modelo `PerfilIdoso`

O Plano 1 não incluiu um telefone para o **idoso** em si (só para os `contatos_familiares`). Sem isso, não há para onde mandar os lembretes de WhatsApp. Esta task adiciona o campo e atualiza os três lugares do Plano 1 que constroem um `PerfilIdoso`.

**Files:**
- Modify: `zela/models/perfil.py`
- Modify: `tests/test_models_perfil.py`
- Modify: `tests/test_domain_emergencia.py`
- Modify: `tests/test_simulacao.py`

**Interfaces:**
- Produces: `PerfilIdoso` ganha um campo `telefone: str` (validado E.164, obrigatório).
- Consumes/afeta: todo código que constrói `PerfilIdoso` (nas Tasks 9-13 deste plano, `perfil.telefone` é o destino dos lembretes).

- [ ] **Step 1: Atualizar os testes existentes para incluir `telefone`**

Substitua o conteúdo de `tests/test_models_perfil.py` por:

```python
import pytest
from datetime import date
from pydantic import ValidationError

from zela.models.perfil import ContatoFamiliar, PerfilIdoso


def test_perfil_idoso_valido():
    perfil = PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )
    assert perfil.nome == "Maria da Silva"
    assert perfil.telefone == "+5511911111111"
    assert perfil.contatos_familiares[0].telefone == "+5511987654321"


def test_perfil_idoso_exige_ao_menos_um_contato_familiar():
    with pytest.raises(ValidationError):
        PerfilIdoso(
            nome="Maria da Silva",
            telefone="+5511911111111",
            data_nascimento=date(1945, 3, 12),
            contatos_familiares=[],
        )


def test_perfil_idoso_rejeita_telefone_fora_do_padrao_e164():
    with pytest.raises(ValidationError):
        PerfilIdoso(
            nome="Maria da Silva",
            telefone="011911111111",
            data_nascimento=date(1945, 3, 12),
            contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
        )


def test_contato_familiar_rejeita_telefone_fora_do_padrao_e164():
    with pytest.raises(ValidationError):
        ContatoFamiliar(nome="João", telefone="011987654321")


def test_perfil_idoso_condicoes_medicas_e_opcional_e_vazia_por_padrao():
    perfil = PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )
    assert perfil.condicoes_medicas == []
```

Em `tests/test_domain_emergencia.py`, atualize a função `_perfil()` para:

```python
def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=datetime(1945, 3, 12).date(),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )
```

Em `tests/test_simulacao.py`, atualize a função `_perfil()` para:

```python
def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=datetime(1945, 3, 12).date(),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_models_perfil.py tests/test_domain_emergencia.py tests/test_simulacao.py -v`
Expected: FAIL com `ValidationError: telefone Field required` (o modelo ainda não tem o campo)

- [ ] **Step 3: Implementar a mudança em `zela/models/perfil.py`**

```python
from datetime import date

from pydantic import BaseModel, Field

E164_PATTERN = r"^\+[1-9]\d{6,14}$"


class ContatoFamiliar(BaseModel):
    nome: str
    telefone: str = Field(pattern=E164_PATTERN)


class PerfilIdoso(BaseModel):
    nome: str
    telefone: str = Field(pattern=E164_PATTERN)
    data_nascimento: date
    contatos_familiares: list[ContatoFamiliar] = Field(min_length=1)
    condicoes_medicas: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Rodar a suíte completa e confirmar que passa**

Run: `pytest -v`
Expected: 43 passed (mesmos testes de antes, com o campo novo)

- [ ] **Step 5: Commit**

```bash
git add zela/models/perfil.py tests/test_models_perfil.py tests/test_domain_emergencia.py tests/test_simulacao.py
git commit -m "feat: adiciona telefone do idoso ao PerfilIdoso"
```

---

### Task 3: Storage — conexão SQLite e schema

**Files:**
- Create: `zela/storage/db.py`
- Test: `tests/test_storage_db.py`

**Interfaces:**
- Produces: `ESQUEMA: str` (SQL completo), `conectar(caminho_db: str = "zela.db") -> sqlite3.Connection`.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_storage_db.py
from zela.storage.db import ESQUEMA, conectar


def test_conectar_cria_todas_as_tabelas():
    conn = conectar(":memory:")
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tabelas = {linha["name"] for linha in cursor.fetchall()}
    assert tabelas == {
        "perfil_idoso",
        "medicamento",
        "confirmacao_medicacao",
        "compromisso",
        "leitura_sensor",
        "alerta",
        "estado_escalonamento",
    }


def test_conectar_e_idempotente():
    conn = conectar(":memory:")
    conn.executescript(ESQUEMA)  # não deve levantar erro ao rodar de novo
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `pytest tests/test_storage_db.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.storage.db'`

- [ ] **Step 3: Implementar `zela/storage/db.py`**

```python
import sqlite3

ESQUEMA = """
CREATE TABLE IF NOT EXISTS perfil_idoso (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    telefone TEXT NOT NULL,
    data_nascimento TEXT NOT NULL,
    condicoes_medicas TEXT NOT NULL,
    contatos_familiares TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS medicamento (
    id TEXT PRIMARY KEY,
    idoso_id TEXT NOT NULL,
    nome TEXT NOT NULL,
    dosagem_quantidade REAL NOT NULL,
    dosagem_unidade TEXT NOT NULL,
    horarios TEXT NOT NULL,
    dias_semana TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS confirmacao_medicacao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicamento_id TEXT NOT NULL,
    horario_previsto TEXT NOT NULL,
    horario_confirmado TEXT,
    status TEXT NOT NULL,
    canal TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS compromisso (
    id TEXT PRIMARY KEY,
    idoso_id TEXT NOT NULL,
    titulo TEXT NOT NULL,
    data_hora TEXT NOT NULL,
    local TEXT NOT NULL,
    tipo TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leitura_sensor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idoso_id TEXT NOT NULL,
    fonte TEXT NOT NULL,
    tipo TEXT NOT NULL,
    valor REAL NOT NULL,
    unidade TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idoso_id TEXT NOT NULL,
    nivel TEXT NOT NULL,
    destinatario TEXT NOT NULL,
    canal TEXT NOT NULL,
    mensagem TEXT NOT NULL,
    status TEXT NOT NULL,
    simulado INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS estado_escalonamento (
    idoso_id TEXT PRIMARY KEY,
    estagio TEXT NOT NULL,
    iniciado_em TEXT
);
"""


def conectar(caminho_db: str = "zela.db") -> sqlite3.Connection:
    conn = sqlite3.connect(caminho_db)
    conn.row_factory = sqlite3.Row
    conn.executescript(ESQUEMA)
    return conn
```

Nota: as tabelas `compromisso`, `leitura_sensor`, `alerta` e `estado_escalonamento` são criadas agora (schema completo, estável), mas só ganham código Python de leitura/escrita no Plano 3, quando os agentes de Monitoramento e Emergência forem religados e passarem a gerar alertas de verdade — construir esse repositório agora seria código sem consumidor neste plano (nada aqui gera alertas).

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `pytest tests/test_storage_db.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add zela/storage/db.py tests/test_storage_db.py
git commit -m "feat: conexao SQLite e schema completo do banco do Zela+"
```

---

### Task 4: Storage — repositório de perfil

**Files:**
- Create: `zela/storage/perfil.py`
- Test: `tests/test_storage_perfil.py`

**Interfaces:**
- Consumes: `zela.models.perfil.{PerfilIdoso, ContatoFamiliar}`, `zela.storage.db.conectar`.
- Produces: `salvar_perfil(conn, perfil: PerfilIdoso, idoso_id: str) -> None`, `obter_perfil(conn, idoso_id: str) -> PerfilIdoso | None`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_storage_perfil.py
from datetime import date

from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.storage.db import conectar
from zela.storage.perfil import obter_perfil, salvar_perfil


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def test_salvar_e_obter_perfil():
    conn = conectar(":memory:")
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")

    recuperado = obter_perfil(conn, "idosa-1")

    assert recuperado is not None
    assert recuperado.nome == "Maria da Silva"
    assert recuperado.telefone == "+5511911111111"
    assert recuperado.contatos_familiares[0].telefone == "+5511987654321"


def test_obter_perfil_inexistente_retorna_none():
    conn = conectar(":memory:")
    assert obter_perfil(conn, "nao-existe") is None


def test_salvar_perfil_atualiza_registro_existente():
    conn = conectar(":memory:")
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")

    perfil_atualizado = _perfil().model_copy(update={"nome": "Maria S. Silva"})
    salvar_perfil(conn, perfil_atualizado, idoso_id="idosa-1")

    recuperado = obter_perfil(conn, "idosa-1")
    assert recuperado.nome == "Maria S. Silva"
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_storage_perfil.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.storage.perfil'`

- [ ] **Step 3: Implementar `zela/storage/perfil.py`**

```python
import json
import sqlite3

from zela.models.perfil import ContatoFamiliar, PerfilIdoso


def salvar_perfil(conn: sqlite3.Connection, perfil: PerfilIdoso, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO perfil_idoso (id, nome, telefone, data_nascimento, condicoes_medicas, contatos_familiares)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nome = excluded.nome,
            telefone = excluded.telefone,
            data_nascimento = excluded.data_nascimento,
            condicoes_medicas = excluded.condicoes_medicas,
            contatos_familiares = excluded.contatos_familiares
        """,
        (
            idoso_id,
            perfil.nome,
            perfil.telefone,
            perfil.data_nascimento.isoformat(),
            json.dumps(perfil.condicoes_medicas),
            json.dumps([c.model_dump() for c in perfil.contatos_familiares]),
        ),
    )
    conn.commit()


def obter_perfil(conn: sqlite3.Connection, idoso_id: str) -> PerfilIdoso | None:
    linha = conn.execute("SELECT * FROM perfil_idoso WHERE id = ?", (idoso_id,)).fetchone()
    if linha is None:
        return None
    return PerfilIdoso(
        nome=linha["nome"],
        telefone=linha["telefone"],
        data_nascimento=linha["data_nascimento"],
        condicoes_medicas=json.loads(linha["condicoes_medicas"]),
        contatos_familiares=[
            ContatoFamiliar(**c) for c in json.loads(linha["contatos_familiares"])
        ],
    )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_storage_perfil.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add zela/storage/perfil.py tests/test_storage_perfil.py
git commit -m "feat: repositorio SQLite de PerfilIdoso"
```

---

### Task 5: Storage — repositório de rotina (medicamentos e confirmações)

**Files:**
- Create: `zela/storage/rotina.py`
- Test: `tests/test_storage_rotina.py`

**Interfaces:**
- Consumes: `zela.domain.rotina.{calcular_lembretes_pendentes, registrar_confirmacao}`, `zela.models.rotina.*`.
- Produces: `salvar_medicamento(conn, medicamento, idoso_id) -> None`, `listar_medicamentos(conn, idoso_id) -> list[Medicamento]`, `salvar_confirmacao(conn, confirmacao) -> None`, `listar_confirmacoes_do_dia(conn, idoso_id, dia) -> list[ConfirmacaoMedicacao]`, `aplicar_lembretes_pendentes(conn, idoso_id, agora) -> list[Medicamento]`, `aplicar_confirmacao(conn, medicamento, horario_previsto, agora, canal=...) -> ConfirmacaoMedicacao`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_storage_rotina.py
from datetime import datetime, time

from zela.models.rotina import Dosagem, Medicamento
from zela.storage.db import conectar
from zela.storage.rotina import (
    aplicar_confirmacao,
    aplicar_lembretes_pendentes,
    listar_medicamentos,
    salvar_medicamento,
)


def _medicamento():
    return Medicamento(
        id="med-1",
        nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"),
        horarios=[time(8, 0)],
    )


def test_salvar_e_listar_medicamentos():
    conn = conectar(":memory:")
    salvar_medicamento(conn, _medicamento(), idoso_id="idosa-1")

    medicamentos = listar_medicamentos(conn, "idosa-1")

    assert len(medicamentos) == 1
    assert medicamentos[0].nome == "Losartana"
    assert medicamentos[0].horarios == [time(8, 0)]
    assert medicamentos[0].dosagem.quantidade == 50


def test_aplicar_lembretes_pendentes_encontra_medicamento_na_janela():
    conn = conectar(":memory:")
    salvar_medicamento(conn, _medicamento(), idoso_id="idosa-1")
    agora = datetime(2026, 9, 14, 8, 5)

    pendentes = aplicar_lembretes_pendentes(conn, "idosa-1", agora)

    assert len(pendentes) == 1
    assert pendentes[0].id == "med-1"


def test_aplicar_confirmacao_persiste_e_exclui_de_lembretes_futuros():
    conn = conectar(":memory:")
    medicamento = _medicamento()
    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")
    agora = datetime(2026, 9, 14, 8, 5)

    confirmacao = aplicar_confirmacao(conn, medicamento, horario_previsto=agora, agora=agora)
    assert confirmacao.medicamento_id == "med-1"
    assert confirmacao.status.value == "confirmado"

    pendentes_depois = aplicar_lembretes_pendentes(conn, "idosa-1", agora)
    assert pendentes_depois == []
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_storage_rotina.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.storage.rotina'`

- [ ] **Step 3: Implementar `zela/storage/rotina.py`**

```python
import json
import sqlite3
from datetime import datetime, time

from zela.domain.rotina import calcular_lembretes_pendentes
from zela.domain.rotina import registrar_confirmacao as registrar_confirmacao_dominio
from zela.models.rotina import (
    CanalConfirmacao,
    ConfirmacaoMedicacao,
    Dosagem,
    Medicamento,
    StatusConfirmacao,
)


def salvar_medicamento(conn: sqlite3.Connection, medicamento: Medicamento, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO medicamento
            (id, idoso_id, nome, dosagem_quantidade, dosagem_unidade, horarios, dias_semana, ativo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nome = excluded.nome,
            dosagem_quantidade = excluded.dosagem_quantidade,
            dosagem_unidade = excluded.dosagem_unidade,
            horarios = excluded.horarios,
            dias_semana = excluded.dias_semana,
            ativo = excluded.ativo
        """,
        (
            medicamento.id,
            idoso_id,
            medicamento.nome,
            medicamento.dosagem.quantidade,
            medicamento.dosagem.unidade,
            json.dumps([h.isoformat() for h in medicamento.horarios]),
            json.dumps(medicamento.dias_semana),
            int(medicamento.ativo),
        ),
    )
    conn.commit()


def _linha_para_medicamento(linha: sqlite3.Row) -> Medicamento:
    return Medicamento(
        id=linha["id"],
        nome=linha["nome"],
        dosagem=Dosagem(quantidade=linha["dosagem_quantidade"], unidade=linha["dosagem_unidade"]),
        horarios=[time.fromisoformat(h) for h in json.loads(linha["horarios"])],
        dias_semana=json.loads(linha["dias_semana"]),
        ativo=bool(linha["ativo"]),
    )


def listar_medicamentos(conn: sqlite3.Connection, idoso_id: str) -> list[Medicamento]:
    linhas = conn.execute("SELECT * FROM medicamento WHERE idoso_id = ?", (idoso_id,)).fetchall()
    return [_linha_para_medicamento(linha) for linha in linhas]


def salvar_confirmacao(conn: sqlite3.Connection, confirmacao: ConfirmacaoMedicacao) -> None:
    conn.execute(
        """
        INSERT INTO confirmacao_medicacao
            (medicamento_id, horario_previsto, horario_confirmado, status, canal)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            confirmacao.medicamento_id,
            confirmacao.horario_previsto.isoformat(),
            confirmacao.horario_confirmado.isoformat() if confirmacao.horario_confirmado else None,
            confirmacao.status.value,
            confirmacao.canal.value,
        ),
    )
    conn.commit()


def listar_confirmacoes_do_dia(
    conn: sqlite3.Connection, idoso_id: str, dia: datetime
) -> list[ConfirmacaoMedicacao]:
    linhas = conn.execute(
        """
        SELECT cm.* FROM confirmacao_medicacao cm
        JOIN medicamento m ON m.id = cm.medicamento_id
        WHERE m.idoso_id = ? AND date(cm.horario_previsto) = date(?)
        """,
        (idoso_id, dia.isoformat()),
    ).fetchall()
    return [
        ConfirmacaoMedicacao(
            medicamento_id=linha["medicamento_id"],
            horario_previsto=datetime.fromisoformat(linha["horario_previsto"]),
            horario_confirmado=(
                datetime.fromisoformat(linha["horario_confirmado"])
                if linha["horario_confirmado"]
                else None
            ),
            status=StatusConfirmacao(linha["status"]),
            canal=CanalConfirmacao(linha["canal"]),
        )
        for linha in linhas
    ]


def aplicar_lembretes_pendentes(
    conn: sqlite3.Connection, idoso_id: str, agora: datetime
) -> list[Medicamento]:
    medicamentos = listar_medicamentos(conn, idoso_id)
    confirmacoes = listar_confirmacoes_do_dia(conn, idoso_id, agora)
    return calcular_lembretes_pendentes(medicamentos, confirmacoes, agora)


def aplicar_confirmacao(
    conn: sqlite3.Connection,
    medicamento: Medicamento,
    horario_previsto: datetime,
    agora: datetime,
    canal: CanalConfirmacao = CanalConfirmacao.WHATSAPP,
) -> ConfirmacaoMedicacao:
    confirmacao = registrar_confirmacao_dominio(medicamento, horario_previsto, agora, canal)
    salvar_confirmacao(conn, confirmacao)
    return confirmacao
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_storage_rotina.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add zela/storage/rotina.py tests/test_storage_rotina.py
git commit -m "feat: repositorio SQLite de medicamentos e confirmacoes"
```

---

### Task 6: Ferramentas reais no Agente de Rotina (ADK)

**Files:**
- Modify: `zela/agents/orchestrator.py`
- Test: `tests/test_agents_orchestrator_tools.py`

**Interfaces:**
- Consumes: `zela.storage.rotina.{aplicar_lembretes_pendentes, aplicar_confirmacao, listar_medicamentos}`, `zela.storage.db.conectar`.
- Produces: funções de ferramenta `verificar_lembretes_pendentes(idoso_id: str, agora_iso: str) -> list[dict]`, `confirmar_medicamento(idoso_id: str, medicamento_id: str, horario_previsto_iso: str, agora_iso: str) -> dict`; `montar_agente_rotina` passa a usar `tools=[verificar_lembretes_pendentes, confirmar_medicamento]`.

**Risco real de API (ADK):** não há garantia de que `agente.tools` exponha as funções Python originais sem transformação — o ADK pode envolvê-las em objetos `FunctionTool`. Os testes abaixo verificam a contagem de ferramentas (`len(...) == 2`, estrutural e robusto) e testam as funções de ferramenta diretamente como funções Python comuns (sem depender do ADK para isso). Se `len(agente.tools) == 2` não bater com a instalação real, inspecione `agente.tools` (`python3 -c "..."`) e ajuste a asserção — a lógica das próprias funções de ferramenta não muda.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_agents_orchestrator_tools.py
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
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_agents_orchestrator_tools.py -v`
Expected: FAIL (`ImportError` — `confirmar_medicamento`/`verificar_lembretes_pendentes` ainda não existem)

- [ ] **Step 3: Adicionar as ferramentas em `zela/agents/orchestrator.py`**

No topo do arquivo, junto aos imports existentes, adicione:

```python
from datetime import datetime

from zela.storage.db import conectar
from zela.storage.rotina import aplicar_confirmacao, aplicar_lembretes_pendentes, listar_medicamentos

_CAMINHO_DB = "zela.db"


def _obter_conexao():
    return conectar(_CAMINHO_DB)


def verificar_lembretes_pendentes(idoso_id: str, agora_iso: str) -> list[dict]:
    """Retorna os medicamentos com lembrete pendente para o idoso no horário informado (ISO 8601)."""
    conn = _obter_conexao()
    agora = datetime.fromisoformat(agora_iso)
    pendentes = aplicar_lembretes_pendentes(conn, idoso_id, agora)
    return [m.model_dump(mode="json") for m in pendentes]


def confirmar_medicamento(
    idoso_id: str, medicamento_id: str, horario_previsto_iso: str, agora_iso: str
) -> dict:
    """Registra que o idoso confirmou ter tomado um medicamento."""
    conn = _obter_conexao()
    medicamentos = {m.id: m for m in listar_medicamentos(conn, idoso_id)}
    medicamento = medicamentos.get(medicamento_id)
    if medicamento is None:
        return {"erro": f"medicamento {medicamento_id} não encontrado"}
    confirmacao = aplicar_confirmacao(
        conn,
        medicamento,
        horario_previsto=datetime.fromisoformat(horario_previsto_iso),
        agora=datetime.fromisoformat(agora_iso),
    )
    return confirmacao.model_dump(mode="json")
```

Depois, modifique `montar_agente_rotina` (mantendo `name`, `model`, `description` como estão) para passar as ferramentas:

```python
def montar_agente_rotina(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_rotina",
        model=model,
        description="Gerencia lembretes de medicamentos e compromissos do idoso.",
        instruction=(
            "Verifique a agenda de medicamentos do idoso usando "
            "verificar_lembretes_pendentes, e registre confirmações com "
            "confirmar_medicamento quando o idoso informar que tomou o "
            "medicamento."
        ),
        tools=[verificar_lembretes_pendentes, confirmar_medicamento],
    )
```

Não altere `montar_agente_monitoramento`, `montar_agente_comunicacao`, `montar_agente_emergencia` nem `montar_orquestrador` — eles continuam sem `tools=[]` neste plano (ver Global Constraints).

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_agents_orchestrator_tools.py tests/test_agents_orchestrator.py -v`
Expected: todos passam (os testes estruturais da Task 10 do Plano 1 continuam válidos)

- [ ] **Step 5: Rodar a suíte completa**

Run: `pytest -q`
Expected: todos passam (43 anteriores + os novos desta task)

- [ ] **Step 6: Commit**

```bash
git add zela/agents/orchestrator.py tests/test_agents_orchestrator_tools.py
git commit -m "feat: ferramentas reais (SQLite) no agente de rotina"
```

---

### Task 7: Cliente WAHA

**Files:**
- Create: `zela/integrations/waha_client.py`
- Test: `tests/test_integrations_waha_client.py`

**Interfaces:**
- Produces: `WahaClient(base_url: str, session: str = "default")` com métodos `enviar_texto(telefone: str, texto: str) -> dict` e `enviar_audio(telefone: str, audio_base64: str, mimetype: str = "audio/ogg") -> dict`.

**Risco real de API (WAHA):** o endpoint e o formato de payload abaixo (`/api/sendText`, `/api/sendVoice`, `chatId`/`text`/`file`/`session`) foram escritos a partir de conhecimento de treinamento sobre o WAHA (devlikeapro/whatsapp-http-api) e podem ter mudado. Antes de usar contra uma instância real, abra a documentação Swagger exposta na raiz da instância (ex.: `http://localhost:3000/`) e ajuste `WahaClient` se necessário — os testes usam HTTP mockado, então continuam passando independente disso; só a integração manual real depende da verificação.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_integrations_waha_client.py
import httpx

from zela.integrations.waha_client import WahaClient


class _RespostaFalsa:
    def __init__(self, json_data):
        self._json_data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def test_enviar_texto_monta_payload_correto(monkeypatch):
    chamadas = []

    def post_falso(url, json, timeout):
        chamadas.append((url, json, timeout))
        return _RespostaFalsa({"id": "msg-1"})

    monkeypatch.setattr(httpx, "post", post_falso)

    cliente = WahaClient(base_url="http://localhost:3000")
    resultado = cliente.enviar_texto("+5511987654321", "Olá!")

    assert resultado == {"id": "msg-1"}
    url, payload, _ = chamadas[0]
    assert url == "http://localhost:3000/api/sendText"
    assert payload["chatId"] == "5511987654321@c.us"
    assert payload["text"] == "Olá!"
    assert payload["session"] == "default"


def test_enviar_audio_monta_payload_correto(monkeypatch):
    chamadas = []

    def post_falso(url, json, timeout):
        chamadas.append((url, json, timeout))
        return _RespostaFalsa({"id": "msg-2"})

    monkeypatch.setattr(httpx, "post", post_falso)

    cliente = WahaClient(base_url="http://localhost:3000")
    resultado = cliente.enviar_audio("+5511987654321", "YmFzZTY0", mimetype="audio/ogg")

    assert resultado == {"id": "msg-2"}
    url, payload, _ = chamadas[0]
    assert url == "http://localhost:3000/api/sendVoice"
    assert payload["file"]["data"] == "YmFzZTY0"
    assert payload["file"]["mimetype"] == "audio/ogg"


def test_para_chat_id_remove_sinal_de_mais():
    assert WahaClient._para_chat_id("+5511987654321") == "5511987654321@c.us"
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_integrations_waha_client.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.integrations.waha_client'`

- [ ] **Step 3: Implementar `zela/integrations/waha_client.py`**

```python
import httpx


class WahaClient:
    def __init__(self, base_url: str, session: str = "default"):
        self.base_url = base_url.rstrip("/")
        self.session = session

    def enviar_texto(self, telefone: str, texto: str) -> dict:
        resposta = httpx.post(
            f"{self.base_url}/api/sendText",
            json={"chatId": self._para_chat_id(telefone), "text": texto, "session": self.session},
            timeout=30,
        )
        resposta.raise_for_status()
        return resposta.json()

    def enviar_audio(self, telefone: str, audio_base64: str, mimetype: str = "audio/ogg") -> dict:
        resposta = httpx.post(
            f"{self.base_url}/api/sendVoice",
            json={
                "chatId": self._para_chat_id(telefone),
                "file": {"mimetype": mimetype, "data": audio_base64},
                "session": self.session,
            },
            timeout=30,
        )
        resposta.raise_for_status()
        return resposta.json()

    @staticmethod
    def _para_chat_id(telefone: str) -> str:
        numero = telefone.lstrip("+")
        return f"{numero}@c.us"
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_integrations_waha_client.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add zela/integrations/waha_client.py tests/test_integrations_waha_client.py
git commit -m "feat: cliente HTTP do WAHA (enviar texto e audio)"
```

---

### Task 8: Webhook FastAPI

**Files:**
- Create: `zela/api/webhook.py`
- Test: `tests/test_api_webhook.py`

**Interfaces:**
- Consumes: `zela.integrations.waha_client.WahaClient` (via injeção de dependência — não instanciado dentro deste módulo).
- Produces: `montar_roteador(processar_mensagem, waha_client, id_idoso: str = "idosa-1") -> fastapi.APIRouter`, expondo `POST /webhook/whatsapp`. `processar_mensagem` é uma função `(id_idoso: str, texto: str, agora: datetime) -> str` injetada pelo chamador (a implementação real vem da Task 9).

**Risco real de API (WAHA):** o formato do payload do webhook assumido abaixo (`payload["payload"]["from"]`, `payload["payload"]["body"]`) é uma suposição razoável baseada em conhecimento de treinamento sobre o WAHA, não verificada contra uma instância real. Antes de usar em produção, dispare uma mensagem de teste (WhatsApp real → WAHA → seu webhook local, ou via `curl` simulando o WAHA) e confira o JSON recebido de fato, ajustando `_extrair_telefone_e_texto` se necessário — a suíte de testes usa payloads fabricados e não depende do formato real estar certo.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_api_webhook.py
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zela.api.webhook import montar_roteador


class _WahaFalso:
    def __init__(self):
        self.enviados = []

    def enviar_texto(self, telefone, texto):
        self.enviados.append((telefone, texto))
        return {"id": "msg-1"}


def test_webhook_processa_mensagem_e_envia_resposta():
    waha_falso = _WahaFalso()

    def processar_falso(id_idoso, texto, agora):
        assert id_idoso == "idosa-1"
        assert texto == "já tomei"
        return "Que bom! Confirmado."

    app = FastAPI()
    app.include_router(montar_roteador(processar_falso, waha_falso))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={
            "event": "message",
            "session": "default",
            "payload": {"from": "5511987654321@c.us", "body": "já tomei", "fromMe": False},
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "processado"}
    assert waha_falso.enviados == [("+5511987654321", "Que bom! Confirmado.")]


def test_webhook_ignora_payload_sem_remetente_ou_texto():
    waha_falso = _WahaFalso()
    app = FastAPI()
    app.include_router(montar_roteador(lambda *a: "nunca chamado", waha_falso))
    cliente = TestClient(app)

    resposta = cliente.post("/webhook/whatsapp", json={"event": "message", "payload": {}})

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ignorado"}
    assert waha_falso.enviados == []
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_api_webhook.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.api.webhook'`

- [ ] **Step 3: Implementar `zela/api/webhook.py`**

```python
from datetime import datetime

from fastapi import APIRouter, Request

_ID_IDOSO_PADRAO = "idosa-1"


def _extrair_telefone_e_texto(payload: dict) -> tuple[str, str] | None:
    dados = payload.get("payload", {})
    remetente = dados.get("from")
    texto = dados.get("body")
    if not remetente or not texto:
        return None
    telefone = "+" + remetente.split("@")[0]
    return telefone, texto


def montar_roteador(processar_mensagem, waha_client, id_idoso: str = _ID_IDOSO_PADRAO) -> APIRouter:
    roteador = APIRouter()

    @roteador.post("/webhook/whatsapp")
    async def receber_mensagem(request: Request):
        payload = await request.json()
        extraido = _extrair_telefone_e_texto(payload)
        if extraido is None:
            return {"status": "ignorado"}
        telefone, texto = extraido

        resposta_texto = processar_mensagem(id_idoso, texto, datetime.now())
        waha_client.enviar_texto(telefone, resposta_texto)

        return {"status": "processado"}

    return roteador
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_webhook.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add zela/api/webhook.py tests/test_api_webhook.py
git commit -m "feat: webhook FastAPI para mensagens do WhatsApp via WAHA"
```

---

### Task 9: Runner — ponte com o ADK Runner

**Files:**
- Create: `zela/api/runner.py`
- Test: `tests/test_api_runner.py`

**Interfaces:**
- Consumes: `zela.agents.orchestrator.root_agent` (exportado no Plano 1, fix da revisão final), `google.adk.runners.InMemoryRunner`, `google.genai.types`.
- Produces: `obter_runner_zela() -> InMemoryRunner`, `processar_mensagem(runner, id_idoso: str, texto: str, agora: datetime) -> str`.

**Risco real de API (google-adk):** a forma exata de invocar o `InMemoryRunner` (nome do método para criar sessão, assinatura de `.run(...)`, formato dos eventos retornados) foi escrita a partir de conhecimento de treinamento e **não foi verificada** contra a versão instalada — diferente da Task 10 do Plano 1 (onde a verificação da API do `Agent` bateu exatamente), aqui o risco é maior porque o Runner tem mais superfície de API. Antes de considerar esta task pronta:
1. Rode `python3 -c "from google.adk.runners import InMemoryRunner; help(InMemoryRunner)"` (ou inspecione o código-fonte do pacote instalado) e confirme os nomes reais dos métodos usados abaixo (`session_service.create_session_sync`, `.run(user_id=, session_id=, new_message=)`, `evento.is_final_response()`, `evento.content.parts[0].text`).
2. Se algo divergir, ajuste `processar_mensagem`/`obter_runner_zela` para a API real, mantendo a mesma assinatura pública (`processar_mensagem(runner, id_idoso, texto, agora) -> str`) e a mesma lógica (extrair o texto do evento de resposta final).
3. Documente no relatório da task qualquer divergência encontrada e como foi resolvida.

Para manter os testes livres de rede/LLM, `processar_mensagem` recebe o `runner` por parâmetro (injeção de dependência) e os testes usam um runner falso com o mesmo formato de interface — a chamada real ao `InMemoryRunner` de verdade só acontece na Task 11 (montagem do app), fora da suíte automatizada.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_api_runner.py
from datetime import datetime

from zela.api.runner import obter_runner_zela, processar_mensagem


class _ParteFalsa:
    def __init__(self, text):
        self.text = text


class _ConteudoFalso:
    def __init__(self, texto):
        self.parts = [_ParteFalsa(texto)]


class _EventoFalso:
    def __init__(self, texto, final=True):
        self.content = _ConteudoFalso(texto)
        self._final = final

    def is_final_response(self):
        return self._final


class _SessaoFalsa:
    id = "sessao-1"


class _ServicoSessaoFalso:
    def create_session_sync(self, app_name, user_id, session_id):
        return _SessaoFalsa()


class _RunnerFalso:
    def __init__(self, eventos):
        self.session_service = _ServicoSessaoFalso()
        self._eventos = eventos
        self.chamadas = []

    def run(self, user_id, session_id, new_message):
        self.chamadas.append((user_id, session_id, new_message))
        return self._eventos


def test_processar_mensagem_extrai_texto_do_evento_final():
    runner_falso = _RunnerFalso([_EventoFalso("Que bom que tomou!")])

    resposta = processar_mensagem(runner_falso, "idosa-1", "já tomei", datetime(2026, 9, 14, 8, 5))

    assert resposta == "Que bom que tomou!"
    assert len(runner_falso.chamadas) == 1


def test_processar_mensagem_retorna_mensagem_padrao_sem_evento_final():
    runner_falso = _RunnerFalso([])

    resposta = processar_mensagem(runner_falso, "idosa-1", "oi", datetime(2026, 9, 14, 8, 5))

    assert "não consegui processar" in resposta.lower()


def test_obter_runner_zela_usa_o_agente_orquestrador():
    runner = obter_runner_zela()
    assert runner.agent.name == "orquestrador_zela"
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_api_runner.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.api.runner'`

- [ ] **Step 3: Implementar `zela/api/runner.py`**

```python
from datetime import datetime

from google.adk.runners import InMemoryRunner
from google.genai import types

from zela.agents.orchestrator import root_agent

_APP_NAME = "zela"


def obter_runner_zela() -> InMemoryRunner:
    return InMemoryRunner(agent=root_agent, app_name=_APP_NAME)


def processar_mensagem(runner, id_idoso: str, texto: str, agora: datetime) -> str:
    """Processa uma mensagem do idoso através do agente orquestrador e
    retorna o texto da resposta. `runner` é injetado para permitir testes
    sem um Runner ADK real (ver nota de risco de API no cabeçalho da task)."""
    sessao = runner.session_service.create_session_sync(
        app_name=_APP_NAME, user_id=id_idoso, session_id=id_idoso
    )
    mensagem = types.Content(role="user", parts=[types.Part(text=texto)])

    texto_resposta = ""
    for evento in runner.run(user_id=id_idoso, session_id=sessao.id, new_message=mensagem):
        if evento.is_final_response() and evento.content and evento.content.parts:
            texto_resposta = evento.content.parts[0].text or ""

    return texto_resposta or "Desculpe, não consegui processar sua mensagem agora."
```

- [ ] **Step 4: Rodar os testes e confirmar que passam (ou adaptar conforme a nota de risco de API)**

Run: `pytest tests/test_api_runner.py -v`
Expected: 3 passed. O terceiro teste (`test_obter_runner_zela_usa_o_agente_orquestrador`) constrói um `InMemoryRunner` de verdade (sem chamar `.run()`, então sem rede/LLM) — se `runner.agent` não for o atributo correto para acessar o agente associado, inspecione `InMemoryRunner` e ajuste a asserção.

- [ ] **Step 5: Commit**

```bash
git add zela/api/runner.py tests/test_api_runner.py
git commit -m "feat: ponte com o ADK Runner para processar mensagens do idoso"
```

---

### Task 10: Scheduler de lembretes

**Files:**
- Create: `zela/api/scheduler.py`
- Test: `tests/test_api_scheduler.py`

**Interfaces:**
- Consumes: `zela.storage.db.conectar`, `zela.storage.perfil.obter_perfil`, `zela.storage.rotina.aplicar_lembretes_pendentes`, `zela.domain.comunicacao.formatar_lembrete`, `zela.integrations.waha_client.WahaClient`.
- Produces: `verificar_e_enviar_lembretes(caminho_db: str, id_idoso: str, waha_client) -> list[str]`, `iniciar_scheduler(caminho_db: str, id_idoso: str, waha_client) -> BackgroundScheduler`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_api_scheduler.py
from datetime import date, time

from zela.api.scheduler import verificar_e_enviar_lembretes
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.models.rotina import Dosagem, Medicamento
from zela.storage.db import conectar
from zela.storage.perfil import salvar_perfil
from zela.storage.rotina import salvar_medicamento


class _WahaFalso:
    def __init__(self):
        self.enviados = []

    def enviar_texto(self, telefone, texto):
        self.enviados.append((telefone, texto))


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def test_verificar_e_enviar_lembretes_envia_para_o_telefone_do_idoso(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")
    medicamento = Medicamento(
        id="med-1", nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
    )
    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")

    class _DatetimeFixo:
        @staticmethod
        def now():
            from datetime import datetime as _dt
            return _dt(2026, 9, 14, 8, 5)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    waha_falso = _WahaFalso()
    enviadas = verificar_e_enviar_lembretes(caminho_db, "idosa-1", waha_falso)

    assert len(enviadas) == 1
    assert "Losartana" in enviadas[0]
    assert waha_falso.enviados[0][0] == "+5511911111111"


def test_verificar_e_enviar_lembretes_sem_perfil_retorna_lista_vazia(tmp_path):
    caminho_db = str(tmp_path / "teste.db")
    conectar(caminho_db)

    waha_falso = _WahaFalso()
    enviadas = verificar_e_enviar_lembretes(caminho_db, "nao-existe", waha_falso)

    assert enviadas == []
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_api_scheduler.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.api.scheduler'`

- [ ] **Step 3: Implementar `zela/api/scheduler.py`**

```python
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from zela.domain.comunicacao import formatar_lembrete
from zela.storage.db import conectar
from zela.storage.perfil import obter_perfil
from zela.storage.rotina import aplicar_lembretes_pendentes

INTERVALO_MINUTOS = 5


def verificar_e_enviar_lembretes(caminho_db: str, id_idoso: str, waha_client) -> list[str]:
    conn = conectar(caminho_db)
    perfil = obter_perfil(conn, id_idoso)
    if perfil is None:
        return []

    agora = datetime.now()
    pendentes = aplicar_lembretes_pendentes(conn, id_idoso, agora)

    enviadas = []
    for medicamento in pendentes:
        texto = formatar_lembrete(medicamento)
        waha_client.enviar_texto(perfil.telefone, texto)
        enviadas.append(texto)
    return enviadas


def iniciar_scheduler(caminho_db: str, id_idoso: str, waha_client) -> BackgroundScheduler:
    agendador = BackgroundScheduler()
    agendador.add_job(
        verificar_e_enviar_lembretes,
        "interval",
        minutes=INTERVALO_MINUTOS,
        args=[caminho_db, id_idoso, waha_client],
        id="verificar_lembretes",
    )
    agendador.start()
    return agendador
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_scheduler.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add zela/api/scheduler.py tests/test_api_scheduler.py
git commit -m "feat: scheduler de lembretes de medicacao via APScheduler"
```

---

### Task 11: Montagem do app FastAPI

**Files:**
- Create: `zela/api/main.py`
- Test: `tests/test_api_main.py`

**Interfaces:**
- Consumes: tudo das Tasks 8-11 (`WahaClient`, `montar_roteador`, `obter_runner_zela`, `processar_mensagem`, `iniciar_scheduler`).
- Produces: `app: FastAPI` pronto para rodar com `uvicorn zela.api.main:app`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_api_main.py
from fastapi.testclient import TestClient


def test_app_inclui_rota_de_webhook():
    from zela.api.main import app

    rotas = {rota.path for rota in app.routes}
    assert "/webhook/whatsapp" in rotas


def test_app_sobe_e_desce_com_lifespan(monkeypatch):
    class _AgendadorFalso:
        def shutdown(self):
            pass

    monkeypatch.setattr("zela.api.main.iniciar_scheduler", lambda *a, **k: _AgendadorFalso())

    from zela.api.main import app

    with TestClient(app) as cliente:
        resposta = cliente.get("/docs")
        assert resposta.status_code == 200
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_api_main.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.api.main'`

- [ ] **Step 3: Implementar `zela/api/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from zela.api.runner import obter_runner_zela, processar_mensagem
from zela.api.scheduler import iniciar_scheduler
from zela.api.webhook import montar_roteador
from zela.integrations.waha_client import WahaClient

CAMINHO_DB = "zela.db"
ID_IDOSO = "idosa-1"
WAHA_BASE_URL = "http://localhost:3000"

waha_client = WahaClient(base_url=WAHA_BASE_URL)
_runner = obter_runner_zela()


def _processar(id_idoso: str, texto: str, agora) -> str:
    return processar_mensagem(_runner, id_idoso, texto, agora)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    agendador = iniciar_scheduler(CAMINHO_DB, ID_IDOSO, waha_client)
    yield
    agendador.shutdown()


app = FastAPI(lifespan=ciclo_de_vida)
app.include_router(montar_roteador(_processar, waha_client, id_idoso=ID_IDOSO))
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_main.py -v`
Expected: 2 passed

- [ ] **Step 5: Rodar a suíte completa do projeto**

Run: `pytest -q`
Expected: todos os testes passam (Plano 1 + Plano 2)

- [ ] **Step 6: Commit**

```bash
git add zela/api/main.py tests/test_api_main.py
git commit -m "feat: monta o app FastAPI final (webhook + scheduler)"
```

---

### Task 12: Docker Compose do WAHA e documentação

**Files:**
- Create: `docker-compose.yml`
- Modify: `README.md`

**Interfaces:**
- Nenhuma (infraestrutura + documentação).

- [ ] **Step 1: Criar `docker-compose.yml`**

```yaml
services:
  waha:
    image: devlikeapro/waha
    ports:
      - "3000:3000"
    volumes:
      - waha_data:/app/.sessions

volumes:
  waha_data:
```

- [ ] **Step 2: Atualizar o README** — substituir a linha "2. Comunicação real..." da seção "Status do projeto" por uma marcação de concluído, e adicionar uma nova seção `## Configurando o WAHA (WhatsApp)` com o seguinte conteúdo:

```markdown
## Configurando o WAHA (WhatsApp)

1. Suba o container do WAHA:
   ```bash
   docker compose up -d
   ```
2. Abra `http://localhost:3000/` no navegador — o WAHA expõe um painel/Swagger
   com um QR code. Escaneie com o WhatsApp do número que vai representar o
   Zela+ (pode ser um número dedicado ao projeto, não precisa ser o número
   pessoal do idoso).
3. Configure o webhook do WAHA para apontar para
   `http://<seu-host>:8000/webhook/whatsapp` (durante desenvolvimento local,
   use uma ferramenta de túnel como `ngrok` se o WAHA rodar em um ambiente
   que não alcança `localhost` diretamente).
4. Defina a variável de ambiente com a chave de API do Gemini antes de
   rodar o backend (necessária para o ADK processar as mensagens):
   ```bash
   export GOOGLE_API_KEY=sua-chave-aqui
   ```
5. Rode o backend:
   ```bash
   uvicorn zela.api.main:app --reload
   ```

**Nota:** o formato exato dos endpoints/payloads do WAHA usado no código
(`zela/integrations/waha_client.py`, `zela/api/webhook.py`) foi escrito a
partir de documentação/conhecimento geral sobre o projeto WAHA e pode
precisar de pequenos ajustes contra a versão específica da imagem Docker
usada — confira o Swagger da sua instância (`http://localhost:3000/`) se
as mensagens não chegarem como esperado.
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml README.md
git commit -m "docs: docker-compose do WAHA e instrucoes de setup"
```
