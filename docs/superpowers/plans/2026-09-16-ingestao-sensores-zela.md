# Zela+ — Ingestão de Sensores e Detecção de Risco (Plano 3 de 7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ligar os agentes de Monitoramento e Emergência (deixados sem ferramentas desde o Plano 1) a dados reais de sensor: ingestão HTTP do ESP32 (presença) e do smartwatch (via app "Health Connect Webhook"), um ciclo determinístico de classificação de risco + escalonamento rodando no scheduler, e ferramentas ADK para a família consultar o status pelo WhatsApp.

**Architecture:** Três novos repositórios SQLite (`monitoramento`, `escalonamento`, `alertas` — schema já existe desde o Plano 2) fazem a ponte entre o banco e as funções puras de `zela/domain/` (Plano 1, inalteradas). Um novo módulo `zela/api/ingestao.py` recebe leituras via HTTP. Um novo job no scheduler roda a classificação e o escalonamento periodicamente, chamando as funções de domínio diretamente — **o LLM nunca decide se há risco**; ele só responde a perguntas sobre o status já calculado, via novas ferramentas ADK nos agentes de Monitoramento e Emergência. O webhook do WhatsApp (Plano 2) ganha suporte a múltiplos números permitidos, para a família também poder consultar o agente.

**Tech Stack:** Python 3.11+, FastAPI, SQLite (`sqlite3`), APScheduler (todos já instalados desde o Plano 2). Firmware ESP32 em C++/Arduino (fora da suíte de testes Python).

**Spec:** `docs/superpowers/specs/2026-09-10-cuida-mais-agente-idoso-design.md` (seção 14 detalha este plano).

## Global Constraints

- Python 3.11+, mesmas convenções dos Planos 1 e 2.
- **A camada `zela/domain/` não muda neste plano** — continua pura, sem I/O.
- **A decisão de risco é 100% determinística**: o job do scheduler chama `classificar_por_regra` e `decidir_proxima_acao` (domínio, Plano 1) diretamente. O LLM (agentes ADK de Monitoramento/Emergência) só consulta resultados já calculados — nunca decide se há risco nem se deve escalar.
- **Nenhum teste automatizado pode exigir um ESP32 real, um app "Health Connect Webhook" real, nem acesso de rede.** O endpoint de ingestão é testado com payloads fabricados; o firmware do ESP32 não tem teste automatizado (não é Python) — é verificado manualmente, documentado no README (mesmo tratamento dado ao `docker-compose.yml` do WAHA no Plano 2).
- **Risco real de API (payload do "Health Connect Webhook"):** o formato exato do payload não foi verificado contra uma instância real do app. A task de ingestão tem uma nota explícita de verificação — mesmo tratamento dado ao WAHA e ao ADK Runner no Plano 2.
- `Alerta.destinatario` guarda um **nome** (não um telefone) — o job do scheduler precisa resolver nome → telefone (via `perfil.nome`/`perfil.telefone` ou `contato.nome`/`contato.telefone`) antes de enviar pelo WAHA. Um alerta com `simulado=True` nunca é enviado por WhatsApp de verdade (só registrado).
- Nome do projeto: **Zela+**. Escopo de idoso único (`id_idoso = "idosa-1"`), mesma convenção dos planos anteriores.

---

## Mapa de arquivos deste plano

```
zela/
  storage/
    monitoramento.py    # CRUD LeituraSensor + aplicar_classificacao (com "sem dados")
    escalonamento.py     # get/save EstadoEscalonamento + aplicar_escalonamento
    alertas.py            # CRUD de Alerta (adiado desde o Plano 2)
  api/
    ingestao.py            # POST /ingest/esp32, POST /ingest/health-connect
    scheduler.py             # MODIFICADO: novo job verificar_e_escalonar_riscos
    webhook.py                # MODIFICADO: telefone_idoso -> telefones_permitidos (list)
    main.py                    # MODIFICADO: inclui roteador de ingestão, lista de permissão com família
  agents/
    orchestrator.py              # MODIFICADO: agente_monitoramento e agente_emergencia ganham tools=[...]
firmware/
  zela_presenca/
    zela_presenca.ino             # firmware ESP32 (HC-SR04 -> POST /ingest/esp32), sem teste automatizado
tests/
  test_storage_monitoramento.py
  test_storage_escalonamento.py
  test_storage_alertas.py
  test_api_ingestao.py
  test_api_scheduler.py                    # MODIFICADO: novos testes do job de risco
  test_api_webhook.py                       # MODIFICADO: telefones_permitidos (lista)
  test_api_main.py                           # MODIFICADO: novas rotas de ingestão
  test_agents_orchestrator_tools_monitoramento.py
README.md                                    # MODIFICADO: setup do Health Connect Webhook, wiring/flash do ESP32
```

---

### Task 1: Storage — repositório de monitoramento (leituras de sensor)

**Files:**
- Create: `zela/storage/monitoramento.py`
- Test: `tests/test_storage_monitoramento.py`

**Interfaces:**
- Consumes: `zela.domain.monitoramento.classificar_por_regra` (Plano 1), `zela.models.monitoramento.*`, `zela.storage.db.conectar`.
- Produces: `salvar_leitura(conn, leitura: LeituraSensor, idoso_id: str) -> None`, `listar_leituras_recentes(conn, idoso_id, desde: datetime) -> list[LeituraSensor]`, `aplicar_classificacao(conn, idoso_id, agora: datetime, janela_horas: float = 48.0) -> EventoMonitoramento`.

`aplicar_classificacao` implementa o requisito da spec (seção 10) de gerar um alerta distinto de "sem dados" quando o sensor de presença para de reportar — se nenhuma leitura de presença existir na janela de lookback (`janela_horas`, padrão 48h — generosa o bastante para nunca esconder o limite de 6h de `classificar_por_regra`), retorna `ATENCAO` com motivo explícito de falta de dados, em vez de deixar cair silenciosamente em `NORMAL`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_storage_monitoramento.py
from datetime import datetime, timedelta

from zela.models.monitoramento import (
    FonteSensor,
    StatusMonitoramento,
    TipoLeitura,
)
from zela.models.monitoramento import LeituraSensor
from zela.storage.db import conectar
from zela.storage.monitoramento import (
    aplicar_classificacao,
    listar_leituras_recentes,
    salvar_leitura,
)


def test_salvar_e_listar_leituras_recentes():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 10, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora,
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    leituras = listar_leituras_recentes(conn, "idosa-1", desde=agora - timedelta(hours=1))

    assert len(leituras) == 1
    assert leituras[0].tipo == TipoLeitura.PRESENCA
    assert leituras[0].fonte == FonteSensor.ESP32


def test_listar_leituras_recentes_exclui_leituras_antigas():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 10, 0)
    leitura_antiga = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora - timedelta(hours=30),
    )
    salvar_leitura(conn, leitura_antiga, idoso_id="idosa-1")

    leituras = listar_leituras_recentes(conn, "idosa-1", desde=agora - timedelta(hours=24))

    assert leituras == []


def test_aplicar_classificacao_risco_por_ausencia_de_presenca():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora - timedelta(hours=8),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    evento = aplicar_classificacao(conn, "idosa-1", agora)

    assert evento.status == StatusMonitoramento.RISCO


def test_aplicar_classificacao_normal_com_presenca_recente():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora - timedelta(minutes=30),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    evento = aplicar_classificacao(conn, "idosa-1", agora)

    assert evento.status == StatusMonitoramento.NORMAL


def test_aplicar_classificacao_sem_leituras_de_presenca_na_janela_e_atencao():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)
    # nenhuma leitura salva — simula ESP32 que nunca reportou ou parou há muito tempo

    evento = aplicar_classificacao(conn, "idosa-1", agora)

    assert evento.status == StatusMonitoramento.ATENCAO
    assert "sem" in evento.motivo.lower() or "nenhuma" in evento.motivo.lower()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_storage_monitoramento.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.storage.monitoramento'`

- [ ] **Step 3: Implementar `zela/storage/monitoramento.py`**

```python
import sqlite3
from datetime import datetime, timedelta

from zela.domain.monitoramento import classificar_por_regra
from zela.models.monitoramento import (
    EventoMonitoramento,
    FonteSensor,
    MetodoClassificacao,
    StatusMonitoramento,
    TipoLeitura,
)
from zela.models.monitoramento import LeituraSensor

JANELA_LOOKBACK_HORAS = 48.0


def salvar_leitura(conn: sqlite3.Connection, leitura: LeituraSensor, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO leitura_sensor (idoso_id, fonte, tipo, valor, unidade, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            idoso_id,
            leitura.fonte.value,
            leitura.tipo.value,
            leitura.valor,
            leitura.unidade,
            leitura.timestamp.isoformat(),
        ),
    )
    conn.commit()


def listar_leituras_recentes(
    conn: sqlite3.Connection, idoso_id: str, desde: datetime
) -> list[LeituraSensor]:
    linhas = conn.execute(
        "SELECT * FROM leitura_sensor WHERE idoso_id = ? AND timestamp >= ? ORDER BY timestamp",
        (idoso_id, desde.isoformat()),
    ).fetchall()
    return [
        LeituraSensor(
            fonte=FonteSensor(linha["fonte"]),
            tipo=TipoLeitura(linha["tipo"]),
            valor=linha["valor"],
            unidade=linha["unidade"],
            timestamp=datetime.fromisoformat(linha["timestamp"]),
        )
        for linha in linhas
    ]


def aplicar_classificacao(
    conn: sqlite3.Connection,
    idoso_id: str,
    agora: datetime,
    janela_horas: float = JANELA_LOOKBACK_HORAS,
) -> EventoMonitoramento:
    desde = agora - timedelta(hours=janela_horas)
    leituras = listar_leituras_recentes(conn, idoso_id, desde)

    tem_leitura_presenca = any(l.tipo == TipoLeitura.PRESENCA for l in leituras)
    if not tem_leitura_presenca:
        return EventoMonitoramento(
            status=StatusMonitoramento.ATENCAO,
            motivo=(
                f"Nenhuma leitura de presença recebida nas últimas "
                f"{janela_horas:.0f}h — possível falha do sensor ou da conexão"
            ),
            timestamp=agora,
            metodo_classificacao=MetodoClassificacao.REGRA,
        )

    return classificar_por_regra(leituras, agora)
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_storage_monitoramento.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add zela/storage/monitoramento.py tests/test_storage_monitoramento.py
git commit -m "feat: repositorio SQLite de leituras de sensor e classificacao de risco"
```

---

### Task 2: Storage — repositório de escalonamento

**Files:**
- Create: `zela/storage/escalonamento.py`
- Test: `tests/test_storage_escalonamento.py`

**Interfaces:**
- Consumes: `zela.domain.emergencia.{EstadoEscalonamento, EstagioEscalonamento, decidir_proxima_acao}` (Plano 1), `zela.models.alertas.Alerta`, `zela.models.perfil.PerfilIdoso`.
- Produces: `obter_estado(conn, idoso_id) -> EstadoEscalonamento`, `salvar_estado(conn, idoso_id, estado: EstadoEscalonamento) -> None`, `aplicar_escalonamento(conn, idoso_id, evento: EventoMonitoramento, perfil: PerfilIdoso, agora) -> list[Alerta]`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_storage_escalonamento.py
from datetime import datetime

from zela.domain.emergencia import EstadoEscalonamento, EstagioEscalonamento
from zela.models.monitoramento import EventoMonitoramento, MetodoClassificacao, StatusMonitoramento
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.storage.db import conectar
from zela.storage.escalonamento import aplicar_escalonamento, obter_estado, salvar_estado


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511900000000",
        data_nascimento=datetime(1945, 3, 12).date(),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def test_obter_estado_sem_registro_retorna_ocioso():
    conn = conectar(":memory:")

    estado = obter_estado(conn, "idosa-1")

    assert estado.estagio == EstagioEscalonamento.OCIOSO
    assert estado.iniciado_em is None


def test_salvar_e_obter_estado():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)

    salvar_estado(
        conn, "idosa-1",
        EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=agora),
    )
    estado = obter_estado(conn, "idosa-1")

    assert estado.estagio == EstagioEscalonamento.CONTATO_IDOSO
    assert estado.iniciado_em == agora


def test_salvar_estado_atualiza_registro_existente():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)
    salvar_estado(conn, "idosa-1", EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=agora))

    salvar_estado(conn, "idosa-1", EstadoEscalonamento(estagio=EstagioEscalonamento.RESOLVIDO))

    estado = obter_estado(conn, "idosa-1")
    assert estado.estagio == EstagioEscalonamento.RESOLVIDO
    assert estado.iniciado_em is None


def test_aplicar_escalonamento_persiste_novo_estado_e_retorna_alertas():
    conn = conectar(":memory:")
    agora = datetime(2026, 9, 16, 14, 0)
    evento = EventoMonitoramento(
        status=StatusMonitoramento.RISCO,
        motivo="Sem movimentação detectada há 8.0h",
        timestamp=agora,
        metodo_classificacao=MetodoClassificacao.REGRA,
    )

    alertas = aplicar_escalonamento(conn, "idosa-1", evento, _perfil(), agora)

    assert len(alertas) == 1
    assert alertas[0].destinatario == "Maria da Silva"
    estado_persistido = obter_estado(conn, "idosa-1")
    assert estado_persistido.estagio == EstagioEscalonamento.CONTATO_IDOSO
    assert estado_persistido.iniciado_em == agora
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_storage_escalonamento.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.storage.escalonamento'`

- [ ] **Step 3: Implementar `zela/storage/escalonamento.py`**

```python
import sqlite3
from datetime import datetime

from zela.domain.emergencia import EstadoEscalonamento, EstagioEscalonamento, decidir_proxima_acao
from zela.models.alertas import Alerta
from zela.models.monitoramento import EventoMonitoramento
from zela.models.perfil import PerfilIdoso


def obter_estado(conn: sqlite3.Connection, idoso_id: str) -> EstadoEscalonamento:
    linha = conn.execute(
        "SELECT * FROM estado_escalonamento WHERE idoso_id = ?", (idoso_id,)
    ).fetchone()
    if linha is None:
        return EstadoEscalonamento()
    return EstadoEscalonamento(
        estagio=EstagioEscalonamento(linha["estagio"]),
        iniciado_em=datetime.fromisoformat(linha["iniciado_em"]) if linha["iniciado_em"] else None,
    )


def salvar_estado(conn: sqlite3.Connection, idoso_id: str, estado: EstadoEscalonamento) -> None:
    conn.execute(
        """
        INSERT INTO estado_escalonamento (idoso_id, estagio, iniciado_em)
        VALUES (?, ?, ?)
        ON CONFLICT(idoso_id) DO UPDATE SET
            estagio = excluded.estagio,
            iniciado_em = excluded.iniciado_em
        """,
        (
            idoso_id,
            estado.estagio.value,
            estado.iniciado_em.isoformat() if estado.iniciado_em else None,
        ),
    )
    conn.commit()


def aplicar_escalonamento(
    conn: sqlite3.Connection,
    idoso_id: str,
    evento: EventoMonitoramento,
    perfil: PerfilIdoso,
    agora: datetime,
) -> list[Alerta]:
    estado_atual = obter_estado(conn, idoso_id)
    novo_estado, alertas = decidir_proxima_acao(evento, perfil, estado_atual, agora)
    salvar_estado(conn, idoso_id, novo_estado)
    return alertas
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_storage_escalonamento.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add zela/storage/escalonamento.py tests/test_storage_escalonamento.py
git commit -m "feat: repositorio SQLite de estado de escalonamento"
```

---

### Task 3: Storage — repositório de alertas

**Files:**
- Create: `zela/storage/alertas.py`
- Test: `tests/test_storage_alertas.py`

**Interfaces:**
- Consumes: `zela.models.alertas.{Alerta, CanalAlerta, NivelAlerta, StatusAlerta}` (o campo `Alerta.simulado` já existe desde o Plano 1).
- Produces: `salvar_alerta(conn, alerta: Alerta, idoso_id: str) -> None`, `listar_alertas(conn, idoso_id: str) -> list[Alerta]`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_storage_alertas.py
from datetime import datetime

from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.storage.alertas import listar_alertas, salvar_alerta
from zela.storage.db import conectar


def test_salvar_e_listar_alertas():
    conn = conectar(":memory:")
    alerta = Alerta(
        nivel=NivelAlerta.CRITICO,
        destinatario="João",
        canal=CanalAlerta.WHATSAPP,
        mensagem="Sem resposta.",
        timestamp=datetime(2026, 9, 16, 14, 20),
    )

    salvar_alerta(conn, alerta, idoso_id="idosa-1")
    alertas = listar_alertas(conn, "idosa-1")

    assert len(alertas) == 1
    assert alertas[0].destinatario == "João"
    assert alertas[0].simulado is False


def test_salvar_alerta_simulado_preserva_a_flag():
    conn = conectar(":memory:")
    alerta = Alerta(
        nivel=NivelAlerta.CRITICO,
        destinatario="servico_emergencia_simulado",
        canal=CanalAlerta.WHATSAPP,
        mensagem="[SIMULAÇÃO] ...",
        simulado=True,
        timestamp=datetime(2026, 9, 16, 14, 30),
    )

    salvar_alerta(conn, alerta, idoso_id="idosa-1")
    alertas = listar_alertas(conn, "idosa-1")

    assert alertas[0].simulado is True


def test_listar_alertas_ordena_por_timestamp():
    conn = conectar(":memory:")
    tarde = Alerta(
        nivel=NivelAlerta.INFO, destinatario="A", canal=CanalAlerta.WHATSAPP,
        mensagem="segundo", timestamp=datetime(2026, 9, 16, 12, 0),
    )
    manha = Alerta(
        nivel=NivelAlerta.INFO, destinatario="A", canal=CanalAlerta.WHATSAPP,
        mensagem="primeiro", timestamp=datetime(2026, 9, 16, 8, 0),
    )
    salvar_alerta(conn, tarde, idoso_id="idosa-1")
    salvar_alerta(conn, manha, idoso_id="idosa-1")

    alertas = listar_alertas(conn, "idosa-1")

    assert [a.mensagem for a in alertas] == ["primeiro", "segundo"]
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_storage_alertas.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.storage.alertas'`

- [ ] **Step 3: Implementar `zela/storage/alertas.py`**

```python
import sqlite3
from datetime import datetime

from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta, StatusAlerta


def salvar_alerta(conn: sqlite3.Connection, alerta: Alerta, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO alerta (idoso_id, nivel, destinatario, canal, mensagem, status, simulado, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            idoso_id,
            alerta.nivel.value,
            alerta.destinatario,
            alerta.canal.value,
            alerta.mensagem,
            alerta.status.value,
            int(alerta.simulado),
            alerta.timestamp.isoformat(),
        ),
    )
    conn.commit()


def listar_alertas(conn: sqlite3.Connection, idoso_id: str) -> list[Alerta]:
    linhas = conn.execute(
        "SELECT * FROM alerta WHERE idoso_id = ? ORDER BY timestamp", (idoso_id,)
    ).fetchall()
    return [
        Alerta(
            nivel=NivelAlerta(linha["nivel"]),
            destinatario=linha["destinatario"],
            canal=CanalAlerta(linha["canal"]),
            mensagem=linha["mensagem"],
            status=StatusAlerta(linha["status"]),
            simulado=bool(linha["simulado"]),
            timestamp=datetime.fromisoformat(linha["timestamp"]),
        )
        for linha in linhas
    ]
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_storage_alertas.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add zela/storage/alertas.py tests/test_storage_alertas.py
git commit -m "feat: repositorio SQLite de alertas"
```

---

### Task 4: Ingestão HTTP (ESP32 + Health Connect) e montagem no app

**Files:**
- Create: `zela/api/ingestao.py`
- Modify: `zela/api/main.py`
- Test: `tests/test_api_ingestao.py`
- Modify: `tests/test_api_main.py`

**Interfaces:**
- Produces: `montar_roteador_ingestao(salvar_leitura, id_idoso: str = "idosa-1") -> APIRouter`, expondo `POST /ingest/esp32` e `POST /ingest/health-connect`. `salvar_leitura` é injetado (padrão de DI já usado em `webhook.py`) — assinatura `(leitura: LeituraSensor, idoso_id: str) -> None`.

**Risco real de API (payload do "Health Connect Webhook"):** o formato assumido abaixo (`{"value": ..., "unit": ..., "timestamp": ...}`) é uma suposição razoável, **não verificada** contra uma instância real do app (Play Store, `com.hcwebhook.app`). Antes de usar em produção, configure o app de verdade, aponte o webhook para este endpoint, dispare uma sincronização manual e confira o JSON recebido de fato — ajuste `receber_health_connect` conforme necessário. A suíte de testes usa payloads fabricados e não depende do formato real estar certo.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_api_ingestao.py
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zela.api.ingestao import montar_roteador_ingestao
from zela.models.monitoramento import FonteSensor, TipoLeitura


class _ArmazenamentoFalso:
    def __init__(self):
        self.salvas = []

    def salvar(self, leitura, idoso_id):
        self.salvas.append((leitura, idoso_id))


def test_ingest_esp32_salva_leitura_de_presenca():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post("/ingest/esp32", json={"valor": 1, "timestamp": "2026-09-16T10:00:00"})

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "recebido"}
    assert len(armazenamento.salvas) == 1
    leitura, idoso_id = armazenamento.salvas[0]
    assert leitura.fonte == FonteSensor.ESP32
    assert leitura.tipo == TipoLeitura.PRESENCA
    assert leitura.valor == 1
    assert idoso_id == "idosa-1"


def test_ingest_esp32_payload_invalido_retorna_400():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post("/ingest/esp32", json={"timestamp": "nao-e-uma-data"})

    assert resposta.status_code == 400
    assert armazenamento.salvas == []


def test_ingest_health_connect_salva_leitura_de_frequencia_cardiaca():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/ingest/health-connect",
        json={"value": 72, "unit": "bpm", "timestamp": "2026-09-16T10:00:00"},
    )

    assert resposta.status_code == 200
    leitura, idoso_id = armazenamento.salvas[0]
    assert leitura.fonte == FonteSensor.SMARTWATCH
    assert leitura.tipo == TipoLeitura.FREQUENCIA_CARDIACA
    assert leitura.valor == 72
    assert leitura.unidade == "bpm"


def test_ingest_health_connect_payload_invalido_retorna_400():
    armazenamento = _ArmazenamentoFalso()
    app = FastAPI()
    app.include_router(montar_roteador_ingestao(armazenamento.salvar))
    cliente = TestClient(app)

    resposta = cliente.post("/ingest/health-connect", json={})

    assert resposta.status_code == 400
    assert armazenamento.salvas == []
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_api_ingestao.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.api.ingestao'`

- [ ] **Step 3: Implementar `zela/api/ingestao.py`**

```python
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura

_ID_IDOSO_PADRAO = "idosa-1"


def montar_roteador_ingestao(salvar_leitura, id_idoso: str = _ID_IDOSO_PADRAO) -> APIRouter:
    roteador = APIRouter()

    @roteador.post("/ingest/esp32")
    async def receber_esp32(request: Request):
        corpo = await request.json()
        try:
            leitura = LeituraSensor(
                fonte=FonteSensor.ESP32,
                tipo=TipoLeitura.PRESENCA,
                valor=corpo["valor"],
                unidade="deteccao",
                timestamp=datetime.fromisoformat(corpo["timestamp"]),
            )
        except (ValidationError, KeyError, ValueError) as erro:
            return JSONResponse(status_code=400, content={"status": "erro", "detalhe": str(erro)})
        salvar_leitura(leitura, id_idoso)
        return {"status": "recebido"}

    @roteador.post("/ingest/health-connect")
    async def receber_health_connect(request: Request):
        corpo = await request.json()
        try:
            leitura = LeituraSensor(
                fonte=FonteSensor.SMARTWATCH,
                tipo=TipoLeitura.FREQUENCIA_CARDIACA,
                valor=float(corpo["value"]),
                unidade=corpo.get("unit", "bpm"),
                timestamp=datetime.fromisoformat(corpo["timestamp"]),
            )
        except (ValidationError, KeyError, ValueError) as erro:
            return JSONResponse(status_code=400, content={"status": "erro", "detalhe": str(erro)})
        salvar_leitura(leitura, id_idoso)
        return {"status": "recebido"}

    return roteador
```

- [ ] **Step 4: Rodar os testes de ingestão e confirmar que passam**

Run: `pytest tests/test_api_ingestao.py -v`
Expected: 4 passed

- [ ] **Step 5: Atualizar `tests/test_api_main.py`** — no teste existente `test_app_inclui_rota_de_webhook` (que hoje faz `caminhos = set(app.openapi()["paths"]); assert "/webhook/whatsapp" in caminhos`), adicione as duas novas rotas à asserção:

```python
    assert "/webhook/whatsapp" in caminhos
    assert "/ingest/esp32" in caminhos
    assert "/ingest/health-connect" in caminhos
```

- [ ] **Step 6: Rodar `tests/test_api_main.py` e confirmar que falha (rotas novas ainda não montadas)**

Run: `pytest tests/test_api_main.py -v`
Expected: FAIL — `/ingest/esp32` e `/ingest/health-connect` não estão em `caminhos`

- [ ] **Step 7: Modificar `zela/api/main.py`** para montar o roteador de ingestão. Adicione aos imports existentes:

```python
from zela.api.ingestao import montar_roteador_ingestao
from zela.storage.monitoramento import salvar_leitura as salvar_leitura_sensor
```

Adicione, antes da definição de `app = FastAPI(...)`:

```python
def _salvar_leitura(leitura, idoso_id: str) -> None:
    conexao = conectar(CAMINHO_DB)
    salvar_leitura_sensor(conexao, leitura, idoso_id)
```

E adicione a segunda chamada de `include_router` logo após a existente:

```python
app.include_router(montar_roteador_ingestao(_salvar_leitura, id_idoso=ID_IDOSO))
```

- [ ] **Step 8: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_main.py tests/test_api_ingestao.py -v`
Expected: todos passam

- [ ] **Step 9: Rodar a suíte completa**

Run: `pytest -q`
Expected: todos os testes passam (76 anteriores + os novos desta task)

- [ ] **Step 10: Commit**

```bash
git add zela/api/ingestao.py zela/api/main.py tests/test_api_ingestao.py tests/test_api_main.py
git commit -m "feat: endpoints de ingestao HTTP (ESP32 e Health Connect)"
```

---

### Task 5: Scheduler — job de detecção de risco e escalonamento

**Files:**
- Modify: `zela/api/scheduler.py`
- Modify: `tests/test_api_scheduler.py`

**Interfaces:**
- Consumes: `zela.storage.monitoramento.aplicar_classificacao` (Task 1), `zela.storage.escalonamento.aplicar_escalonamento` (Task 2), `zela.storage.alertas.salvar_alerta` (Task 3), `zela.storage.perfil.obter_perfil` (Plano 2).
- Produces: `verificar_e_escalonar_riscos(caminho_db: str, id_idoso: str, waha_client) -> list[Alerta]`. `iniciar_scheduler` passa a agendar também este job (a cada `INTERVALO_MONITORAMENTO_MINUTOS`).

Esta função resolve o problema de `Alerta.destinatario` guardar um **nome**, não um telefone (`perfil.nome`/`contato.nome`) — mapeia o nome de volta para o telefone certo antes de enviar pelo WAHA, e nunca envia um alerta `simulado=True` de verdade.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_api_scheduler.py`, troque a primeira linha do arquivo (hoje
`from datetime import date, time`) para incluir também `datetime`:

```python
from datetime import date, datetime, time
```

Adicione os seguintes imports novos logo abaixo dos imports existentes
(mantenha os imports e testes já existentes no arquivo intactos):

```python
from zela.domain.emergencia import EstagioEscalonamento
from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura
from zela.storage.escalonamento import obter_estado
from zela.storage.monitoramento import salvar_leitura


def test_verificar_e_escalonar_riscos_risco_envia_para_a_idosa(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=datetime(2026, 9, 16, 6, 0),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    class _DatetimeFixo:
        @staticmethod
        def now():
            return datetime(2026, 9, 16, 14, 0)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    waha_falso = _WahaFalso()
    alertas = verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)

    assert len(alertas) == 1
    assert waha_falso.enviados == [("+5511911111111", alertas[0].mensagem)]
    assert obter_estado(conn, "idosa-1").estagio == EstagioEscalonamento.CONTATO_IDOSO


def test_verificar_e_escalonar_riscos_normal_nao_envia_nada(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")

    class _DatetimeFixo:
        @staticmethod
        def now():
            return datetime(2026, 9, 16, 14, 0)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=datetime(2026, 9, 16, 13, 45),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    waha_falso = _WahaFalso()
    alertas = verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)

    assert alertas == []
    assert waha_falso.enviados == []


def test_verificar_e_escalonar_riscos_sem_perfil_retorna_lista_vazia(tmp_path):
    caminho_db = str(tmp_path / "teste.db")
    conectar(caminho_db)

    waha_falso = _WahaFalso()
    alertas = verificar_e_escalonar_riscos(caminho_db, "nao-existe", waha_falso)

    assert alertas == []
```

Adicione o import de `verificar_e_escalonar_riscos` (e `datetime`, se ainda não importado no topo do arquivo) ao topo de `tests/test_api_scheduler.py`, junto ao import existente de `verificar_e_enviar_lembretes`:

```python
from zela.api.scheduler import verificar_e_enviar_lembretes, verificar_e_escalonar_riscos
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_api_scheduler.py -v`
Expected: FAIL — `ImportError: cannot import name 'verificar_e_escalonar_riscos'`

- [ ] **Step 3: Modificar `zela/api/scheduler.py`**

Adicione aos imports existentes no topo do arquivo:

```python
from zela.models.alertas import Alerta
from zela.models.monitoramento import EventoMonitoramento
from zela.models.perfil import PerfilIdoso
from zela.storage.alertas import salvar_alerta
from zela.storage.escalonamento import aplicar_escalonamento
from zela.storage.monitoramento import aplicar_classificacao
```

Adicione a constante, junto a `INTERVALO_MINUTOS`:

```python
INTERVALO_MONITORAMENTO_MINUTOS = 15
```

Adicione as novas funções (após `verificar_e_enviar_lembretes`, antes de `iniciar_scheduler`):

```python
def _telefone_por_nome(perfil: PerfilIdoso, nome: str) -> str | None:
    if nome == perfil.nome:
        return perfil.telefone
    for contato in perfil.contatos_familiares:
        if contato.nome == nome:
            return contato.telefone
    return None


def verificar_e_escalonar_riscos(caminho_db: str, id_idoso: str, waha_client) -> list[Alerta]:
    conn = conectar(caminho_db)
    perfil = obter_perfil(conn, id_idoso)
    if perfil is None:
        return []

    agora = datetime.now()
    evento: EventoMonitoramento = aplicar_classificacao(conn, id_idoso, agora)
    alertas = aplicar_escalonamento(conn, id_idoso, evento, perfil, agora)

    for alerta in alertas:
        salvar_alerta(conn, alerta, id_idoso)
        if alerta.simulado:
            continue
        telefone = _telefone_por_nome(perfil, alerta.destinatario)
        if telefone is not None:
            waha_client.enviar_texto(telefone, alerta.mensagem)

    return alertas
```

Modifique `iniciar_scheduler` para agendar também este job:

```python
def iniciar_scheduler(caminho_db: str, id_idoso: str, waha_client) -> BackgroundScheduler:
    agendador = BackgroundScheduler()
    agendador.add_job(
        verificar_e_enviar_lembretes,
        "interval",
        minutes=INTERVALO_MINUTOS,
        args=[caminho_db, id_idoso, waha_client],
        id="verificar_lembretes",
    )
    agendador.add_job(
        verificar_e_escalonar_riscos,
        "interval",
        minutes=INTERVALO_MONITORAMENTO_MINUTOS,
        args=[caminho_db, id_idoso, waha_client],
        id="verificar_riscos",
    )
    agendador.start()
    return agendador
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_scheduler.py -v`
Expected: todos passam (os 3 testes existentes do Plano 2 + os 3 novos)

- [ ] **Step 5: Rodar a suíte completa**

Run: `pytest -q`
Expected: todos os testes passam

- [ ] **Step 6: Commit**

```bash
git add zela/api/scheduler.py tests/test_api_scheduler.py
git commit -m "feat: job de deteccao de risco e escalonamento no scheduler"
```

---

### Task 6: Webhook — lista de permissão com múltiplos números

O Plano 2 restringiu o webhook a um único `telefone_idoso`. Agora a família também precisa poder mandar mensagem (para consultar o status — ver Task 7). Esta task generaliza para uma lista.

**Files:**
- Modify: `zela/api/webhook.py`
- Modify: `zela/api/main.py`
- Modify: `tests/test_api_webhook.py`

**Interfaces:**
- Produces (alterado): `montar_roteador(processar_mensagem, waha_client, id_idoso="idosa-1", telefones_permitidos: list[str] | None = None) -> APIRouter` — substitui o parâmetro `telefone_idoso: str | None`.

- [ ] **Step 1: Atualizar os testes existentes em `tests/test_api_webhook.py`**

Nos dois testes que hoje usam `telefone_idoso="+5511911111111"` (`test_webhook_ignora_numero_fora_da_lista_permitida` e `test_webhook_processa_numero_da_lista_permitida`), troque o argumento para `telefones_permitidos=["+5511911111111"]` (lista com um item — mesmo comportamento de antes).

Adicione um novo teste ao final do arquivo, provando que um SEGUNDO número (o de um familiar) também é aceito quando está na lista:

```python
def test_webhook_aceita_numero_de_familiar_quando_ha_mais_de_um_permitido():
    waha_falso = _WahaFalso()

    def processar_falso(id_idoso, texto, agora):
        return "A vovó está bem hoje."

    app = FastAPI()
    app.include_router(
        montar_roteador(
            processar_falso, waha_falso,
            telefones_permitidos=["+5511911111111", "+5511987654321"],
        )
    )
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={
            "event": "message",
            "payload": {"from": "5511987654321@c.us", "body": "como ela está?", "fromMe": False},
        },
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "processado"}
    assert waha_falso.enviados == [("+5511987654321", "A vovó está bem hoje.")]
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_api_webhook.py -v`
Expected: FAIL — `montar_roteador() got an unexpected keyword argument 'telefones_permitidos'`

- [ ] **Step 3: Modificar `zela/api/webhook.py`**

Troque a assinatura de `montar_roteador`:

```python
def montar_roteador(
    processar_mensagem,
    waha_client,
    id_idoso: str = _ID_IDOSO_PADRAO,
    telefones_permitidos: list[str] | None = None,
) -> APIRouter:
```

E troque a checagem dentro de `receber_mensagem`:

```python
        if telefones_permitidos is not None and telefone not in telefones_permitidos:
            return {"status": "ignorado"}
```

- [ ] **Step 4: Modificar `zela/api/main.py`**

Troque a função `_obter_telefone_idoso` e a constante `_TELEFONE_IDOSO`:

```python
def _obter_telefones_permitidos() -> list[str] | None:
    conexao = conectar(CAMINHO_DB)
    perfil = obter_perfil(conexao, ID_IDOSO)
    if perfil is None:
        return None
    return [perfil.telefone] + [c.telefone for c in perfil.contatos_familiares]


_TELEFONES_PERMITIDOS = _obter_telefones_permitidos()
```

E a chamada de `montar_roteador` no `include_router`:

```python
app.include_router(
    montar_roteador(_processar, waha_client, id_idoso=ID_IDOSO, telefones_permitidos=_TELEFONES_PERMITIDOS)
)
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_webhook.py tests/test_api_main.py -v`
Expected: todos passam

- [ ] **Step 6: Rodar a suíte completa**

Run: `pytest -q`
Expected: todos os testes passam

- [ ] **Step 7: Commit**

```bash
git add zela/api/webhook.py zela/api/main.py tests/test_api_webhook.py
git commit -m "feat: webhook aceita lista de numeros permitidos (idosa + familia)"
```

---

### Task 7: Ferramentas ADK — Agente de Monitoramento e Agente de Emergência

**Files:**
- Modify: `zela/agents/orchestrator.py`
- Test: `tests/test_agents_orchestrator_tools_monitoramento.py`

**Interfaces:**
- Consumes: `zela.storage.monitoramento.aplicar_classificacao` (Task 1), `zela.storage.alertas.listar_alertas` (Task 3).
- Produces: `consultar_status_atual(idoso_id: str, agora_iso: str) -> dict`, `consultar_historico_alertas(idoso_id: str) -> list[dict]`; `montar_agente_monitoramento` e `montar_agente_emergencia` passam a usar `tools=[...]`.

**Nota:** esta task só toca `montar_agente_monitoramento` e `montar_agente_emergencia` — `montar_agente_rotina`, `montar_agente_comunicacao` e `montar_orquestrador` não mudam.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_agents_orchestrator_tools_monitoramento.py
from datetime import datetime, timedelta

from zela.agents.orchestrator import (
    consultar_historico_alertas,
    consultar_status_atual,
    montar_agente_emergencia,
    montar_agente_monitoramento,
)
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.models.monitoramento import FonteSensor, LeituraSensor, StatusMonitoramento, TipoLeitura
from zela.storage.alertas import salvar_alerta
from zela.storage.db import conectar
from zela.storage.monitoramento import salvar_leitura


def test_agente_monitoramento_tem_uma_ferramenta(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    agente = montar_agente_monitoramento()

    assert len(agente.tools) == 1


def test_consultar_status_atual_reflete_leituras_reais(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    conn = conectar(banco)
    agora = datetime(2026, 9, 16, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=agora - timedelta(hours=8),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    resultado = consultar_status_atual("idosa-1", agora.isoformat())

    assert resultado["status"] == StatusMonitoramento.RISCO.value


def test_consultar_status_atual_com_data_invalida_retorna_erro(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    resultado = consultar_status_atual("idosa-1", "nao-e-uma-data")

    assert "erro" in resultado


def test_agente_emergencia_tem_uma_ferramenta(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    agente = montar_agente_emergencia()

    assert len(agente.tools) == 1


def test_consultar_historico_alertas_retorna_alertas_persistidos(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    conn = conectar(banco)
    alerta = Alerta(
        nivel=NivelAlerta.CRITICO, destinatario="João", canal=CanalAlerta.WHATSAPP,
        mensagem="Sem resposta.", timestamp=datetime(2026, 9, 16, 14, 0),
    )
    salvar_alerta(conn, alerta, idoso_id="idosa-1")

    resultado = consultar_historico_alertas("idosa-1")

    assert len(resultado) == 1
    assert resultado[0]["destinatario"] == "João"


def test_consultar_historico_alertas_sem_alertas_retorna_lista_vazia(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr("zela.agents.orchestrator._CAMINHO_DB", banco)

    resultado = consultar_historico_alertas("idosa-1")

    assert resultado == []
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_agents_orchestrator_tools_monitoramento.py -v`
Expected: FAIL — `ImportError: cannot import name 'consultar_status_atual'`

- [ ] **Step 3: Modificar `zela/agents/orchestrator.py`**

Adicione aos imports existentes:

```python
from zela.storage.alertas import listar_alertas
from zela.storage.monitoramento import aplicar_classificacao
```

Adicione as duas novas funções de ferramenta (após `confirmar_medicamento`, antes de `montar_agente_rotina`):

```python
def consultar_status_atual(idoso_id: str, agora_iso: str) -> dict:
    """Retorna o status de monitoramento mais recente do idoso (normal, atenção ou risco) e o motivo."""
    try:
        agora = datetime.fromisoformat(agora_iso)
    except ValueError:
        return {"erro": f"agora_iso inválido: {agora_iso!r}"}
    conn = _obter_conexao()
    evento = aplicar_classificacao(conn, idoso_id, agora)
    return evento.model_dump(mode="json")


def consultar_historico_alertas(idoso_id: str) -> list[dict]:
    """Retorna os alertas registrados para o idoso, do mais antigo ao mais recente."""
    conn = _obter_conexao()
    alertas = listar_alertas(conn, idoso_id)
    return [a.model_dump(mode="json") for a in alertas]
```

Substitua `montar_agente_monitoramento` por:

```python
def montar_agente_monitoramento(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_monitoramento",
        model=model,
        description="Analisa leituras de sensores e classifica o status de risco do idoso.",
        instruction=(
            "Quando a família perguntar sobre o estado de saúde/segurança do "
            "idoso, use a ferramenta consultar_status_atual para obter a "
            "classificação mais recente (normal, atenção ou risco) e o "
            "motivo. Nunca decida o status você mesmo — sempre consulte a "
            "ferramenta, que reflete um cálculo já feito automaticamente.\n\n"
            "Toda mensagem recebida começa com uma linha de contexto do "
            "sistema no formato "
            "'[contexto do sistema: idoso_id=<id>; agora=<timestamp ISO 8601>]', "
            "seguida do texto real da pergunta. Extraia idoso_id e agora "
            "dessa linha e use-os como os argumentos idoso_id e agora_iso."
        ),
        tools=[consultar_status_atual],
    )
```

Substitua `montar_agente_emergencia` por:

```python
def montar_agente_emergencia(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_emergencia",
        model=model,
        description="Decide o escalonamento de alertas em situações de risco.",
        instruction=(
            "Quando a família perguntar sobre alertas ou ocorrências "
            "recentes, use a ferramenta consultar_historico_alertas para "
            "obter o histórico já registrado. O escalonamento de risco em "
            "si é decidido automaticamente por um processo separado, não "
            "por você — sua função aqui é relatar o que já foi registrado, "
            "nunca decidir se algo é uma emergência.\n\n"
            "Toda mensagem recebida começa com uma linha de contexto do "
            "sistema no formato "
            "'[contexto do sistema: idoso_id=<id>; agora=<timestamp ISO 8601>]', "
            "seguida do texto real da pergunta. Extraia idoso_id dessa linha "
            "e use-o como o argumento idoso_id."
        ),
        tools=[consultar_historico_alertas],
    )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_agents_orchestrator_tools_monitoramento.py tests/test_agents_orchestrator_tools.py tests/test_agents_orchestrator.py -v`
Expected: todos passam

- [ ] **Step 5: Rodar a suíte completa**

Run: `pytest -q`
Expected: todos os testes passam

- [ ] **Step 6: Commit**

```bash
git add zela/agents/orchestrator.py tests/test_agents_orchestrator_tools_monitoramento.py
git commit -m "feat: ferramentas reais nos agentes de monitoramento e emergencia"
```

---

### Task 8: Firmware ESP32 (sensor de presença)

**Files:**
- Create: `firmware/zela_presenca/zela_presenca.ino`

**Interfaces:**
- Nenhuma testável via `pytest` — este é código C++/Arduino para o ESP32, verificado manualmente (flash real + observação do Serial Monitor).

- [ ] **Step 1: Criar o diretório e o arquivo do firmware**

```bash
mkdir -p firmware/zela_presenca
```

Crie `firmware/zela_presenca/zela_presenca.ino`:

```cpp
// Firmware do ESP32 para o Zela+: le um sensor ultrassonico HC-SR04 e
// notifica o backend (POST /ingest/esp32) sempre que a presenca no
// comodo muda de estado (presente <-> ausente).
//
// Ligacoes do HC-SR04:
//   VCC   -> 5V (ou 3.3V, conforme o modulo)
//   GND   -> GND
//   TRIG  -> GPIO 5
//   ECHO  -> GPIO 18 (usar um divisor de tensao 5V->3.3V se o modulo for 5V)

#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>

const char *WIFI_SSID = "SUA_REDE_WIFI";
const char *WIFI_SENHA = "SUA_SENHA_WIFI";
const char *URL_INGESTAO = "http://SEU_SERVIDOR:8000/ingest/esp32";

const int PINO_TRIGGER = 5;
const int PINO_ECHO = 18;
const float DISTANCIA_LIMIAR_CM = 150.0;
const unsigned long INTERVALO_LEITURA_MS = 2000;

bool presencaAnterior = false;

float lerDistanciaCm() {
  digitalWrite(PINO_TRIGGER, LOW);
  delayMicroseconds(2);
  digitalWrite(PINO_TRIGGER, HIGH);
  delayMicroseconds(10);
  digitalWrite(PINO_TRIGGER, LOW);

  long duracaoMicros = pulseIn(PINO_ECHO, HIGH, 30000);
  if (duracaoMicros == 0) {
    return -1.0;  // sem eco dentro do timeout (nada refletindo o sinal)
  }
  return duracaoMicros * 0.0343 / 2.0;
}

String obterTimestampIso() {
  time_t agora = time(nullptr);
  struct tm infoTempo;
  gmtime_r(&agora, &infoTempo);
  char buffer[25];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%S", &infoTempo);
  return String(buffer);
}

void enviarLeitura(bool presenca) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi desconectado, pulando envio.");
    return;
  }
  HTTPClient http;
  http.begin(URL_INGESTAO);
  http.addHeader("Content-Type", "application/json");

  String corpo = String("{\"valor\": ") + (presenca ? "1" : "0") +
                 ", \"timestamp\": \"" + obterTimestampIso() + "\"}";

  int codigoResposta = http.POST(corpo);
  Serial.printf("POST /ingest/esp32 -> %d\n", codigoResposta);
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(PINO_TRIGGER, OUTPUT);
  pinMode(PINO_ECHO, INPUT);

  WiFi.begin(WIFI_SSID, WIFI_SENHA);
  Serial.print("Conectando ao WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConectado.");

  // O ESP32 nao tem RTC com bateria propria — sincroniza a hora via NTP
  // antes de comecar a enviar leituras, para os timestamps serem reais.
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("Sincronizando hora via NTP");
  time_t agora = time(nullptr);
  while (agora < 100000) {
    delay(500);
    Serial.print(".");
    agora = time(nullptr);
  }
  Serial.println("\nHora sincronizada.");
}

void loop() {
  float distanciaCm = lerDistanciaCm();
  bool presencaAtual = (distanciaCm > 0 && distanciaCm <= DISTANCIA_LIMIAR_CM);

  if (presencaAtual != presencaAnterior) {
    enviarLeitura(presencaAtual);
    presencaAnterior = presencaAtual;
  }

  delay(INTERVALO_LEITURA_MS);
}
```

- [ ] **Step 2: Verificação manual (documentar no README na Task 9, não repetir aqui)**

Este firmware não tem teste automatizado. A verificação é manual: compilar no Arduino IDE (placa "ESP32 Dev Module", biblioteca `WiFi`/`HTTPClient` já inclusas no core do ESP32), gravar no dispositivo, abrir o Serial Monitor a 115200 bps e confirmar que aparece "Conectado." e "Hora sincronizada.", depois mover a mão na frente do sensor e observar as linhas `POST /ingest/esp32 -> 200` (com o backend do Zela+ rodando e acessível na rede).

- [ ] **Step 3: Commit**

```bash
git add firmware/zela_presenca/zela_presenca.ino
git commit -m "feat: firmware do ESP32 para deteccao de presenca via HC-SR04"
```

---

### Task 9: README — setup do Health Connect Webhook e do ESP32

**Files:**
- Modify: `README.md`

**Interfaces:**
- Nenhuma (documentação).

- [ ] **Step 1: Atualizar a lista "Status do projeto"** — marque o item 3 (ingestão de sensores) como concluído, seguindo o mesmo estilo usado para os itens 1 e 2.

- [ ] **Step 2: Adicionar uma nova seção `## Configurando a ingestão de sensores`**, com o seguinte conteúdo:

```markdown
## Configurando a ingestão de sensores

### ESP32 (sensor de presença)

1. Monte o circuito: HC-SR04 com `TRIG` no GPIO 5 e `ECHO` no GPIO 18 do
   ESP32 (use um divisor de tensão no `ECHO` se o seu módulo for de 5V).
2. Abra `firmware/zela_presenca/zela_presenca.ino` no Arduino IDE, com a
   placa "ESP32 Dev Module" selecionada.
3. Edite `WIFI_SSID`, `WIFI_SENHA` e `URL_INGESTAO` (aponte para o
   endereço da máquina rodando o backend do Zela+, ex.:
   `http://192.168.0.10:8000/ingest/esp32`).
4. Grave no ESP32 e abra o Serial Monitor (115200 bps) para confirmar a
   conexão WiFi, a sincronização de hora via NTP, e os envios
   (`POST /ingest/esp32 -> 200`) ao mover a mão na frente do sensor.

### Smartwatch (Mi Band 9 → Health Connect → Health Connect Webhook)

1. Instale o app **"Health Connect Webhook"** (Play Store,
   `com.hcwebhook.app`) no celular Android onde o Mi Fitness já
   sincroniza com o Health Connect.
2. Configure a URL do webhook para
   `http://<seu-servidor>:8000/ingest/health-connect` e selecione os
   tipos de dados desejados (ex.: frequência cardíaca).
3. **Nota:** o formato exato do payload enviado por esse app não foi
   verificado neste projeto — confira o JSON recebido de fato após
   configurar o app (ex.: logando o corpo da requisição temporariamente)
   e ajuste `zela/api/ingestao.py` se necessário.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: setup do ESP32 e do Health Connect Webhook"
```
