# Zela+ — Fundação dos Agentes (Plano 1 de 7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a fundação de software do Zela+: modelos Pydantic, lógica de domínio de cada um dos 5 agentes (pura, sem dependências externas) e o esqueleto de orquestração multiagente via ADK — tudo testável com `pytest`, sem hardware real, sem WhatsApp/Twilio, sem embeddings e sem chamadas de rede/API. Este é o Plano 1 de uma série de 7; os planos seguintes (comunicação real, ingestão de sensores, embeddings, Streamlit, n8n, empacotamento) substituem/complementam partes mockadas aqui.

**Architecture:** Camadas isoladas: `zela/models` (contratos de dados Pydantic) → `zela/domain` (regras de negócio puras, uma função/módulo por agente, 100% testável sem I/O) → `zela/agents` (agentes ADK que futuramente chamarão as funções de domínio como tools) → `zela/simulacao.py` (integra tudo num fluxo de "um dia" de ponta a ponta, sem ADK, para validar a lógica de negócio conjunta).

**Tech Stack:** Python 3.11+, Pydantic 2.x, google-adk, pytest.

**Spec:** `docs/superpowers/specs/2026-09-10-cuida-mais-agente-idoso-design.md`

## Global Constraints

- Python 3.11+ (usa sintaxe `list[int]`, `int | None` nativa).
- Pydantic 2.x para todos os modelos de dados (seção 4 do spec).
- Todos os campos categóricos usam `Enum` (str, Enum), nunca strings soltas.
- Telefones de contatos familiares validados em formato E.164 (`^\+[1-9]\d{6,14}$`), conforme spec seção 4.
- **Nenhum teste automatizado pode exigir chave de API, credenciais ou acesso de rede.** Comportamento dependente de LLM (raciocínio do agente) é verificado manualmente via `adk run`, documentado no README — os testes automatizados verificam apenas a estrutura dos agentes (nomes, sub_agents, tools) e a lógica de domínio pura.
- Persistência de dados (banco de dados, arquivo) **não** é decidida neste plano — está fora de escopo. Toda lógica de domínio recebe listas/objetos em memória como parâmetros; a decisão de onde os dados "moram" de verdade fica para o Plano 2, quando as integrações reais (WhatsApp, sensores) exigirem estado persistente.
- Nome do projeto: **Zela+** (não usar "Cuida+", nome já existente no mercado).
- O card do curso cita "Langflow" nos itens 3.4 e 3.8, mas o projeto usa **n8n** no lugar (decisão registrada na spec, seção 1) — isso não afeta este plano (Plano 1 é 100% Python/ADK), mas deve ser lembrado nos planos 2 e 6.

---

## Mapa de arquivos deste plano

```
zela/
  __init__.py
  models/
    __init__.py
    perfil.py          # PerfilIdoso, ContatoFamiliar
    rotina.py           # Dosagem, Medicamento, Compromisso, ConfirmacaoMedicacao + enums
    monitoramento.py    # LeituraSensor, EventoMonitoramento + enums + FAIXAS_PLAUSIVEIS
    comunicacao.py       # MensagemEntrada + enum TipoMensagem
    alertas.py           # Alerta + enums
  domain/
    __init__.py
    rotina.py            # calcular_lembretes_pendentes, registrar_confirmacao
    monitoramento.py     # classificar_por_regra
    comunicacao.py        # formatar_lembrete, interpretar_resposta
    emergencia.py         # EstadoEscalonamento, decidir_proxima_acao
  agents/
    __init__.py
    orchestrator.py       # montar_agente_* (ADK), montar_orquestrador
  simulacao.py             # simular_dia — integra domain, sem ADK
tests/
  __init__.py
  test_models_perfil.py
  test_models_rotina.py
  test_models_monitoramento.py
  test_models_comunicacao_alertas.py
  test_domain_rotina.py
  test_domain_monitoramento.py
  test_domain_comunicacao.py
  test_domain_emergencia.py
  test_agents_orchestrator.py
  test_simulacao.py
pyproject.toml
.gitignore
README.md
```

---

### Task 1: Scaffolding do projeto

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `zela/__init__.py`
- Create: `zela/models/__init__.py` (vazio por enquanto)
- Create: `zela/domain/__init__.py` (vazio)
- Create: `zela/agents/__init__.py` (vazio)
- Create: `tests/__init__.py` (vazio)

**Interfaces:**
- Produces: pacote `zela` instalável em modo editável, `pytest` configurado e coletando a partir de `tests/`.

- [ ] **Step 1: Criar a estrutura de diretórios e arquivos vazios**

```bash
mkdir -p zela/models zela/domain zela/agents tests
touch zela/__init__.py zela/models/__init__.py zela/domain/__init__.py zela/agents/__init__.py tests/__init__.py
```

- [ ] **Step 2: Criar `pyproject.toml`**

```toml
[project]
name = "zela"
version = "0.1.0"
description = "Zela+ — agente de IA de apoio ao idoso que mora sozinho"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.6,<3",
    "google-adk>=1.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["zela*"]
```

Nota: `google-adk` é uma biblioteca em evolução rápida. Se a instalação falhar por causa da versão, rode `pip install -U google-adk` e ajuste o mínimo aqui para a versão instalada.

- [ ] **Step 3: Criar `.gitignore`**

```
__pycache__/
*.pyc
.venv/
venv/
*.egg-info/
.pytest_cache/
.env
```

- [ ] **Step 4: Instalar o projeto em modo editável com dependências de dev**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

- [ ] **Step 5: Verificar que o pytest coleta (mesmo sem testes ainda) sem erros**

Run: `pytest --collect-only`
Expected: `no tests ran` (ou `collected 0 items`), sem erros de import.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore zela tests
git commit -m "chore: scaffolding inicial do projeto Zela+"
```

---

### Task 2: Modelos Pydantic — Perfil do Idoso

**Files:**
- Create: `zela/models/perfil.py`
- Test: `tests/test_models_perfil.py`

**Interfaces:**
- Produces: `ContatoFamiliar(nome: str, telefone: str)`, `PerfilIdoso(nome: str, data_nascimento: date, contatos_familiares: list[ContatoFamiliar], condicoes_medicas: list[str])`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_models_perfil.py
import pytest
from datetime import date
from pydantic import ValidationError

from zela.models.perfil import ContatoFamiliar, PerfilIdoso


def test_perfil_idoso_valido():
    perfil = PerfilIdoso(
        nome="Maria da Silva",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )
    assert perfil.nome == "Maria da Silva"
    assert perfil.contatos_familiares[0].telefone == "+5511987654321"


def test_perfil_idoso_exige_ao_menos_um_contato_familiar():
    with pytest.raises(ValidationError):
        PerfilIdoso(
            nome="Maria da Silva",
            data_nascimento=date(1945, 3, 12),
            contatos_familiares=[],
        )


def test_contato_familiar_rejeita_telefone_fora_do_padrao_e164():
    with pytest.raises(ValidationError):
        ContatoFamiliar(nome="João", telefone="011987654321")


def test_perfil_idoso_condicoes_medicas_e_opcional_e_vazia_por_padrao():
    perfil = PerfilIdoso(
        nome="Maria da Silva",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )
    assert perfil.condicoes_medicas == []
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_models_perfil.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.models.perfil'`

- [ ] **Step 3: Implementar `zela/models/perfil.py`**

```python
from datetime import date

from pydantic import BaseModel, Field

E164_PATTERN = r"^\+[1-9]\d{6,14}$"


class ContatoFamiliar(BaseModel):
    nome: str
    telefone: str = Field(pattern=E164_PATTERN)


class PerfilIdoso(BaseModel):
    nome: str
    data_nascimento: date
    contatos_familiares: list[ContatoFamiliar] = Field(min_length=1)
    condicoes_medicas: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_models_perfil.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add zela/models/perfil.py tests/test_models_perfil.py
git commit -m "feat: modelo PerfilIdoso e ContatoFamiliar com validação E.164"
```

---

### Task 3: Modelos Pydantic — Rotina (medicamentos e compromissos)

**Files:**
- Create: `zela/models/rotina.py`
- Test: `tests/test_models_rotina.py`

**Interfaces:**
- Produces: enums `TipoCompromisso`, `StatusConfirmacao`, `CanalConfirmacao`; modelos `Dosagem(quantidade: float, unidade: str)`, `Medicamento(id, nome, dosagem, horarios: list[time], dias_semana: list[int], ativo: bool)`, `Compromisso(id, titulo, data_hora, local, tipo)`, `ConfirmacaoMedicacao(medicamento_id, horario_previsto, horario_confirmado, status, canal)`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_models_rotina.py
from datetime import datetime, time, timedelta

import pytest
from pydantic import ValidationError

from zela.models.rotina import (
    CanalConfirmacao,
    Compromisso,
    ConfirmacaoMedicacao,
    Dosagem,
    Medicamento,
    StatusConfirmacao,
    TipoCompromisso,
)


def test_medicamento_valido():
    medicamento = Medicamento(
        id="med-1",
        nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"),
        horarios=[time(8, 0), time(20, 0)],
    )
    assert medicamento.ativo is True
    assert medicamento.dias_semana == list(range(7))


def test_dosagem_rejeita_quantidade_nao_positiva():
    with pytest.raises(ValidationError):
        Dosagem(quantidade=0, unidade="mg")


def test_medicamento_rejeita_horarios_vazios():
    with pytest.raises(ValidationError):
        Medicamento(id="med-1", nome="Losartana", dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[])


def test_medicamento_rejeita_horarios_duplicados():
    with pytest.raises(ValidationError):
        Medicamento(
            id="med-1",
            nome="Losartana",
            dosagem=Dosagem(quantidade=50, unidade="mg"),
            horarios=[time(8, 0), time(8, 0)],
        )


def test_medicamento_rejeita_dia_semana_invalido():
    with pytest.raises(ValidationError):
        Medicamento(
            id="med-1",
            nome="Losartana",
            dosagem=Dosagem(quantidade=50, unidade="mg"),
            horarios=[time(8, 0)],
            dias_semana=[7],
        )


def test_compromisso_rejeita_data_no_passado():
    with pytest.raises(ValidationError):
        Compromisso(
            id="cp-1",
            titulo="Consulta cardiologista",
            data_hora=datetime.now() - timedelta(days=1),
            local="Clínica Central",
            tipo=TipoCompromisso.CONSULTA,
        )


def test_compromisso_aceita_data_futura():
    compromisso = Compromisso(
        id="cp-1",
        titulo="Consulta cardiologista",
        data_hora=datetime.now() + timedelta(days=1),
        local="Clínica Central",
        tipo=TipoCompromisso.CONSULTA,
    )
    assert compromisso.tipo == TipoCompromisso.CONSULTA


def test_confirmacao_medicacao_valida():
    confirmacao = ConfirmacaoMedicacao(
        medicamento_id="med-1",
        horario_previsto=datetime(2026, 9, 13, 8, 0),
        horario_confirmado=datetime(2026, 9, 13, 8, 5),
        status=StatusConfirmacao.CONFIRMADO,
        canal=CanalConfirmacao.WHATSAPP,
    )
    assert confirmacao.status == StatusConfirmacao.CONFIRMADO
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_models_rotina.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.models.rotina'`

- [ ] **Step 3: Implementar `zela/models/rotina.py`**

```python
from datetime import datetime, time
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class TipoCompromisso(str, Enum):
    CONSULTA = "consulta"
    EXAME = "exame"
    OUTRO = "outro"


class StatusConfirmacao(str, Enum):
    CONFIRMADO = "confirmado"
    ATRASADO = "atrasado"
    NAO_CONFIRMADO = "nao_confirmado"


class CanalConfirmacao(str, Enum):
    WHATSAPP = "whatsapp"
    MANUAL = "manual"


class Dosagem(BaseModel):
    quantidade: float = Field(gt=0)
    unidade: str


class Medicamento(BaseModel):
    id: str
    nome: str
    dosagem: Dosagem
    horarios: list[time]
    dias_semana: list[int] = Field(default_factory=lambda: list(range(7)))
    ativo: bool = True

    @field_validator("horarios")
    @classmethod
    def horarios_nao_vazios_e_unicos(cls, v: list[time]) -> list[time]:
        if not v:
            raise ValueError("é necessário ao menos um horário")
        if len(v) != len(set(v)):
            raise ValueError("horários devem ser únicos")
        return v

    @field_validator("dias_semana")
    @classmethod
    def dias_semana_validos(cls, v: list[int]) -> list[int]:
        if any(dia < 0 or dia > 6 for dia in v):
            raise ValueError("dias_semana deve conter valores entre 0 (segunda) e 6 (domingo)")
        return v


class Compromisso(BaseModel):
    id: str
    titulo: str
    data_hora: datetime
    local: str
    tipo: TipoCompromisso

    @field_validator("data_hora")
    @classmethod
    def data_hora_deve_ser_futura(cls, v: datetime) -> datetime:
        if v <= datetime.now():
            raise ValueError("data_hora do compromisso deve ser no futuro")
        return v


class ConfirmacaoMedicacao(BaseModel):
    medicamento_id: str
    horario_previsto: datetime
    horario_confirmado: datetime | None = None
    status: StatusConfirmacao
    canal: CanalConfirmacao
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_models_rotina.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add zela/models/rotina.py tests/test_models_rotina.py
git commit -m "feat: modelos de rotina (Medicamento, Compromisso, ConfirmacaoMedicacao)"
```

---

### Task 4: Modelos Pydantic — Monitoramento de saúde/risco

**Files:**
- Create: `zela/models/monitoramento.py`
- Test: `tests/test_models_monitoramento.py`

**Interfaces:**
- Produces: enums `FonteSensor`, `TipoLeitura`, `StatusMonitoramento`, `MetodoClassificacao`; dict `FAIXAS_PLAUSIVEIS: dict[TipoLeitura, tuple[float, float]]`; modelos `LeituraSensor(fonte, tipo, valor, unidade, timestamp, plausivel: bool)`, `EventoMonitoramento(status, motivo, leituras_relacionadas, timestamp, metodo_classificacao)`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_models_monitoramento.py
from datetime import datetime

from zela.models.monitoramento import (
    EventoMonitoramento,
    FonteSensor,
    LeituraSensor,
    MetodoClassificacao,
    StatusMonitoramento,
    TipoLeitura,
)


def test_leitura_frequencia_cardiaca_plausivel():
    leitura = LeituraSensor(
        fonte=FonteSensor.SMARTWATCH,
        tipo=TipoLeitura.FREQUENCIA_CARDIACA,
        valor=72,
        unidade="bpm",
        timestamp=datetime(2026, 9, 13, 10, 0),
    )
    assert leitura.plausivel is True


def test_leitura_frequencia_cardiaca_implausivel_e_flagueada_nao_rejeitada():
    leitura = LeituraSensor(
        fonte=FonteSensor.SMARTWATCH,
        tipo=TipoLeitura.FREQUENCIA_CARDIACA,
        valor=300,
        unidade="bpm",
        timestamp=datetime(2026, 9, 13, 10, 0),
    )
    assert leitura.plausivel is False


def test_leitura_presenca_plausivel():
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=datetime(2026, 9, 13, 10, 0),
    )
    assert leitura.plausivel is True


def test_evento_monitoramento_valido():
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=datetime(2026, 9, 13, 10, 0),
    )
    evento = EventoMonitoramento(
        status=StatusMonitoramento.NORMAL,
        motivo="Nenhuma anomalia detectada",
        leituras_relacionadas=[leitura],
        timestamp=datetime(2026, 9, 13, 10, 0),
        metodo_classificacao=MetodoClassificacao.REGRA,
    )
    assert evento.status == StatusMonitoramento.NORMAL
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_models_monitoramento.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.models.monitoramento'`

- [ ] **Step 3: Implementar `zela/models/monitoramento.py`**

```python
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class FonteSensor(str, Enum):
    SMARTWATCH = "smartwatch"
    ESP32 = "esp32"


class TipoLeitura(str, Enum):
    FREQUENCIA_CARDIACA = "frequencia_cardiaca"
    PASSOS = "passos"
    SONO = "sono"
    PRESENCA = "presenca"


class StatusMonitoramento(str, Enum):
    NORMAL = "normal"
    ATENCAO = "atencao"
    RISCO = "risco"


class MetodoClassificacao(str, Enum):
    REGRA = "regra"
    EMBEDDING = "embedding"


FAIXAS_PLAUSIVEIS: dict[TipoLeitura, tuple[float, float]] = {
    TipoLeitura.FREQUENCIA_CARDIACA: (30, 220),
    TipoLeitura.PASSOS: (0, 60000),
    TipoLeitura.SONO: (0, 24),
    TipoLeitura.PRESENCA: (0, 1),
}


class LeituraSensor(BaseModel):
    fonte: FonteSensor
    tipo: TipoLeitura
    valor: float
    unidade: str
    timestamp: datetime
    plausivel: bool = True

    @model_validator(mode="after")
    def calcular_plausibilidade(self) -> "LeituraSensor":
        minimo, maximo = FAIXAS_PLAUSIVEIS[self.tipo]
        self.plausivel = minimo <= self.valor <= maximo
        return self


class EventoMonitoramento(BaseModel):
    status: StatusMonitoramento
    motivo: str
    leituras_relacionadas: list[LeituraSensor] = Field(default_factory=list)
    timestamp: datetime
    metodo_classificacao: MetodoClassificacao
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_models_monitoramento.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add zela/models/monitoramento.py tests/test_models_monitoramento.py
git commit -m "feat: modelos de monitoramento com validacao de faixas plausiveis"
```

---

### Task 5: Modelos Pydantic — Comunicação e Alertas

**Files:**
- Create: `zela/models/comunicacao.py`
- Create: `zela/models/alertas.py`
- Modify: `zela/models/__init__.py`
- Test: `tests/test_models_comunicacao_alertas.py`

**Interfaces:**
- Produces: enum `TipoMensagem`, modelo `MensagemEntrada(remetente, tipo, conteudo_bruto, transcricao, timestamp)`; enums `NivelAlerta`, `CanalAlerta`, `StatusAlerta`, modelo `Alerta(nivel, destinatario, canal, mensagem, status, timestamp)`.
- Consumes: nenhuma dependência de outros módulos `zela` (modelos-folha).

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_models_comunicacao_alertas.py
from datetime import datetime

from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta, StatusAlerta
from zela.models.comunicacao import MensagemEntrada, TipoMensagem


def test_mensagem_texto_preenche_transcricao_automaticamente():
    mensagem = MensagemEntrada(
        remetente="idosa",
        tipo=TipoMensagem.TEXTO,
        conteudo_bruto="já tomei o remédio",
        timestamp=datetime(2026, 9, 13, 8, 5),
    )
    assert mensagem.transcricao == "já tomei o remédio"


def test_mensagem_audio_permite_transcricao_none_inicialmente():
    mensagem = MensagemEntrada(
        remetente="idosa",
        tipo=TipoMensagem.AUDIO,
        conteudo_bruto="<audio-bytes-base64>",
        timestamp=datetime(2026, 9, 13, 8, 5),
    )
    assert mensagem.transcricao is None


def test_alerta_valido_com_status_padrao_enviado():
    alerta = Alerta(
        nivel=NivelAlerta.CRITICO,
        destinatario="João",
        canal=CanalAlerta.WHATSAPP,
        mensagem="Sem resposta da Maria há 20 minutos.",
        timestamp=datetime(2026, 9, 13, 8, 20),
    )
    assert alerta.status == StatusAlerta.ENVIADO
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_models_comunicacao_alertas.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar `zela/models/comunicacao.py`**

```python
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, model_validator


class TipoMensagem(str, Enum):
    TEXTO = "texto"
    AUDIO = "audio"


class MensagemEntrada(BaseModel):
    remetente: str
    tipo: TipoMensagem
    conteudo_bruto: str
    transcricao: str | None = None
    timestamp: datetime

    @model_validator(mode="after")
    def preencher_transcricao_de_texto(self) -> "MensagemEntrada":
        if self.tipo == TipoMensagem.TEXTO and self.transcricao is None:
            self.transcricao = self.conteudo_bruto
        return self
```

- [ ] **Step 4: Implementar `zela/models/alertas.py`**

```python
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class NivelAlerta(str, Enum):
    INFO = "info"
    ATENCAO = "atencao"
    CRITICO = "critico"


class CanalAlerta(str, Enum):
    WHATSAPP = "whatsapp"
    STREAMLIT = "streamlit"


class StatusAlerta(str, Enum):
    ENVIADO = "enviado"
    CONFIRMADO = "confirmado"


class Alerta(BaseModel):
    nivel: NivelAlerta
    destinatario: str
    canal: CanalAlerta
    mensagem: str
    status: StatusAlerta = StatusAlerta.ENVIADO
    timestamp: datetime
```

- [ ] **Step 5: Atualizar `zela/models/__init__.py` para reexportar tudo**

```python
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta, StatusAlerta
from zela.models.comunicacao import MensagemEntrada, TipoMensagem
from zela.models.monitoramento import (
    FAIXAS_PLAUSIVEIS,
    EventoMonitoramento,
    FonteSensor,
    LeituraSensor,
    MetodoClassificacao,
    StatusMonitoramento,
    TipoLeitura,
)
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.models.rotina import (
    CanalConfirmacao,
    Compromisso,
    ConfirmacaoMedicacao,
    Dosagem,
    Medicamento,
    StatusConfirmacao,
    TipoCompromisso,
)

__all__ = [
    "Alerta",
    "CanalAlerta",
    "NivelAlerta",
    "StatusAlerta",
    "MensagemEntrada",
    "TipoMensagem",
    "FAIXAS_PLAUSIVEIS",
    "EventoMonitoramento",
    "FonteSensor",
    "LeituraSensor",
    "MetodoClassificacao",
    "StatusMonitoramento",
    "TipoLeitura",
    "ContatoFamiliar",
    "PerfilIdoso",
    "CanalConfirmacao",
    "Compromisso",
    "ConfirmacaoMedicacao",
    "Dosagem",
    "Medicamento",
    "StatusConfirmacao",
    "TipoCompromisso",
]
```

- [ ] **Step 6: Rodar todos os testes de modelos e confirmar que passam**

Run: `pytest tests/test_models_comunicacao_alertas.py tests/test_models_perfil.py tests/test_models_rotina.py tests/test_models_monitoramento.py -v`
Expected: todos passam (19 testes no total)

- [ ] **Step 7: Commit**

```bash
git add zela/models/comunicacao.py zela/models/alertas.py zela/models/__init__.py tests/test_models_comunicacao_alertas.py
git commit -m "feat: modelos de comunicacao e alertas + reexport em models/__init__"
```

---

### Task 6: Domínio — Agente de Rotina/Medicação

**Files:**
- Create: `zela/domain/rotina.py`
- Test: `tests/test_domain_rotina.py`

**Interfaces:**
- Consumes: `zela.models.rotina.{Medicamento, ConfirmacaoMedicacao, StatusConfirmacao, CanalConfirmacao}`.
- Produces: `calcular_lembretes_pendentes(medicamentos: list[Medicamento], confirmacoes: list[ConfirmacaoMedicacao], agora: datetime) -> list[Medicamento]`; `registrar_confirmacao(medicamento: Medicamento, horario_previsto: datetime, agora: datetime, canal: CanalConfirmacao = CanalConfirmacao.WHATSAPP) -> ConfirmacaoMedicacao`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_domain_rotina.py
from datetime import datetime, time

from zela.domain.rotina import calcular_lembretes_pendentes, registrar_confirmacao
from zela.models.rotina import CanalConfirmacao, ConfirmacaoMedicacao, Dosagem, Medicamento, StatusConfirmacao


def _medicamento(horario=time(8, 0), dias_semana=None):
    kwargs = dict(
        id="med-1",
        nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"),
        horarios=[horario],
    )
    if dias_semana is not None:
        kwargs["dias_semana"] = dias_semana
    return Medicamento(**kwargs)


def test_lembrete_pendente_dentro_da_janela():
    medicamento = _medicamento()
    agora = datetime(2026, 9, 13, 8, 5)  # domingo (weekday() == 6); dias_semana padrão inclui todos os dias
    pendentes = calcular_lembretes_pendentes([medicamento], [], agora)
    assert pendentes == [medicamento]


def test_lembrete_fora_da_janela_nao_aparece():
    medicamento = _medicamento()
    agora = datetime(2026, 9, 13, 9, 0)
    pendentes = calcular_lembretes_pendentes([medicamento], [], agora)
    assert pendentes == []


def test_lembrete_ja_confirmado_hoje_nao_aparece():
    medicamento = _medicamento()
    agora = datetime(2026, 9, 13, 8, 5)
    confirmacao = ConfirmacaoMedicacao(
        medicamento_id="med-1",
        horario_previsto=datetime(2026, 9, 13, 8, 0),
        horario_confirmado=datetime(2026, 9, 13, 8, 1),
        status=StatusConfirmacao.CONFIRMADO,
        canal=CanalConfirmacao.WHATSAPP,
    )
    pendentes = calcular_lembretes_pendentes([medicamento], [confirmacao], agora)
    assert pendentes == []


def test_lembrete_fora_do_dia_da_semana_nao_aparece():
    # 2026-09-13 é domingo (datetime.weekday() == 6); dias_semana=[0..4] é
    # segunda a sexta, que exclui domingo.
    medicamento = _medicamento(dias_semana=[0, 1, 2, 3, 4])
    agora = datetime(2026, 9, 13, 8, 5)
    pendentes = calcular_lembretes_pendentes([medicamento], [], agora)
    assert pendentes == []


def test_registrar_confirmacao_no_horario():
    medicamento = _medicamento()
    horario_previsto = datetime(2026, 9, 13, 8, 0)
    agora = datetime(2026, 9, 13, 8, 5)
    confirmacao = registrar_confirmacao(medicamento, horario_previsto, agora)
    assert confirmacao.status == StatusConfirmacao.CONFIRMADO
    assert confirmacao.medicamento_id == "med-1"


def test_registrar_confirmacao_atrasada():
    medicamento = _medicamento()
    horario_previsto = datetime(2026, 9, 13, 8, 0)
    agora = datetime(2026, 9, 13, 9, 0)
    confirmacao = registrar_confirmacao(medicamento, horario_previsto, agora)
    assert confirmacao.status == StatusConfirmacao.ATRASADO
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_domain_rotina.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.domain.rotina'`

- [ ] **Step 3: Implementar `zela/domain/rotina.py`**

```python
from datetime import datetime, timedelta

from zela.models.rotina import CanalConfirmacao, ConfirmacaoMedicacao, Medicamento, StatusConfirmacao

JANELA_LEMBRETE = timedelta(minutes=15)
TOLERANCIA_ATRASO = timedelta(minutes=30)


def calcular_lembretes_pendentes(
    medicamentos: list[Medicamento],
    confirmacoes: list[ConfirmacaoMedicacao],
    agora: datetime,
) -> list[Medicamento]:
    dia_semana_atual = agora.weekday()
    confirmados_hoje = {
        c.medicamento_id
        for c in confirmacoes
        if c.horario_previsto.date() == agora.date() and c.status == StatusConfirmacao.CONFIRMADO
    }

    pendentes = []
    for medicamento in medicamentos:
        if not medicamento.ativo or dia_semana_atual not in medicamento.dias_semana:
            continue
        if medicamento.id in confirmados_hoje:
            continue
        for horario in medicamento.horarios:
            horario_previsto = datetime.combine(agora.date(), horario)
            if horario_previsto <= agora <= horario_previsto + JANELA_LEMBRETE:
                pendentes.append(medicamento)
                break
    return pendentes


def registrar_confirmacao(
    medicamento: Medicamento,
    horario_previsto: datetime,
    agora: datetime,
    canal: CanalConfirmacao = CanalConfirmacao.WHATSAPP,
) -> ConfirmacaoMedicacao:
    atrasado = agora > horario_previsto + TOLERANCIA_ATRASO
    return ConfirmacaoMedicacao(
        medicamento_id=medicamento.id,
        horario_previsto=horario_previsto,
        horario_confirmado=agora,
        status=StatusConfirmacao.ATRASADO if atrasado else StatusConfirmacao.CONFIRMADO,
        canal=canal,
    )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_domain_rotina.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add zela/domain/rotina.py tests/test_domain_rotina.py
git commit -m "feat: logica de dominio do agente de rotina/medicacao"
```

---

### Task 7: Domínio — Agente de Monitoramento de Saúde/Risco

**Files:**
- Create: `zela/domain/monitoramento.py`
- Test: `tests/test_domain_monitoramento.py`

**Interfaces:**
- Consumes: `zela.models.monitoramento.{LeituraSensor, EventoMonitoramento, TipoLeitura, StatusMonitoramento, MetodoClassificacao}`.
- Produces: `classificar_por_regra(leituras: list[LeituraSensor], agora: datetime, limite_horas_sem_presenca: float = 6.0) -> EventoMonitoramento`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_domain_monitoramento.py
from datetime import datetime, timedelta

from zela.domain.monitoramento import classificar_por_regra
from zela.models.monitoramento import FonteSensor, StatusMonitoramento, TipoLeitura
from zela.models.monitoramento import LeituraSensor


def test_classifica_normal_sem_leituras():
    agora = datetime(2026, 9, 13, 14, 0)
    evento = classificar_por_regra([], agora)
    assert evento.status == StatusMonitoramento.NORMAL


def test_classifica_risco_por_ausencia_de_presenca():
    agora = datetime(2026, 9, 13, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=agora - timedelta(hours=8),
    )
    evento = classificar_por_regra([leitura], agora)
    assert evento.status == StatusMonitoramento.RISCO
    assert "8.0h" in evento.motivo or "8h" in evento.motivo


def test_classifica_normal_com_presenca_recente():
    agora = datetime(2026, 9, 13, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=agora - timedelta(minutes=30),
    )
    evento = classificar_por_regra([leitura], agora)
    assert evento.status == StatusMonitoramento.NORMAL


def test_classifica_atencao_por_frequencia_cardiaca_implausivel():
    agora = datetime(2026, 9, 13, 14, 0)
    leitura = LeituraSensor(
        fonte=FonteSensor.SMARTWATCH,
        tipo=TipoLeitura.FREQUENCIA_CARDIACA,
        valor=250,
        unidade="bpm",
        timestamp=agora,
    )
    evento = classificar_por_regra([leitura], agora)
    assert evento.status == StatusMonitoramento.ATENCAO
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_domain_monitoramento.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.domain.monitoramento'`

- [ ] **Step 3: Implementar `zela/domain/monitoramento.py`**

```python
from datetime import datetime

from zela.models.monitoramento import (
    EventoMonitoramento,
    LeituraSensor,
    MetodoClassificacao,
    StatusMonitoramento,
    TipoLeitura,
)

LIMITE_HORAS_SEM_PRESENCA = 6.0


def classificar_por_regra(
    leituras: list[LeituraSensor],
    agora: datetime,
    limite_horas_sem_presenca: float = LIMITE_HORAS_SEM_PRESENCA,
) -> EventoMonitoramento:
    leituras_presenca = [l for l in leituras if l.tipo == TipoLeitura.PRESENCA]
    leituras_fc = [l for l in leituras if l.tipo == TipoLeitura.FREQUENCIA_CARDIACA]

    if leituras_presenca:
        ultima_presenca = max(l.timestamp for l in leituras_presenca)
        horas_sem_presenca = (agora - ultima_presenca).total_seconds() / 3600
        if horas_sem_presenca >= limite_horas_sem_presenca:
            return EventoMonitoramento(
                status=StatusMonitoramento.RISCO,
                motivo=f"Sem movimentação detectada há {horas_sem_presenca:.1f}h",
                leituras_relacionadas=leituras_presenca,
                timestamp=agora,
                metodo_classificacao=MetodoClassificacao.REGRA,
            )

    leituras_fc_implausiveis = [l for l in leituras_fc if not l.plausivel]
    if leituras_fc_implausiveis:
        return EventoMonitoramento(
            status=StatusMonitoramento.ATENCAO,
            motivo="Frequência cardíaca fora da faixa esperada",
            leituras_relacionadas=leituras_fc_implausiveis,
            timestamp=agora,
            metodo_classificacao=MetodoClassificacao.REGRA,
        )

    return EventoMonitoramento(
        status=StatusMonitoramento.NORMAL,
        motivo="Nenhuma anomalia detectada",
        leituras_relacionadas=leituras,
        timestamp=agora,
        metodo_classificacao=MetodoClassificacao.REGRA,
    )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_domain_monitoramento.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add zela/domain/monitoramento.py tests/test_domain_monitoramento.py
git commit -m "feat: classificacao por regra do agente de monitoramento"
```

---

### Task 8: Domínio — Agente de Comunicação

**Files:**
- Create: `zela/domain/comunicacao.py`
- Test: `tests/test_domain_comunicacao.py`

**Interfaces:**
- Consumes: `zela.models.rotina.Medicamento`, `zela.models.comunicacao.MensagemEntrada`.
- Produces: `formatar_lembrete(medicamento: Medicamento) -> str`; `interpretar_resposta(mensagem: MensagemEntrada) -> bool | None`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_domain_comunicacao.py
from datetime import datetime

from zela.domain.comunicacao import formatar_lembrete, interpretar_resposta
from zela.models.comunicacao import MensagemEntrada, TipoMensagem
from zela.models.rotina import Dosagem, Medicamento
from datetime import time


def _medicamento():
    return Medicamento(
        id="med-1",
        nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"),
        horarios=[time(8, 0)],
    )


def test_formatar_lembrete_inclui_nome_e_dosagem():
    texto = formatar_lembrete(_medicamento())
    assert "Losartana" in texto
    assert "50" in texto
    assert "mg" in texto


def test_interpretar_resposta_positiva():
    mensagem = MensagemEntrada(
        remetente="idosa", tipo=TipoMensagem.TEXTO, conteudo_bruto="Sim, já tomei",
        timestamp=datetime(2026, 9, 13, 8, 5),
    )
    assert interpretar_resposta(mensagem) is True


def test_interpretar_resposta_negativa():
    mensagem = MensagemEntrada(
        remetente="idosa", tipo=TipoMensagem.TEXTO, conteudo_bruto="Ainda não, esqueci",
        timestamp=datetime(2026, 9, 13, 8, 5),
    )
    assert interpretar_resposta(mensagem) is False


def test_interpretar_resposta_ambigua_retorna_none():
    mensagem = MensagemEntrada(
        remetente="idosa", tipo=TipoMensagem.TEXTO, conteudo_bruto="Está chovendo hoje",
        timestamp=datetime(2026, 9, 13, 8, 5),
    )
    assert interpretar_resposta(mensagem) is None
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_domain_comunicacao.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.domain.comunicacao'`

- [ ] **Step 3: Implementar `zela/domain/comunicacao.py`**

```python
from zela.models.comunicacao import MensagemEntrada
from zela.models.rotina import Medicamento

PALAVRAS_CONFIRMACAO = {"sim", "ok", "certo", "feito", "tomei"}
PALAVRAS_NEGACAO = {"não", "nao", "esqueci"}


def formatar_lembrete(medicamento: Medicamento) -> str:
    return (
        f"Olá! Hora de tomar {medicamento.nome} "
        f"({medicamento.dosagem.quantidade} {medicamento.dosagem.unidade}). "
        "Responda 'tomei' quando fizer isso, tá bem?"
    )


def interpretar_resposta(mensagem: MensagemEntrada) -> bool | None:
    texto = (mensagem.transcricao or mensagem.conteudo_bruto).strip().lower()
    palavras_do_texto = set(texto.replace(",", "").split())
    if palavras_do_texto & PALAVRAS_NEGACAO:
        return False
    if palavras_do_texto & PALAVRAS_CONFIRMACAO:
        return True
    return None
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_domain_comunicacao.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add zela/domain/comunicacao.py tests/test_domain_comunicacao.py
git commit -m "feat: formatacao de lembretes e interpretacao heuristica de respostas"
```

---

### Task 9: Domínio — Agente de Emergência (escalonamento)

**Files:**
- Create: `zela/domain/emergencia.py`
- Test: `tests/test_domain_emergencia.py`

**Interfaces:**
- Consumes: `zela.models.monitoramento.{EventoMonitoramento, StatusMonitoramento}`, `zela.models.perfil.PerfilIdoso`, `zela.models.alertas.{Alerta, NivelAlerta, CanalAlerta}`.
- Produces: enum `EstagioEscalonamento`, dataclass `EstadoEscalonamento(estagio, iniciado_em)`, `decidir_proxima_acao(evento: EventoMonitoramento, perfil: PerfilIdoso, estado: EstadoEscalonamento, agora: datetime) -> tuple[EstadoEscalonamento, list[Alerta]]`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_domain_emergencia.py
from datetime import datetime, timedelta

from zela.domain.emergencia import EstadoEscalonamento, EstagioEscalonamento, decidir_proxima_acao
from zela.models.monitoramento import EventoMonitoramento, MetodoClassificacao, StatusMonitoramento
from zela.models.perfil import ContatoFamiliar, PerfilIdoso


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        data_nascimento=datetime(1945, 3, 12).date(),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def _evento(status):
    return EventoMonitoramento(
        status=status,
        motivo="Sem movimentação detectada há 8.0h",
        timestamp=datetime(2026, 9, 13, 14, 0),
        metodo_classificacao=MetodoClassificacao.REGRA,
    )


def test_evento_normal_resolve_e_nao_gera_alerta():
    estado = EstadoEscalonamento()
    novo_estado, alertas = decidir_proxima_acao(
        _evento(StatusMonitoramento.NORMAL), _perfil(), estado, datetime(2026, 9, 13, 14, 0)
    )
    assert novo_estado.estagio == EstagioEscalonamento.RESOLVIDO
    assert alertas == []


def test_primeiro_evento_de_risco_contata_idoso():
    estado = EstadoEscalonamento()
    agora = datetime(2026, 9, 13, 14, 0)
    novo_estado, alertas = decidir_proxima_acao(_evento(StatusMonitoramento.RISCO), _perfil(), estado, agora)
    assert novo_estado.estagio == EstagioEscalonamento.CONTATO_IDOSO
    assert len(alertas) == 1
    assert alertas[0].destinatario == "Maria da Silva"


def test_sem_resposta_apos_janela_notifica_familia():
    inicio = datetime(2026, 9, 13, 14, 0)
    estado = EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=inicio)
    agora = inicio + timedelta(minutes=11)
    novo_estado, alertas = decidir_proxima_acao(_evento(StatusMonitoramento.RISCO), _perfil(), estado, agora)
    assert novo_estado.estagio == EstagioEscalonamento.NOTIFICAR_FAMILIA
    assert len(alertas) == 1
    assert alertas[0].destinatario == "João"


def test_ainda_dentro_da_janela_de_contato_idoso_nao_escalona():
    inicio = datetime(2026, 9, 13, 14, 0)
    estado = EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=inicio)
    agora = inicio + timedelta(minutes=5)
    novo_estado, alertas = decidir_proxima_acao(_evento(StatusMonitoramento.RISCO), _perfil(), estado, agora)
    assert novo_estado.estagio == EstagioEscalonamento.CONTATO_IDOSO
    assert alertas == []


def test_sem_resposta_da_familia_apos_janela_simula_emergencia():
    inicio = datetime(2026, 9, 13, 14, 0)
    estado = EstadoEscalonamento(estagio=EstagioEscalonamento.NOTIFICAR_FAMILIA, iniciado_em=inicio)
    agora = inicio + timedelta(minutes=16)
    novo_estado, alertas = decidir_proxima_acao(_evento(StatusMonitoramento.RISCO), _perfil(), estado, agora)
    assert novo_estado.estagio == EstagioEscalonamento.SIMULAR_EMERGENCIA
    assert len(alertas) == 1
    assert "SIMULAÇÃO" in alertas[0].mensagem
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_domain_emergencia.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.domain.emergencia'`

- [ ] **Step 3: Implementar `zela/domain/emergencia.py`**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.models.monitoramento import EventoMonitoramento, StatusMonitoramento
from zela.models.perfil import PerfilIdoso


class EstagioEscalonamento(str, Enum):
    OCIOSO = "ocioso"
    CONTATO_IDOSO = "contato_idoso"
    NOTIFICAR_FAMILIA = "notificar_familia"
    SIMULAR_EMERGENCIA = "simular_emergencia"
    RESOLVIDO = "resolvido"


@dataclass
class EstadoEscalonamento:
    estagio: EstagioEscalonamento = EstagioEscalonamento.OCIOSO
    iniciado_em: datetime | None = None


JANELA_CONTATO_IDOSO = timedelta(minutes=10)
JANELA_NOTIFICAR_FAMILIA = timedelta(minutes=15)


def decidir_proxima_acao(
    evento: EventoMonitoramento,
    perfil: PerfilIdoso,
    estado: EstadoEscalonamento,
    agora: datetime,
) -> tuple[EstadoEscalonamento, list[Alerta]]:
    if evento.status == StatusMonitoramento.NORMAL:
        return EstadoEscalonamento(estagio=EstagioEscalonamento.RESOLVIDO), []

    if estado.estagio == EstagioEscalonamento.OCIOSO:
        novo_estado = EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=agora)
        alerta = Alerta(
            nivel=NivelAlerta.ATENCAO,
            destinatario=perfil.nome,
            canal=CanalAlerta.WHATSAPP,
            mensagem=f"Tudo bem? Detectamos: {evento.motivo}. Pode confirmar que está tudo certo?",
            timestamp=agora,
        )
        return novo_estado, [alerta]

    tempo_decorrido = agora - estado.iniciado_em

    if estado.estagio == EstagioEscalonamento.CONTATO_IDOSO:
        if tempo_decorrido < JANELA_CONTATO_IDOSO:
            return estado, []
        novo_estado = EstadoEscalonamento(estagio=EstagioEscalonamento.NOTIFICAR_FAMILIA, iniciado_em=agora)
        alertas = [
            Alerta(
                nivel=NivelAlerta.CRITICO,
                destinatario=contato.nome,
                canal=CanalAlerta.WHATSAPP,
                mensagem=f"Atenção: {perfil.nome} não respondeu. Motivo do alerta: {evento.motivo}.",
                timestamp=agora,
            )
            for contato in perfil.contatos_familiares
        ]
        return novo_estado, alertas

    if estado.estagio == EstagioEscalonamento.NOTIFICAR_FAMILIA:
        if tempo_decorrido < JANELA_NOTIFICAR_FAMILIA:
            return estado, []
        novo_estado = EstadoEscalonamento(estagio=EstagioEscalonamento.SIMULAR_EMERGENCIA, iniciado_em=agora)
        alerta = Alerta(
            nivel=NivelAlerta.CRITICO,
            destinatario="servico_emergencia_simulado",
            canal=CanalAlerta.WHATSAPP,
            mensagem=(
                f"[SIMULAÇÃO] Acionamento de serviço de emergência para {perfil.nome}. "
                f"Motivo: {evento.motivo}. Nenhuma ligação real foi realizada."
            ),
            timestamp=agora,
        )
        return novo_estado, [alerta]

    return estado, []
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_domain_emergencia.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add zela/domain/emergencia.py tests/test_domain_emergencia.py
git commit -m "feat: maquina de estados de escalonamento do agente de emergencia"
```

---

### Task 10: Agentes ADK — esqueleto de orquestração

**Files:**
- Create: `zela/agents/orchestrator.py`
- Test: `tests/test_agents_orchestrator.py`

**Interfaces:**
- Consumes: `google.adk.agents.Agent`.
- Produces: `montar_agente_rotina(model: str = MODELO_PADRAO) -> Agent`, `montar_agente_monitoramento(...) -> Agent`, `montar_agente_comunicacao(...) -> Agent`, `montar_agente_emergencia(...) -> Agent`, `montar_orquestrador(...) -> Agent`.

Este task só monta o **esqueleto estrutural** dos 5 agentes (nome, descrição, instruction, hierarquia `sub_agents`) — sem `tools` ainda. A decisão de como cada agente vai *de fato* chamar as funções de domínio como `tools` depende de uma decisão de estado/persistência que é escopo do Plano 2 (ver Global Constraints). Os testes aqui são estruturais (nome, hierarquia) e não fazem nenhuma chamada de rede/LLM.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_agents_orchestrator.py
from zela.agents.orchestrator import (
    montar_agente_comunicacao,
    montar_agente_emergencia,
    montar_agente_monitoramento,
    montar_agente_rotina,
    montar_orquestrador,
)


def test_cada_agente_especializado_tem_nome_esperado():
    assert montar_agente_rotina().name == "agente_rotina"
    assert montar_agente_monitoramento().name == "agente_monitoramento"
    assert montar_agente_comunicacao().name == "agente_comunicacao"
    assert montar_agente_emergencia().name == "agente_emergencia"


def test_orquestrador_tem_os_quatro_subagentes_e_nome_proprio():
    orquestrador = montar_orquestrador()
    nomes_subagentes = {sub_agente.name for sub_agente in orquestrador.sub_agents}
    assert nomes_subagentes == {
        "agente_rotina",
        "agente_monitoramento",
        "agente_comunicacao",
        "agente_emergencia",
    }
    assert orquestrador.name == "orquestrador_zela"
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_agents_orchestrator.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.agents.orchestrator'`

- [ ] **Step 3: Implementar `zela/agents/orchestrator.py`**

```python
from google.adk.agents import Agent

MODELO_PADRAO = "gemini-2.0-flash"


def montar_agente_rotina(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_rotina",
        model=model,
        description="Gerencia lembretes de medicamentos e compromissos do idoso.",
        instruction=(
            "Verifique a agenda de medicamentos do idoso e avise quando houver "
            "lembretes pendentes. Registre confirmações quando o idoso informar "
            "que tomou o medicamento."
        ),
    )


def montar_agente_monitoramento(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_monitoramento",
        model=model,
        description="Analisa leituras de sensores e classifica o status de risco do idoso.",
        instruction=(
            "Avalie as leituras de sensores recebidas e classifique o status como "
            "normal, atenção ou risco, explicando o motivo."
        ),
    )


def montar_agente_comunicacao(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_comunicacao",
        model=model,
        description="Conversa com o idoso e a família via WhatsApp e Streamlit.",
        instruction=(
            "Formate lembretes de forma simples e acolhedora para o idoso, e "
            "interprete as respostas recebidas."
        ),
    )


def montar_agente_emergencia(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_emergencia",
        model=model,
        description="Decide o escalonamento de alertas em situações de risco.",
        instruction=(
            "Quando o agente de monitoramento indicar risco, decida a próxima "
            "ação de escalonamento seguindo a política de camadas: contato com "
            "o idoso, depois família, depois simulação de contato de emergência."
        ),
    )


def montar_orquestrador(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="orquestrador_zela",
        model=model,
        description="Coordena os agentes especializados do Zela+.",
        instruction=(
            "Você é o orquestrador do Zela+. Direcione cada solicitação ao "
            "agente especializado apropriado: rotina/medicação, monitoramento "
            "de saúde/risco, comunicação, ou emergência."
        ),
        sub_agents=[
            montar_agente_rotina(model=model),
            montar_agente_monitoramento(model=model),
            montar_agente_comunicacao(model=model),
            montar_agente_emergencia(model=model),
        ],
    )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_agents_orchestrator.py -v`
Expected: 2 passed

Se a instalação do `google-adk` expuser uma API diferente da esperada (por exemplo, o parâmetro `sub_agents` tiver outro nome), rode `python -c "from google.adk.agents import Agent; help(Agent.__init__)"` e ajuste as chamadas acima de acordo com a versão instalada — a biblioteca evolui rápido e a assinatura exata pode ter mudado desde a escrita deste plano.

- [ ] **Step 5: Commit**

```bash
git add zela/agents/orchestrator.py tests/test_agents_orchestrator.py
git commit -m "feat: esqueleto dos 5 agentes ADK (orquestrador + 4 especializados)"
```

---

### Task 11: Simulação de ponta a ponta (walking skeleton)

**Files:**
- Create: `zela/simulacao.py`
- Test: `tests/test_simulacao.py`

**Interfaces:**
- Consumes: todas as funções de domínio das Tasks 6-9.
- Produces: `RelatorioSimulacao(lembretes_enviados, confirmacoes, alertas)`, `simular_dia(perfil, medicamentos, leituras, resposta_idoso, agora) -> RelatorioSimulacao`.

Este é o teste de integração que comprova que a Fundação funciona de ponta a ponta (sem ADK, sem hardware, sem rede) — o "walking skeleton" do MVP.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_simulacao.py
from datetime import datetime, time, timedelta

from zela.models.comunicacao import MensagemEntrada, TipoMensagem
from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.models.rotina import Dosagem, Medicamento
from zela.simulacao import simular_dia


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        data_nascimento=datetime(1945, 3, 12).date(),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def test_simulacao_gera_lembrete_e_confirmacao_quando_idoso_responde_positivo():
    agora = datetime(2026, 9, 13, 8, 0)
    medicamento = Medicamento(
        id="med-1",
        nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"),
        horarios=[time(8, 0)],
    )
    leitura_presenca = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=agora,
    )
    resposta = MensagemEntrada(
        remetente="idosa",
        tipo=TipoMensagem.TEXTO,
        conteudo_bruto="tomei sim",
        timestamp=agora,
    )

    relatorio = simular_dia(_perfil(), [medicamento], [leitura_presenca], resposta, agora)

    assert len(relatorio.lembretes_enviados) == 1
    assert len(relatorio.confirmacoes) == 1
    assert relatorio.alertas == []


def test_simulacao_escalona_quando_nao_ha_presenca_por_muitas_horas():
    agora = datetime(2026, 9, 13, 14, 0)
    ultima_presenca = agora - timedelta(hours=8)
    leitura_presenca = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=ultima_presenca,
    )

    relatorio = simular_dia(_perfil(), [], [leitura_presenca], None, agora)

    assert len(relatorio.alertas) == 1
    assert relatorio.alertas[0].destinatario == "Maria da Silva"
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_simulacao.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.simulacao'`

- [ ] **Step 3: Implementar `zela/simulacao.py`**

```python
from dataclasses import dataclass, field
from datetime import datetime

from zela.domain.comunicacao import formatar_lembrete, interpretar_resposta
from zela.domain.emergencia import EstadoEscalonamento, decidir_proxima_acao
from zela.domain.monitoramento import classificar_por_regra
from zela.domain.rotina import calcular_lembretes_pendentes, registrar_confirmacao
from zela.models.alertas import Alerta
from zela.models.comunicacao import MensagemEntrada
from zela.models.monitoramento import LeituraSensor
from zela.models.perfil import PerfilIdoso
from zela.models.rotina import ConfirmacaoMedicacao, Medicamento


@dataclass
class RelatorioSimulacao:
    lembretes_enviados: list[str] = field(default_factory=list)
    confirmacoes: list[ConfirmacaoMedicacao] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)


def simular_dia(
    perfil: PerfilIdoso,
    medicamentos: list[Medicamento],
    leituras: list[LeituraSensor],
    resposta_idoso: MensagemEntrada | None,
    agora: datetime,
) -> RelatorioSimulacao:
    relatorio = RelatorioSimulacao()

    pendentes = calcular_lembretes_pendentes(medicamentos, [], agora)
    for medicamento in pendentes:
        relatorio.lembretes_enviados.append(formatar_lembrete(medicamento))
        if resposta_idoso is not None and interpretar_resposta(resposta_idoso):
            confirmacao = registrar_confirmacao(medicamento, horario_previsto=agora, agora=agora)
            relatorio.confirmacoes.append(confirmacao)

    evento = classificar_por_regra(leituras, agora)
    estado = EstadoEscalonamento()
    _, alertas = decidir_proxima_acao(evento, perfil, estado, agora)
    relatorio.alertas.extend(alertas)

    return relatorio
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_simulacao.py -v`
Expected: 2 passed

- [ ] **Step 5: Rodar a suíte completa de testes do Plano 1**

Run: `pytest -v`
Expected: todos os testes passam (aprox. 33 testes)

- [ ] **Step 6: Commit**

```bash
git add zela/simulacao.py tests/test_simulacao.py
git commit -m "feat: simulacao de ponta a ponta (walking skeleton) da fundacao do Zela+"
```

---

### Task 12: README inicial

**Files:**
- Create: `README.md`

**Interfaces:**
- Nenhuma (documentação).

- [ ] **Step 1: Escrever `README.md`**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README inicial do projeto Zela+"
```
