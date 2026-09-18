# Zela+ — Painel Streamlit (Plano 5 de 7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir o painel Streamlit da família previsto desde a spec original (seção 7) e ainda não implementado: status atual, histórico de medicação do dia, últimos alertas, gráfico de presença, e formulários de cadastro/edição de medicamentos e compromissos.

**Architecture:** O painel acessa o SQLite (`zela.db`) diretamente via `zela/storage/*`, sem nenhuma API HTTP nova — mesmo padrão já usado por `zela/api/scheduler.py` e `zela/agents/orchestrator.py`. Um pacote novo `zela/streamlit_app/` organiza o código em componentes isolados e testáveis: `autenticacao.py` (gate de senha), `secoes.py` (4 funções de renderização somente-leitura), `formularios.py` (2 formulários de escrita), e `app.py` (ponto de entrada, monta a página). Testes usam `streamlit.testing.v1.AppTest` — framework oficial de teste do Streamlit, execução real do script, sem mocks do próprio Streamlit.

**Tech Stack:** `streamlit` (novo, `1.64.0` verificado nesta máquina) e `pandas` (novo, trazido também transitivamente pelo streamlit, mas declarado explicitamente pois é usado diretamente no gráfico). SQLite (`sqlite3`, já usado no projeto inteiro).

**Spec:** `docs/superpowers/specs/2026-09-10-cuida-mais-agente-idoso-design.md` (seção 7 e, em detalhe, a nova seção 16).

## Global Constraints

- Python 3.11+, mesmas convenções dos Planos 1-4.
- **A camada `zela/domain/` não muda neste plano** — continua pura, sem I/O.
- **Acesso direto ao SQLite via `zela/storage/*`, sem API HTTP nova.**
- **Todas as funções de `secoes.py`, `formularios.py` e `autenticacao.py` recebem `conn`/parâmetros explícitos — nunca leem variáveis de ambiente ou constantes de caminho de banco diretamente.** Só `zela/streamlit_app/app.py` (o ponto de entrada real) lê `ZELA_DB_PATH` (fallback `"zela.db"`). Isso é o que permite testar cada peça isoladamente com `AppTest.from_string(...)` apontando para um banco de teste construído no próprio código da string, sem precisar mockar nada.
- **Testes usam `streamlit.testing.v1.AppTest`, real, sem mocks do Streamlit.** Padrões confirmados nesta máquina (`streamlit==1.64.0`):
  - Widgets de texto/número: `at.text_input[i].set_value(...)`, `at.number_input[i].set_value(...)`.
  - Seleção: `at.selectbox[i].set_value(...)` (aceita o valor real da opção, inclusive membros de enum), `at.multiselect[i].set_value([...])`.
  - Data/hora: `at.date_input[i].set_value(date(...))`, `at.time_input[i].set_value(time(...))` — ambos aceitam `value=None` no widget para o caso "novo registro, sem valor padrão".
  - Texto longo: `at.text_area[i].set_value(...)`.
  - Botões (inclusive `st.form_submit_button`, que aparece em `at.button`): `at.button[i].click().run()`.
  - `st.rerun()` funciona de forma transparente dentro de um único `.click().run()` — não precisa de uma segunda chamada a `.run()` para ver o estado pós-rerun.
  - `st.stop()` interrompe a execução do script sem gerar nenhuma exceção em `at.exception` — só os elementos renderizados antes do `st.stop()` aparecem.
  - Widgets fora de um `st.form(...)` (ex.: o seletor de "editar existente") reexecutam o script imediatamente ao mudar de valor — use `.set_value(...).run()` para eles. Widgets dentro de um `st.form(...)` só se aplicam quando o botão de submit é clicado — use `.set_value(...)` (sem `.run()`) em cada um, e só chame `.run()` uma vez, junto do clique no botão de submit.
  - Variáveis de ambiente definidas no processo de teste (`monkeypatch.setenv(...)`) são enxergadas normalmente pelo código executado via `AppTest` (mesmo processo, sem subprocess).
- **`Compromisso.data_hora` tem um validador Pydantic que rejeita datas no passado** (`zela/models/rotina.py`, já existente desde o Plano 2, nunca usado até agora). Isso é correto para **criar** um compromisso nunca (a família não deveria agendar algo no passado), mas quebraria a **leitura** de qualquer compromisso já registrado cuja data já passou — cada linha lida do banco reconstruiria um `Compromisso(...)`, e o validador rodaria de novo. `listar_compromissos` (Task 1) usa `Compromisso.model_construct(...)` (que pula toda validação) especificamente para reconstruir a partir do storage — `salvar_compromisso`/o formulário continuam construindo via `Compromisso(...)` normal, preservando a regra na criação.
- Nome do projeto: **Zela+**. Escopo de idoso único (`id_idoso = "idosa-1"`), mesma convenção dos planos anteriores.
- Novas dependências (`pyproject.toml`): `streamlit>=1.60,<2` e `pandas>=2.0,<3` (versões testadas nesta máquina: `streamlit==1.64.0`, `pandas==3.0.6` — o teto `<3` é intencional mesmo com uma versão 3.x já instalada aqui, para deixar explícito que versões futuras do pandas devem ser testadas antes de atualizar; ajuste o teto se necessário ao instalar).

---

## Mapa de arquivos deste plano

```
zela/
  storage/
    rotina.py                     # MODIFICADO: salvar_compromisso, listar_compromissos
  streamlit_app/                   # NOVO pacote
    __init__.py
    autenticacao.py                  # exigir_autenticacao (gate de senha via STREAMLIT_SENHA)
    secoes.py                         # renderizar_status, renderizar_medicacao,
                                       # renderizar_alertas, renderizar_grafico
    formularios.py                     # formulario_medicamento, formulario_compromisso
    app.py                               # ponto de entrada: streamlit run zela/streamlit_app/app.py
tests/
  test_storage_rotina.py             # MODIFICADO: testes de compromisso
  test_streamlit_autenticacao.py
  test_streamlit_secoes.py
  test_streamlit_formularios.py
  test_streamlit_app.py
pyproject.toml                        # MODIFICADO: streamlit, pandas
README.md                              # MODIFICADO: como rodar o painel
```

---

### Task 1: Storage de compromissos

**Files:**
- Modify: `zela/storage/rotina.py`
- Modify: `tests/test_storage_rotina.py`

**Interfaces:**
- Consumes: `zela.models.rotina.{Compromisso, TipoCompromisso}` (Plano 2, já existentes).
- Produces: `salvar_compromisso(conn, compromisso: Compromisso, idoso_id: str) -> None`; `listar_compromissos(conn, idoso_id: str) -> list[Compromisso]` (ordenado por `data_hora`).

- [ ] **Step 1: Escrever os testes que falham**

Adicione a `tests/test_storage_rotina.py` (o arquivo já importa `datetime`, `time`, `conectar` — adicione os imports novos abaixo junto aos existentes):

```python
# adicione a este import já existente no topo do arquivo:
# from zela.models.rotina import Dosagem, Medicamento
# troque por:
from zela.models.rotina import Compromisso, Dosagem, Medicamento, TipoCompromisso

# adicione a este import já existente:
# from zela.storage.rotina import (
#     aplicar_confirmacao,
#     aplicar_lembretes_pendentes,
#     listar_medicamentos,
#     salvar_medicamento,
# )
# troque por:
from zela.storage.rotina import (
    aplicar_confirmacao,
    aplicar_lembretes_pendentes,
    listar_compromissos,
    listar_medicamentos,
    salvar_compromisso,
    salvar_medicamento,
)

# adicione também no topo:
from datetime import timedelta
```

E adicione ao final do arquivo:

```python
def test_salvar_e_listar_compromisso_futuro():
    conn = conectar(":memory:")
    compromisso = Compromisso(
        id="comp-1",
        titulo="Consulta cardiologista",
        data_hora=datetime.now() + timedelta(days=1),
        local="Clínica Central",
        tipo=TipoCompromisso.CONSULTA,
    )

    salvar_compromisso(conn, compromisso, idoso_id="idosa-1")
    compromissos = listar_compromissos(conn, "idosa-1")

    assert len(compromissos) == 1
    assert compromissos[0].titulo == "Consulta cardiologista"
    assert compromissos[0].tipo == TipoCompromisso.CONSULTA
    assert compromissos[0].local == "Clínica Central"


def test_listar_compromisso_ja_passado_nao_levanta_erro():
    conn = conectar(":memory:")
    # Insere direto via SQL (não via Compromisso(...), que rejeitaria uma data
    # no passado) para simular um compromisso já registrado que já aconteceu.
    # listar_compromissos precisa conseguir reconstruí-lo sem levantar erro.
    conn.execute(
        "INSERT INTO compromisso (id, idoso_id, titulo, data_hora, local, tipo) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            "comp-2", "idosa-1", "Exame de sangue",
            (datetime.now() - timedelta(days=1)).isoformat(),
            "Laboratório X", "exame",
        ),
    )
    conn.commit()

    compromissos = listar_compromissos(conn, "idosa-1")

    assert len(compromissos) == 1
    assert compromissos[0].titulo == "Exame de sangue"
    assert compromissos[0].tipo == TipoCompromisso.EXAME


def test_salvar_compromisso_atualiza_existente():
    conn = conectar(":memory:")
    original = Compromisso(
        id="comp-3", titulo="Consulta", data_hora=datetime.now() + timedelta(days=1),
        local="Local A", tipo=TipoCompromisso.CONSULTA,
    )
    salvar_compromisso(conn, original, idoso_id="idosa-1")

    atualizado = Compromisso(
        id="comp-3", titulo="Consulta (remarcada)", data_hora=datetime.now() + timedelta(days=2),
        local="Local B", tipo=TipoCompromisso.CONSULTA,
    )
    salvar_compromisso(conn, atualizado, idoso_id="idosa-1")

    compromissos = listar_compromissos(conn, "idosa-1")

    assert len(compromissos) == 1
    assert compromissos[0].titulo == "Consulta (remarcada)"
    assert compromissos[0].local == "Local B"


def test_listar_compromissos_ordena_por_data_hora():
    conn = conectar(":memory:")
    salvar_compromisso(
        conn,
        Compromisso(
            id="comp-tarde", titulo="Compromisso à tarde",
            data_hora=datetime.now() + timedelta(days=2),
            local="Local", tipo=TipoCompromisso.OUTRO,
        ),
        idoso_id="idosa-1",
    )
    salvar_compromisso(
        conn,
        Compromisso(
            id="comp-cedo", titulo="Compromisso mais cedo",
            data_hora=datetime.now() + timedelta(days=1),
            local="Local", tipo=TipoCompromisso.OUTRO,
        ),
        idoso_id="idosa-1",
    )

    compromissos = listar_compromissos(conn, "idosa-1")

    assert [c.id for c in compromissos] == ["comp-cedo", "comp-tarde"]
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_storage_rotina.py -v`
Expected: FAIL — `ImportError: cannot import name 'salvar_compromisso'`

- [ ] **Step 3: Implementar em `zela/storage/rotina.py`**

Atualize o import de `zela.models.rotina` no topo do arquivo (adicione `Compromisso` e `TipoCompromisso` à lista já existente):

```python
from zela.models.rotina import (
    CanalConfirmacao,
    Compromisso,
    ConfirmacaoMedicacao,
    Dosagem,
    Medicamento,
    StatusConfirmacao,
    TipoCompromisso,
)
```

Adicione ao final do arquivo:

```python
def salvar_compromisso(conn: sqlite3.Connection, compromisso: Compromisso, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO compromisso (id, idoso_id, titulo, data_hora, local, tipo)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            titulo = excluded.titulo,
            data_hora = excluded.data_hora,
            local = excluded.local,
            tipo = excluded.tipo
        """,
        (
            compromisso.id,
            idoso_id,
            compromisso.titulo,
            compromisso.data_hora.isoformat(),
            compromisso.local,
            compromisso.tipo.value,
        ),
    )
    conn.commit()


def _linha_para_compromisso(linha: sqlite3.Row) -> Compromisso:
    # model_construct pula a validação Pydantic (inclusive o validador que
    # rejeita data_hora no passado) — correto aqui porque um compromisso já
    # registrado pode legitimamente estar no passado, e reconstruí-lo a
    # partir do storage não deve falhar por causa disso. A validação
    # continua valendo normalmente na criação, via Compromisso(...) direto.
    return Compromisso.model_construct(
        id=linha["id"],
        titulo=linha["titulo"],
        data_hora=datetime.fromisoformat(linha["data_hora"]),
        local=linha["local"],
        tipo=TipoCompromisso(linha["tipo"]),
    )


def listar_compromissos(conn: sqlite3.Connection, idoso_id: str) -> list[Compromisso]:
    linhas = conn.execute(
        "SELECT * FROM compromisso WHERE idoso_id = ? ORDER BY data_hora", (idoso_id,)
    ).fetchall()
    return [_linha_para_compromisso(linha) for linha in linhas]
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_storage_rotina.py -v`
Expected: PASS (9 testes: 5 pré-existentes + 4 novos)

- [ ] **Step 5: Rodar a suíte completa (checagem de regressão)**

Run: `pytest -q`
Expected: todos os testes continuam passando.

- [ ] **Step 6: Commit**

```bash
git add zela/storage/rotina.py tests/test_storage_rotina.py
git commit -m "feat: adiciona storage de compromissos"
```

---

### Task 2: Autenticação por senha

**Files:**
- Create: `zela/streamlit_app/__init__.py`
- Create: `zela/streamlit_app/autenticacao.py`
- Create: `tests/test_streamlit_autenticacao.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `streamlit` (novo, via `import streamlit as st`).
- Produces: `exigir_autenticacao() -> bool` — mostra um campo de senha (se necessário) e retorna `True` somente se a família já está autenticada nesta sessão do navegador.

- [ ] **Step 1: Adicionar as dependências em `pyproject.toml`**

Adicione `"streamlit>=1.60,<2",` e `"pandas>=2.0,<3",` à lista `dependencies`.

- [ ] **Step 2: Criar o pacote e escrever os testes que falham**

Crie `zela/streamlit_app/__init__.py` com conteúdo **completamente vazio** (0 bytes).

```python
# tests/test_streamlit_autenticacao.py
from streamlit.testing.v1 import AppTest

_CODIGO_TESTE = """
import streamlit as st
from zela.streamlit_app.autenticacao import exigir_autenticacao

if exigir_autenticacao():
    st.write("liberado")
"""


def test_exigir_autenticacao_bloqueia_sem_variavel_de_ambiente(monkeypatch):
    monkeypatch.delenv("STREAMLIT_SENHA", raising=False)

    at = AppTest.from_string(_CODIGO_TESTE)
    at.run()

    assert at.exception == []
    assert any("STREAMLIT_SENHA" in erro.value for erro in at.error)
    assert at.markdown == []


def test_exigir_autenticacao_bloqueia_senha_errada(monkeypatch):
    monkeypatch.setenv("STREAMLIT_SENHA", "correta123")

    at = AppTest.from_string(_CODIGO_TESTE)
    at.run()
    at.text_input[0].set_value("errada").run()

    assert at.exception == []
    assert any("incorreta" in aviso.value.lower() for aviso in at.warning)
    assert at.markdown == []


def test_exigir_autenticacao_libera_com_senha_certa(monkeypatch):
    monkeypatch.setenv("STREAMLIT_SENHA", "correta123")

    at = AppTest.from_string(_CODIGO_TESTE)
    at.run()
    at.text_input[0].set_value("correta123").run()

    assert at.exception == []
    assert [m.value for m in at.markdown] == ["liberado"]


def test_exigir_autenticacao_mantem_liberado_apos_novo_run(monkeypatch):
    monkeypatch.setenv("STREAMLIT_SENHA", "correta123")

    at = AppTest.from_string(_CODIGO_TESTE)
    at.run()
    at.text_input[0].set_value("correta123").run()
    at.run()  # simula uma nova reexecução do script na mesma sessão

    assert at.exception == []
    assert [m.value for m in at.markdown] == ["liberado"]
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

Run: `pip install -e .` (instala `streamlit`/`pandas`)
Run: `pytest tests/test_streamlit_autenticacao.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.streamlit_app.autenticacao'`

- [ ] **Step 4: Implementar `autenticacao.py`**

```python
# zela/streamlit_app/autenticacao.py
import os

import streamlit as st

VARIAVEL_SENHA = "STREAMLIT_SENHA"


def exigir_autenticacao() -> bool:
    """Mostra um campo de senha e retorna True se a família já está autenticada nesta sessão.

    Recusa funcionar (retorna False e mostra um erro) se a variável de
    ambiente STREAMLIT_SENHA não estiver configurada — evita rodar o painel
    sem nenhuma senha por esquecimento.
    """
    senha_esperada = os.environ.get(VARIAVEL_SENHA)
    if not senha_esperada:
        st.error(
            f"Variável de ambiente {VARIAVEL_SENHA} não configurada. "
            "Defina uma senha antes de rodar o painel."
        )
        return False

    if st.session_state.get("autenticado"):
        return True

    senha_informada = st.text_input("Senha", type="password")
    if senha_informada == "":
        return False
    if senha_informada == senha_esperada:
        st.session_state["autenticado"] = True
        return True

    st.warning("Senha incorreta.")
    return False
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_streamlit_autenticacao.py -v`
Expected: PASS (4 testes)

- [ ] **Step 6: Commit**

```bash
git add zela/streamlit_app/__init__.py zela/streamlit_app/autenticacao.py tests/test_streamlit_autenticacao.py pyproject.toml
git commit -m "feat: adiciona gate de autenticacao por senha ao painel Streamlit"
```

---

### Task 3: Seção — Status atual

**Files:**
- Create: `zela/streamlit_app/secoes.py`
- Create: `tests/test_streamlit_secoes.py`

**Interfaces:**
- Consumes: `zela.storage.monitoramento.aplicar_classificacao` (Plano 3).
- Produces: `renderizar_status(conn, idoso_id: str) -> None`.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_streamlit_secoes.py
from datetime import datetime

from streamlit.testing.v1 import AppTest

from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura
from zela.storage.db import conectar
from zela.storage.monitoramento import salvar_leitura


def test_renderizar_status_mostra_classificacao_normal(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conn = conectar(caminho)
    salvar_leitura(
        conn,
        LeituraSensor(
            fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA,
            valor=1, unidade="bool", timestamp=datetime.now(),
        ),
        idoso_id="idosa-1",
    )

    codigo = f"""
from zela.storage.db import conectar
from zela.streamlit_app.secoes import renderizar_status

conn = conectar({caminho!r})
renderizar_status(conn, "idosa-1")
"""
    at = AppTest.from_string(codigo)
    at.run()

    assert at.exception == []
    assert [m.value for m in at.metric] == ["NORMAL"]
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `pytest tests/test_streamlit_secoes.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.streamlit_app.secoes'`

- [ ] **Step 3: Implementar `secoes.py`**

```python
# zela/streamlit_app/secoes.py
from datetime import datetime

import streamlit as st

from zela.storage.monitoramento import aplicar_classificacao


def renderizar_status(conn, idoso_id: str) -> None:
    st.subheader("Status atual")
    evento = aplicar_classificacao(conn, idoso_id, datetime.now())
    st.metric("Status", evento.status.value.upper())
    st.caption(evento.motivo)
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `pytest tests/test_streamlit_secoes.py -v`
Expected: PASS (1 teste)

- [ ] **Step 5: Commit**

```bash
git add zela/streamlit_app/secoes.py tests/test_streamlit_secoes.py
git commit -m "feat: adiciona secao de status atual ao painel Streamlit"
```

---

### Task 4: Seção — Medicação do dia

**Files:**
- Modify: `zela/streamlit_app/secoes.py`
- Modify: `tests/test_streamlit_secoes.py`

**Interfaces:**
- Consumes: `zela.storage.rotina.{listar_medicamentos, listar_confirmacoes_do_dia, salvar_confirmacao}` (Planos 1/2).
- Produces: `renderizar_medicacao(conn, idoso_id: str) -> None`.

- [ ] **Step 1: Escrever o teste que falha**

Adicione a `tests/test_streamlit_secoes.py` (adicione os imports novos ao topo, junto aos já existentes):

```python
from datetime import time

from zela.models.rotina import CanalConfirmacao, ConfirmacaoMedicacao, Dosagem, Medicamento, StatusConfirmacao
from zela.storage.rotina import salvar_confirmacao, salvar_medicamento
```

E ao final do arquivo:

```python
def test_renderizar_medicacao_mostra_confirmacoes_do_dia(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conn = conectar(caminho)
    salvar_medicamento(
        conn,
        Medicamento(
            id="med-1", nome="Losartana",
            dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
        ),
        idoso_id="idosa-1",
    )
    agora = datetime.now().replace(hour=8, minute=5, second=0, microsecond=0)
    salvar_confirmacao(
        conn,
        ConfirmacaoMedicacao(
            medicamento_id="med-1", horario_previsto=agora, horario_confirmado=agora,
            status=StatusConfirmacao.CONFIRMADO, canal=CanalConfirmacao.WHATSAPP,
        ),
    )

    codigo = f"""
from zela.storage.db import conectar
from zela.streamlit_app.secoes import renderizar_medicacao

conn = conectar({caminho!r})
renderizar_medicacao(conn, "idosa-1")
"""
    at = AppTest.from_string(codigo)
    at.run()

    assert at.exception == []
    textos = [m.value for m in at.markdown]
    assert any("Losartana" in t and "confirmado" in t for t in textos)


def test_renderizar_medicacao_sem_confirmacoes_mostra_mensagem(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conectar(caminho)  # garante que o schema existe

    codigo = f"""
from zela.storage.db import conectar
from zela.streamlit_app.secoes import renderizar_medicacao

conn = conectar({caminho!r})
renderizar_medicacao(conn, "idosa-1")
"""
    at = AppTest.from_string(codigo)
    at.run()

    assert at.exception == []
    assert any("Nenhum registro" in m.value for m in at.markdown)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_streamlit_secoes.py -v`
Expected: FAIL — `ImportError: cannot import name 'renderizar_medicacao'`

- [ ] **Step 3: Implementar em `secoes.py`**

Adicione o import ao topo do arquivo (mantenha o import já existente de `aplicar_classificacao`):

```python
from zela.storage.rotina import listar_confirmacoes_do_dia, listar_medicamentos
```

E adicione a função ao final do arquivo:

```python
def renderizar_medicacao(conn, idoso_id: str) -> None:
    st.subheader("Medicação de hoje")
    agora = datetime.now()
    medicamentos = {m.id: m for m in listar_medicamentos(conn, idoso_id)}
    confirmacoes = listar_confirmacoes_do_dia(conn, idoso_id, agora)
    if not confirmacoes:
        st.write("Nenhum registro de medicação hoje ainda.")
        return
    for confirmacao in confirmacoes:
        medicamento = medicamentos.get(confirmacao.medicamento_id)
        nome = medicamento.nome if medicamento else confirmacao.medicamento_id
        horario = confirmacao.horario_previsto.strftime("%H:%M")
        st.write(f"{nome} — {horario} — {confirmacao.status.value}")
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_streamlit_secoes.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
git add zela/streamlit_app/secoes.py tests/test_streamlit_secoes.py
git commit -m "feat: adiciona secao de medicacao do dia ao painel Streamlit"
```

---

### Task 5: Seção — Últimos alertas

**Files:**
- Modify: `zela/streamlit_app/secoes.py`
- Modify: `tests/test_streamlit_secoes.py`

**Interfaces:**
- Consumes: `zela.storage.alertas.listar_alertas` (Plano 3).
- Produces: `renderizar_alertas(conn, idoso_id: str) -> None`.

- [ ] **Step 1: Escrever o teste que falha**

Adicione a `tests/test_streamlit_secoes.py` (imports novos ao topo):

```python
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.storage.alertas import salvar_alerta
```

E ao final do arquivo:

```python
def test_renderizar_alertas_mostra_ultimos_alertas(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conn = conectar(caminho)
    salvar_alerta(
        conn,
        Alerta(
            nivel=NivelAlerta.CRITICO, destinatario="João", canal=CanalAlerta.WHATSAPP,
            mensagem="Sem resposta, notificando família.", timestamp=datetime(2026, 9, 18, 10, 0),
        ),
        idoso_id="idosa-1",
    )

    codigo = f"""
from zela.storage.db import conectar
from zela.streamlit_app.secoes import renderizar_alertas

conn = conectar({caminho!r})
renderizar_alertas(conn, "idosa-1")
"""
    at = AppTest.from_string(codigo)
    at.run()

    assert at.exception == []
    assert any("Sem resposta, notificando família." in m.value for m in at.markdown)


def test_renderizar_alertas_sem_alertas_mostra_mensagem(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conectar(caminho)

    codigo = f"""
from zela.storage.db import conectar
from zela.streamlit_app.secoes import renderizar_alertas

conn = conectar({caminho!r})
renderizar_alertas(conn, "idosa-1")
"""
    at = AppTest.from_string(codigo)
    at.run()

    assert at.exception == []
    assert any("Nenhum alerta" in m.value for m in at.markdown)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_streamlit_secoes.py -v`
Expected: FAIL — `ImportError: cannot import name 'renderizar_alertas'`

- [ ] **Step 3: Implementar em `secoes.py`**

Adicione o import ao topo:

```python
from zela.storage.alertas import listar_alertas
```

E ao final do arquivo:

```python
MAXIMO_ALERTAS_EXIBIDOS = 10


def renderizar_alertas(conn, idoso_id: str) -> None:
    st.subheader("Últimos alertas")
    alertas = listar_alertas(conn, idoso_id)
    if not alertas:
        st.write("Nenhum alerta registrado.")
        return
    for alerta in reversed(alertas[-MAXIMO_ALERTAS_EXIBIDOS:]):
        data_hora = alerta.timestamp.strftime("%d/%m %H:%M")
        st.write(f"[{alerta.nivel.value.upper()}] {data_hora} — {alerta.mensagem}")
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_streamlit_secoes.py -v`
Expected: PASS (5 testes)

- [ ] **Step 5: Commit**

```bash
git add zela/streamlit_app/secoes.py tests/test_streamlit_secoes.py
git commit -m "feat: adiciona secao de ultimos alertas ao painel Streamlit"
```

---

### Task 6: Seção — Gráfico de presença

**Files:**
- Modify: `zela/streamlit_app/secoes.py`
- Modify: `tests/test_streamlit_secoes.py`

**Interfaces:**
- Consumes: `zela.storage.monitoramento.listar_leituras_recentes` (Plano 3), `pandas` (novo).
- Produces: `renderizar_grafico(conn, idoso_id: str) -> None`.

- [ ] **Step 1: Escrever o teste que falha**

Adicione ao final de `tests/test_streamlit_secoes.py` (nenhum import novo necessário — `LeituraSensor`, `FonteSensor`, `TipoLeitura`, `salvar_leitura`, `datetime` já estão importados no arquivo desde a Task 3):

```python
def test_renderizar_grafico_mostra_leituras_de_presenca(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conn = conectar(caminho)
    salvar_leitura(
        conn,
        LeituraSensor(
            fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA,
            valor=1, unidade="bool", timestamp=datetime.now(),
        ),
        idoso_id="idosa-1",
    )

    codigo = f"""
from zela.storage.db import conectar
from zela.streamlit_app.secoes import renderizar_grafico

conn = conectar({caminho!r})
renderizar_grafico(conn, "idosa-1")
"""
    at = AppTest.from_string(codigo)
    at.run()

    assert at.exception == []
    assert not any("Nenhuma leitura" in m.value for m in at.markdown)


def test_renderizar_grafico_sem_leituras_mostra_mensagem(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conectar(caminho)

    codigo = f"""
from zela.storage.db import conectar
from zela.streamlit_app.secoes import renderizar_grafico

conn = conectar({caminho!r})
renderizar_grafico(conn, "idosa-1")
"""
    at = AppTest.from_string(codigo)
    at.run()

    assert at.exception == []
    assert any("Nenhuma leitura" in m.value for m in at.markdown)
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_streamlit_secoes.py -v`
Expected: FAIL — `ImportError: cannot import name 'renderizar_grafico'`

- [ ] **Step 3: Implementar em `secoes.py`**

Adicione os imports ao topo (mantenha os já existentes):

```python
import pandas as pd

from zela.models.monitoramento import TipoLeitura
from zela.storage.monitoramento import listar_leituras_recentes
```

E ao final do arquivo:

```python
def renderizar_grafico(conn, idoso_id: str) -> None:
    st.subheader("Atividade de hoje")
    inicio_do_dia = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    leituras = listar_leituras_recentes(conn, idoso_id, inicio_do_dia)
    leituras_presenca = [l for l in leituras if l.tipo == TipoLeitura.PRESENCA]
    if not leituras_presenca:
        st.write("Nenhuma leitura de presença hoje ainda.")
        return
    dados = pd.DataFrame(
        {"presença": [l.valor for l in leituras_presenca]},
        index=[l.timestamp for l in leituras_presenca],
    )
    st.line_chart(dados)
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_streamlit_secoes.py -v`
Expected: PASS (7 testes)

- [ ] **Step 5: Rodar a suíte completa (checagem de regressão)**

Run: `pytest -q`
Expected: todos os testes continuam passando.

- [ ] **Step 6: Commit**

```bash
git add zela/streamlit_app/secoes.py tests/test_streamlit_secoes.py
git commit -m "feat: adiciona grafico de presenca ao painel Streamlit"
```

---

### Task 7: Formulário — Medicamento

**Files:**
- Create: `zela/streamlit_app/formularios.py`
- Create: `tests/test_streamlit_formularios.py`

**Interfaces:**
- Consumes: `zela.storage.rotina.{listar_medicamentos, salvar_medicamento}` (Planos 1/2/4), `zela.models.rotina.{Medicamento, Dosagem}`.
- Produces: `formulario_medicamento(conn, idoso_id: str) -> None`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_streamlit_formularios.py
from datetime import time

from streamlit.testing.v1 import AppTest

from zela.models.rotina import Dosagem, Medicamento
from zela.storage.db import conectar
from zela.storage.rotina import listar_medicamentos, salvar_medicamento

_CODIGO_MEDICAMENTO = """
from zela.storage.db import conectar
from zela.streamlit_app.formularios import formulario_medicamento

conn = conectar({caminho!r})
formulario_medicamento(conn, "idosa-1")
"""


def test_formulario_medicamento_cria_novo(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conectar(caminho)  # garante que o schema existe

    at = AppTest.from_string(_CODIGO_MEDICAMENTO.format(caminho=caminho))
    at.run()

    at.text_input[0].set_value("Losartana")
    at.number_input[0].set_value(50.0)
    at.text_input[1].set_value("mg")
    at.time_input[0].set_value(time(8, 0))
    at.multiselect[0].set_value([0, 1, 2, 3, 4])
    at.button[0].click().run()

    assert at.exception == []
    medicamentos = listar_medicamentos(conectar(caminho), "idosa-1")
    assert len(medicamentos) == 1
    assert medicamentos[0].nome == "Losartana"
    assert medicamentos[0].dosagem.quantidade == 50.0
    assert medicamentos[0].dosagem.unidade == "mg"
    assert medicamentos[0].dias_semana == [0, 1, 2, 3, 4]


def test_formulario_medicamento_edita_existente(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conn = conectar(caminho)
    salvar_medicamento(
        conn,
        Medicamento(
            id="med-1", nome="Losartana",
            dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
        ),
        idoso_id="idosa-1",
    )

    at = AppTest.from_string(_CODIGO_MEDICAMENTO.format(caminho=caminho))
    at.run()

    at.selectbox[0].set_value("Losartana").run()
    at.number_input[0].set_value(100.0)
    at.button[0].click().run()

    assert at.exception == []
    medicamentos = listar_medicamentos(conectar(caminho), "idosa-1")
    assert len(medicamentos) == 1
    assert medicamentos[0].id == "med-1"
    assert medicamentos[0].dosagem.quantidade == 100.0


def test_formulario_medicamento_erro_de_validacao_e_exibido(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conectar(caminho)

    at = AppTest.from_string(_CODIGO_MEDICAMENTO.format(caminho=caminho))
    at.run()

    # Dosagem.quantidade exige > 0 (Field(gt=0), em zela/models/rotina.py) —
    # mas o widget st.number_input(min_value=0.0) aceita 0.0 normalmente
    # (min_value é inclusivo), então 0.0 chega até o Medicamento(...) e é
    # rejeitado ali por um ValueError real do Pydantic, não simulado.
    at.text_input[0].set_value("Losartana")
    at.number_input[0].set_value(0.0)
    at.text_input[1].set_value("mg")
    at.button[0].click().run()

    assert at.exception == []
    assert len(at.error) >= 1
    medicamentos = listar_medicamentos(conectar(caminho), "idosa-1")
    assert medicamentos == []
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_streamlit_formularios.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.streamlit_app.formularios'`

- [ ] **Step 3: Implementar `formularios.py`**

```python
# zela/streamlit_app/formularios.py
import uuid

import streamlit as st

from zela.models.rotina import Dosagem, Medicamento
from zela.storage.rotina import listar_medicamentos, salvar_medicamento


def formulario_medicamento(conn, idoso_id: str) -> None:
    st.subheader("Cadastrar ou editar medicamento")
    medicamentos = listar_medicamentos(conn, idoso_id)
    opcoes = ["Novo medicamento"] + [m.nome for m in medicamentos]
    escolha = st.selectbox("Medicamento", opcoes, key="medicamento_selecionado")

    medicamento_existente = None
    if escolha != "Novo medicamento":
        medicamento_existente = next(m for m in medicamentos if m.nome == escolha)

    with st.form("form_medicamento"):
        nome = st.text_input(
            "Nome", value=medicamento_existente.nome if medicamento_existente else ""
        )
        quantidade = st.number_input(
            "Quantidade da dose", min_value=0.0,
            value=medicamento_existente.dosagem.quantidade if medicamento_existente else 1.0,
        )
        unidade = st.text_input(
            "Unidade (ex.: mg, comprimido)",
            value=medicamento_existente.dosagem.unidade if medicamento_existente else "",
        )
        horario = st.time_input(
            "Horário",
            value=medicamento_existente.horarios[0] if medicamento_existente else None,
        )
        dias_semana = st.multiselect(
            "Dias da semana (0=segunda ... 6=domingo)",
            options=list(range(7)),
            default=medicamento_existente.dias_semana if medicamento_existente else list(range(7)),
        )
        bula = st.text_area(
            "Bula/instruções (opcional)",
            value=(medicamento_existente.bula or "") if medicamento_existente else "",
        )
        enviado = st.form_submit_button("Salvar")

    if not enviado:
        return

    try:
        medicamento = Medicamento(
            id=medicamento_existente.id if medicamento_existente else str(uuid.uuid4()),
            nome=nome,
            dosagem=Dosagem(quantidade=quantidade, unidade=unidade),
            horarios=[horario],
            dias_semana=dias_semana,
            bula=bula or None,
        )
        salvar_medicamento(conn, medicamento, idoso_id)
        st.success(f"Medicamento '{nome}' salvo com sucesso.")
        st.rerun()
    except Exception as exc:
        st.error(f"Não foi possível salvar: {exc}")
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_streamlit_formularios.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
git add zela/streamlit_app/formularios.py tests/test_streamlit_formularios.py
git commit -m "feat: adiciona formulario de cadastro/edicao de medicamento"
```

---

### Task 8: Formulário — Compromisso

**Files:**
- Modify: `zela/streamlit_app/formularios.py`
- Modify: `tests/test_streamlit_formularios.py`

**Interfaces:**
- Consumes: `zela.storage.rotina.{listar_compromissos, salvar_compromisso}` (Task 1), `zela.models.rotina.{Compromisso, TipoCompromisso}`.
- Produces: `formulario_compromisso(conn, idoso_id: str) -> None`.

- [ ] **Step 1: Escrever os testes que falham**

Adicione a `tests/test_streamlit_formularios.py` (imports novos ao topo, junto aos já existentes):

```python
from datetime import date, datetime, timedelta

from zela.models.rotina import Compromisso, TipoCompromisso
from zela.storage.rotina import listar_compromissos, salvar_compromisso
```

E ao final do arquivo:

```python
_CODIGO_COMPROMISSO = """
from zela.storage.db import conectar
from zela.streamlit_app.formularios import formulario_compromisso

conn = conectar({caminho!r})
formulario_compromisso(conn, "idosa-1")
"""


def test_formulario_compromisso_cria_novo(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conectar(caminho)

    at = AppTest.from_string(_CODIGO_COMPROMISSO.format(caminho=caminho))
    at.run()

    at.text_input[0].set_value("Consulta cardiologista")
    amanha = date.today() + timedelta(days=1)
    at.date_input[0].set_value(amanha)
    at.time_input[0].set_value(datetime.now().time().replace(second=0, microsecond=0))
    at.text_input[1].set_value("Clínica Central")
    at.selectbox[1].set_value(TipoCompromisso.CONSULTA)
    at.button[0].click().run()

    assert at.exception == []
    compromissos = listar_compromissos(conectar(caminho), "idosa-1")
    assert len(compromissos) == 1
    assert compromissos[0].titulo == "Consulta cardiologista"
    assert compromissos[0].tipo == TipoCompromisso.CONSULTA
    assert compromissos[0].local == "Clínica Central"


def test_formulario_compromisso_edita_existente(tmp_path):
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
    at.text_input[1].set_value("Laboratório Y")
    at.button[0].click().run()

    assert at.exception == []
    compromissos = listar_compromissos(conectar(caminho), "idosa-1")
    assert len(compromissos) == 1
    assert compromissos[0].id == "comp-1"
    assert compromissos[0].local == "Laboratório Y"
```

Note: neste teste, `at.selectbox[0]` é o seletor de "qual compromisso editar" e `at.selectbox[1]` é o campo "Tipo" dentro do formulário — a ordem segue a ordem em que os widgets aparecem no script (o seletor de edição vem antes do `st.form`, o campo Tipo vem dentro dele).

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_streamlit_formularios.py -v`
Expected: FAIL — `ImportError: cannot import name 'formulario_compromisso'`

- [ ] **Step 3: Implementar em `formularios.py`**

Adicione os imports ao topo (mantenha os já existentes):

```python
from datetime import datetime

from zela.models.rotina import Compromisso, TipoCompromisso
from zela.storage.rotina import listar_compromissos, salvar_compromisso
```

E ao final do arquivo:

```python
def formulario_compromisso(conn, idoso_id: str) -> None:
    st.subheader("Cadastrar ou editar compromisso")
    compromissos = listar_compromissos(conn, idoso_id)
    opcoes = ["Novo compromisso"] + [c.titulo for c in compromissos]
    escolha = st.selectbox("Compromisso", opcoes, key="compromisso_selecionado")

    compromisso_existente = None
    if escolha != "Novo compromisso":
        compromisso_existente = next(c for c in compromissos if c.titulo == escolha)

    with st.form("form_compromisso"):
        titulo = st.text_input(
            "Título", value=compromisso_existente.titulo if compromisso_existente else ""
        )
        data = st.date_input(
            "Data", value=compromisso_existente.data_hora.date() if compromisso_existente else None
        )
        horario = st.time_input(
            "Horário", value=compromisso_existente.data_hora.time() if compromisso_existente else None
        )
        local = st.text_input(
            "Local", value=compromisso_existente.local if compromisso_existente else ""
        )
        tipos = list(TipoCompromisso)
        indice_padrao = tipos.index(compromisso_existente.tipo) if compromisso_existente else 0
        tipo = st.selectbox("Tipo", tipos, format_func=lambda t: t.value, index=indice_padrao)
        enviado = st.form_submit_button("Salvar")

    if not enviado:
        return

    try:
        compromisso = Compromisso(
            id=compromisso_existente.id if compromisso_existente else str(uuid.uuid4()),
            titulo=titulo,
            data_hora=datetime.combine(data, horario),
            local=local,
            tipo=tipo,
        )
        salvar_compromisso(conn, compromisso, idoso_id)
        st.success(f"Compromisso '{titulo}' salvo com sucesso.")
        st.rerun()
    except Exception as exc:
        st.error(f"Não foi possível salvar: {exc}")
```

(`uuid` já está importado no topo do arquivo desde a Task 7.)

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_streamlit_formularios.py -v`
Expected: PASS (5 testes)

- [ ] **Step 5: Rodar a suíte completa (checagem de regressão)**

Run: `pytest -q`
Expected: todos os testes continuam passando.

- [ ] **Step 6: Commit**

```bash
git add zela/streamlit_app/formularios.py tests/test_streamlit_formularios.py
git commit -m "feat: adiciona formulario de cadastro/edicao de compromisso"
```

---

### Task 9: Ponto de entrada + README

**Files:**
- Create: `zela/streamlit_app/app.py`
- Create: `tests/test_streamlit_app.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: tudo das Tasks 1-8.
- Produces: aplicação Streamlit completa, executável via `streamlit run zela/streamlit_app/app.py`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_streamlit_app.py
from streamlit.testing.v1 import AppTest


def test_app_bloqueia_sem_senha_configurada(monkeypatch, tmp_path):
    monkeypatch.setenv("ZELA_DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.delenv("STREAMLIT_SENHA", raising=False)

    at = AppTest.from_file("../zela/streamlit_app/app.py")
    at.run()

    assert at.exception == []
    assert any("STREAMLIT_SENHA" in erro.value for erro in at.error)
    assert at.metric == []


def test_app_renderiza_secoes_apos_autenticacao(monkeypatch, tmp_path):
    monkeypatch.setenv("ZELA_DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("STREAMLIT_SENHA", "segredo123")

    at = AppTest.from_file("../zela/streamlit_app/app.py")
    at.run()
    at.text_input[0].set_value("segredo123").run()

    assert at.exception == []
    assert len(at.metric) == 1  # seção de status atual
    assert len(at.subheader) >= 4  # status, medicação, alertas, gráfico (+ formulários)
```

Nota: `AppTest.from_file` resolve caminhos relativos a partir do diretório do
arquivo que faz a chamada (`tests/`), não do diretório de onde o `pytest`
é executado — por isso `"../zela/streamlit_app/app.py"` e não
`"zela/streamlit_app/app.py"` (confirmado empiricamente nesta máquina).

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_streamlit_app.py -v`
Expected: FAIL — `FileNotFoundError` (o arquivo `zela/streamlit_app/app.py` ainda não existe)

- [ ] **Step 3: Implementar `app.py`**

```python
# zela/streamlit_app/app.py
import os

import streamlit as st

from zela.storage.db import conectar
from zela.streamlit_app.autenticacao import exigir_autenticacao
from zela.streamlit_app.formularios import formulario_compromisso, formulario_medicamento
from zela.streamlit_app.secoes import (
    renderizar_alertas,
    renderizar_grafico,
    renderizar_medicacao,
    renderizar_status,
)

CAMINHO_DB = os.environ.get("ZELA_DB_PATH", "zela.db")
ID_IDOSO = "idosa-1"

st.set_page_config(page_title="Zela+ — Painel da Família", page_icon="🩺")
st.title("Zela+ — Painel da Família")

if not exigir_autenticacao():
    st.stop()

conn = conectar(CAMINHO_DB)

renderizar_status(conn, ID_IDOSO)
renderizar_medicacao(conn, ID_IDOSO)
renderizar_alertas(conn, ID_IDOSO)
renderizar_grafico(conn, ID_IDOSO)

st.divider()

formulario_medicamento(conn, ID_IDOSO)
formulario_compromisso(conn, ID_IDOSO)
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_streamlit_app.py -v`
Expected: PASS (2 testes)

- [ ] **Step 5: Atualizar o README**

Adicione ao `README.md` uma seção "Painel Streamlit (Plano 5)":

```markdown
## Painel Streamlit (Plano 5)

O painel da família mostra o status atual, a medicação do dia, os últimos
alertas e um gráfico de presença, além de formulários para cadastrar ou
editar medicamentos e compromissos.

1. Defina uma senha de acesso (obrigatória — o painel recusa subir sem ela):
   ```bash
   export STREAMLIT_SENHA=sua-senha-aqui
   ```
2. Rode o painel (com o backend já rodando, para os dados existirem):
   ```bash
   streamlit run zela/streamlit_app/app.py
   ```
3. Abra `http://localhost:8501` no navegador e digite a senha.

**Nota:** a senha é única e compartilhada (não é um sistema de contas por
usuário) — suficiente para o MVP, mas não deve ser considerado um controle
de acesso robusto se o painel for exposto além da rede local/doméstica.
```

Adicione também `zela/streamlit_app/` à lista da seção "## Estrutura do código":

```markdown
- `zela/streamlit_app/` — painel Streamlit da família (status, medicação,
  alertas, gráfico de presença, cadastro de medicamentos e compromissos).
```

- [ ] **Step 6: Rodar a suíte completa**

Run: `pytest -q`
Expected: todos os testes passam (pré-existentes + novos deste plano).

- [ ] **Step 7: Commit**

```bash
git add zela/streamlit_app/app.py tests/test_streamlit_app.py README.md
git commit -m "feat: adiciona ponto de entrada do painel Streamlit"
```
