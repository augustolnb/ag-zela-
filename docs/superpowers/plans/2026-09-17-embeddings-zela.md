# Zela+ — Embeddings: Classificação por Similaridade + RAG (Plano 4 de 7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar os dois usos de embeddings previstos na spec (seção 6) e ainda não construídos: classificação de urgência de mensagens de texto do idoso por similaridade (vizinho mais próximo), reaproveitando a mesma escada de escalonamento determinística dos Planos 1/3; e um RAG (busca semântica) sobre bulas de medicamentos e histórico de mensagens do idoso, exposto como uma ferramenta somente-leitura do Agente de Comunicação.

**Architecture:** Um novo pacote `zela/embeddings/` isola tudo que depende de I/O externo (API de embeddings do Gemini, vector store Chroma local) das camadas puras já existentes. A classificação por similaridade produz um `EventoMonitoramento(metodo_classificacao=EMBEDDING)` — um tipo já previsto desde o Plano 1 mas nunca usado — que entra pela mesma porta que os sensores: `storage/escalonamento.py::aplicar_escalonamento`, que por sua vez chama `decidir_proxima_acao` (domínio, Plano 1, intocado). **O embedding nunca decide escalonamento** — ele só produz um status, exatamente como `classificar_por_regra` já faz para sensores. O RAG é uma ferramenta ADK somente-leitura, no mesmo padrão dos tools de monitoramento/emergência do Plano 3.

**Tech Stack:** `google-genai` (já instalado transitivamente via `google-adk` 2.9.0, versão 2.23.0 confirmada — mesma credencial `GOOGLE_API_KEY`/`GEMINI_API_KEY` já documentada no README) para embeddings (`text-embedding-004`); `chromadb` (novo, versão 1.5.9 verificada nesta máquina) como vector store local persistido em disco.

**Spec:** `docs/superpowers/specs/2026-09-10-cuida-mais-agente-idoso-design.md` (seção 6 e, em detalhe, a nova seção 15).

## Global Constraints

- Python 3.11+, mesmas convenções dos Planos 1-3.
- **A camada `zela/domain/` não muda neste plano** — continua pura, sem I/O.
- **Nenhuma chamada real de rede em teste automatizado.** `client.py` (Gemini) é sempre testado com um SDK fake injetado; `vetorial.py` (Chroma) é testado com uma instância real, mas 100% local/offline (sem download de modelo — embeddings são sempre passados prontos, nunca calculados pelo Chroma).
- **`ClienteEmbeddingGemini` deve ser preguiçoso (lazy):** construir `genai.Client()` de verdade no `__init__` levanta `ValueError` se `GOOGLE_API_KEY`/`GEMINI_API_KEY` não estiver no ambiente — e isso quebraria a suíte de testes inteira, já que `zela/api/main.py` é importado por `tests/test_api_main.py` sem nenhuma chave configurada. A construção do cliente real só pode acontecer dentro de `obter_embedding`, na primeira chamada — nunca em `__init__`.
- **Falha de embedding ou de indexação nunca pode propagar para o webhook** (spec §10, mesma filosofia já usada para falha de envio de WhatsApp): sempre `try/except` + log, nunca deixar a exceção subir.
- A classificação por embedding entra pela mesma porta que os sensores (`aplicar_escalonamento`) — mesmo um `RISCO` vindo de embedding começa pela etapa `CONTATO_IDOSO` (10 min de espera), nunca pula direto para notificar a família.
- Nome do projeto: **Zela+**. Escopo de idoso único (`id_idoso = "idosa-1"`), mesma convenção dos planos anteriores.
- Novas dependências (`pyproject.toml`): `google-genai>=2.0,<3` (declarada explicitamente, embora já viesse transitivamente) e `chromadb>=1.5,<2`.
- Novo diretório de dados local: `./chroma_db/` — adicionar ao `.gitignore` (mesmo tratamento já dado a `zela.db`).

---

## Mapa de arquivos deste plano

```
zela/
  embeddings/                       # NOVO pacote
    __init__.py
    exemplos_referencia.py           # ExemploReferencia + lista estática rotulada (normal/atencao/risco)
    classificador.py                  # puro: similaridade de cosseno + classificar_por_similaridade
    client.py                          # ClienteEmbeddingGemini (lazy, wrap google-genai)
    vetorial.py                         # RepositorioVetorial (wrap chromadb, isolado por idoso_id)
  models/
    rotina.py                         # MODIFICADO: Medicamento ganha campo `bula: str | None`
  storage/
    db.py                              # MODIFICADO: coluna `bula` na tabela medicamento
    rotina.py                          # MODIFICADO: salvar_medicamento/_linha_para_medicamento incluem bula
  api/
    reindexacao.py                    # NOVO: reindexar_documentos (bulas -> Chroma, chamado no boot)
    monitoramento_mensagem.py          # NOVO: processar_risco_mensagem (mensagem -> classificação -> escalonamento -> indexação)
    scheduler.py                        # MODIFICADO: extrai despachar_alertas (reaproveitado por monitoramento_mensagem.py)
    webhook.py                           # MODIFICADO: novo parâmetro opcional processar_risco
    main.py                               # MODIFICADO: wiring completo do pacote embeddings
  agents/
    orchestrator.py                       # MODIFICADO: agente_comunicacao ganha tool consultar_conhecimento
tests/
  test_embeddings_exemplos_referencia.py
  test_embeddings_classificador.py
  test_embeddings_client.py
  test_embeddings_vetorial.py
  test_storage_rotina.py                    # MODIFICADO: round-trip do campo bula
  test_api_reindexacao.py
  test_api_monitoramento_mensagem.py
  test_api_scheduler.py                      # MODIFICADO: teste dedicado de despachar_alertas
  test_api_webhook.py                         # MODIFICADO: novo teste de processar_risco
  test_api_main.py                             # MODIFICADO: monkeypatch de reindexar_documentos no lifespan
  test_agents_orchestrator_tools_comunicacao.py  # NOVO
README.md                                        # MODIFICADO: setup de embeddings/Chroma, nota de migração do zela.db
pyproject.toml                                    # MODIFICADO: google-genai, chromadb
.gitignore                                         # MODIFICADO: chroma_db/
```

---

### Task 1: Exemplos de referência rotulados

**Files:**
- Create: `zela/embeddings/__init__.py`
- Create: `zela/embeddings/exemplos_referencia.py`
- Test: `tests/test_embeddings_exemplos_referencia.py`

**Interfaces:**
- Consumes: `zela.models.monitoramento.StatusMonitoramento` (Plano 1).
- Produces: `ExemploReferencia` (Pydantic: `texto: str`, `status: StatusMonitoramento`); `EXEMPLOS_REFERENCIA: list[ExemploReferencia]`.

- [ ] **Step 1: Criar o pacote e escrever o teste que falha**

Crie `zela/embeddings/__init__.py` com conteúdo **completamente vazio** (0 bytes) — apenas marca o diretório como pacote Python.

```python
# tests/test_embeddings_exemplos_referencia.py
from zela.embeddings.exemplos_referencia import EXEMPLOS_REFERENCIA
from zela.models.monitoramento import StatusMonitoramento


def test_ha_pelo_menos_um_exemplo_por_status():
    status_presentes = {exemplo.status for exemplo in EXEMPLOS_REFERENCIA}
    assert status_presentes == {
        StatusMonitoramento.NORMAL,
        StatusMonitoramento.ATENCAO,
        StatusMonitoramento.RISCO,
    }


def test_ha_pelo_menos_cinco_exemplos_por_status():
    from collections import Counter

    contagem = Counter(exemplo.status for exemplo in EXEMPLOS_REFERENCIA)
    assert all(quantidade >= 5 for quantidade in contagem.values())


def test_textos_dos_exemplos_sao_unicos():
    textos = [exemplo.texto for exemplo in EXEMPLOS_REFERENCIA]
    assert len(textos) == len(set(textos))
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_embeddings_exemplos_referencia.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.embeddings.exemplos_referencia'`

- [ ] **Step 3: Implementar `exemplos_referencia.py`**

```python
# zela/embeddings/exemplos_referencia.py
from pydantic import BaseModel

from zela.models.monitoramento import StatusMonitoramento


class ExemploReferencia(BaseModel):
    texto: str
    status: StatusMonitoramento


EXEMPLOS_REFERENCIA: list[ExemploReferencia] = [
    # NORMAL
    ExemploReferencia(texto="Estou bem, acabei de almoçar.", status=StatusMonitoramento.NORMAL),
    ExemploReferencia(texto="Tudo tranquilo por aqui, só assistindo TV.", status=StatusMonitoramento.NORMAL),
    ExemploReferencia(texto="Já tomei o remédio, obrigado por perguntar.", status=StatusMonitoramento.NORMAL),
    ExemploReferencia(texto="Dormi bem essa noite, acordei descansada.", status=StatusMonitoramento.NORMAL),
    ExemploReferencia(texto="Fui dar uma volta no quintal, está um dia bonito.", status=StatusMonitoramento.NORMAL),
    ExemploReferencia(texto="Estou me sentindo bem hoje, sem dores.", status=StatusMonitoramento.NORMAL),
    # ATENÇÃO
    ExemploReferencia(texto="Estou meio tonta hoje, mas acho que já vai passar.", status=StatusMonitoramento.ATENCAO),
    ExemploReferencia(texto="Tive um pouco de dor de cabeça a tarde toda.", status=StatusMonitoramento.ATENCAO),
    ExemploReferencia(texto="Não dormi muito bem essa noite, me sinto cansada.", status=StatusMonitoramento.ATENCAO),
    ExemploReferencia(texto="Esqueci de tomar o remédio no horário certo.", status=StatusMonitoramento.ATENCAO),
    ExemploReferencia(texto="Estou com um pouco de falta de ar, nada muito forte.", status=StatusMonitoramento.ATENCAO),
    ExemploReferencia(texto="Sinto o coração meio acelerado desde de manhã.", status=StatusMonitoramento.ATENCAO),
    # RISCO
    ExemploReferencia(texto="Caí no banheiro e não consigo levantar.", status=StatusMonitoramento.RISCO),
    ExemploReferencia(texto="Estou com uma dor muito forte no peito.", status=StatusMonitoramento.RISCO),
    ExemploReferencia(texto="Não estou conseguindo respirar direito, socorro.", status=StatusMonitoramento.RISCO),
    ExemploReferencia(texto="Estou muito tonta e achei que ia desmaiar agora.", status=StatusMonitoramento.RISCO),
    ExemploReferencia(texto="Bati a cabeça forte e estou sangrando.", status=StatusMonitoramento.RISCO),
    ExemploReferencia(texto="Não consigo mexer o braço direito, acho que é AVC.", status=StatusMonitoramento.RISCO),
]
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_embeddings_exemplos_referencia.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
git add zela/embeddings/__init__.py zela/embeddings/exemplos_referencia.py tests/test_embeddings_exemplos_referencia.py
git commit -m "feat: adiciona exemplos de referencia rotulados para classificacao por embedding"
```

---

### Task 2: Classificador por similaridade (puro)

**Files:**
- Create: `zela/embeddings/classificador.py`
- Test: `tests/test_embeddings_classificador.py`

**Interfaces:**
- Consumes: `zela.embeddings.exemplos_referencia.ExemploReferencia` (Task 1), `zela.models.monitoramento.{EventoMonitoramento, MetodoClassificacao, StatusMonitoramento}` (Plano 1).
- Produces: `similaridade_cosseno(a: list[float], b: list[float]) -> float`; `classificar_por_similaridade(embedding_mensagem: list[float], exemplos_com_embedding: list[tuple[ExemploReferencia, list[float]]], texto_original: str, agora: datetime) -> EventoMonitoramento`.

Esta função é **pura**: recebe embeddings já calculados (nunca chama uma API), então é testável sem rede com vetores fixos. `exemplos_com_embedding` pareia cada `ExemploReferencia` com seu vetor de embedding — quem calcula esses vetores é a camada de cima (Task 7/10), não esta função.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_embeddings_classificador.py
from datetime import datetime

import pytest

from zela.embeddings.classificador import classificar_por_similaridade, similaridade_cosseno
from zela.embeddings.exemplos_referencia import ExemploReferencia
from zela.models.monitoramento import MetodoClassificacao, StatusMonitoramento


def test_similaridade_cosseno_vetores_identicos_e_um():
    assert similaridade_cosseno([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_similaridade_cosseno_vetores_ortogonais_e_zero():
    assert similaridade_cosseno([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_similaridade_cosseno_vetor_nulo_retorna_zero():
    assert similaridade_cosseno([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_classifica_pelo_exemplo_mais_similar():
    exemplo_normal = ExemploReferencia(texto="Estou bem", status=StatusMonitoramento.NORMAL)
    exemplo_risco = ExemploReferencia(texto="Caí e não consigo levantar", status=StatusMonitoramento.RISCO)
    exemplos_com_embedding = [
        (exemplo_normal, [1.0, 0.0, 0.0]),
        (exemplo_risco, [0.0, 1.0, 0.0]),
    ]
    agora = datetime(2026, 9, 17, 10, 0)

    evento = classificar_por_similaridade(
        embedding_mensagem=[0.05, 0.95, 0.0],
        exemplos_com_embedding=exemplos_com_embedding,
        texto_original="acabei de cair no chão",
        agora=agora,
    )

    assert evento.status == StatusMonitoramento.RISCO
    assert evento.metodo_classificacao == MetodoClassificacao.EMBEDDING
    assert evento.timestamp == agora
    assert "acabei de cair no chão" in evento.motivo
    assert evento.leituras_relacionadas == []


def test_classifica_como_normal_quando_mais_proximo_do_exemplo_normal():
    exemplo_normal = ExemploReferencia(texto="Estou bem", status=StatusMonitoramento.NORMAL)
    exemplo_risco = ExemploReferencia(texto="Caí e não consigo levantar", status=StatusMonitoramento.RISCO)
    exemplos_com_embedding = [
        (exemplo_normal, [1.0, 0.0, 0.0]),
        (exemplo_risco, [0.0, 1.0, 0.0]),
    ]

    evento = classificar_por_similaridade(
        embedding_mensagem=[0.95, 0.05, 0.0],
        exemplos_com_embedding=exemplos_com_embedding,
        texto_original="tudo bem por aqui",
        agora=datetime(2026, 9, 17, 10, 0),
    )

    assert evento.status == StatusMonitoramento.NORMAL


def test_lista_de_exemplos_vazia_levanta_erro():
    with pytest.raises(ValueError):
        classificar_por_similaridade(
            embedding_mensagem=[1.0, 0.0],
            exemplos_com_embedding=[],
            texto_original="oi",
            agora=datetime(2026, 9, 17, 10, 0),
        )
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_embeddings_classificador.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.embeddings.classificador'`

- [ ] **Step 3: Implementar `classificador.py`**

```python
# zela/embeddings/classificador.py
import math
from datetime import datetime

from zela.embeddings.exemplos_referencia import ExemploReferencia
from zela.models.monitoramento import EventoMonitoramento, MetodoClassificacao


def similaridade_cosseno(a: list[float], b: list[float]) -> float:
    produto_escalar = sum(x * y for x, y in zip(a, b))
    norma_a = math.sqrt(sum(x * x for x in a))
    norma_b = math.sqrt(sum(y * y for y in b))
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return produto_escalar / (norma_a * norma_b)


def classificar_por_similaridade(
    embedding_mensagem: list[float],
    exemplos_com_embedding: list[tuple[ExemploReferencia, list[float]]],
    texto_original: str,
    agora: datetime,
) -> EventoMonitoramento:
    if not exemplos_com_embedding:
        raise ValueError("exemplos_com_embedding não pode ser vazio")

    exemplo_mais_similar, _ = max(
        exemplos_com_embedding,
        key=lambda par: similaridade_cosseno(embedding_mensagem, par[1]),
    )

    return EventoMonitoramento(
        status=exemplo_mais_similar.status,
        motivo=(
            f"Mensagem do idoso classificada por similaridade a exemplo de "
            f"referência ('{exemplo_mais_similar.texto}'): \"{texto_original}\""
        ),
        timestamp=agora,
        metodo_classificacao=MetodoClassificacao.EMBEDDING,
    )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_embeddings_classificador.py -v`
Expected: PASS (6 testes)

- [ ] **Step 5: Commit**

```bash
git add zela/embeddings/classificador.py tests/test_embeddings_classificador.py
git commit -m "feat: adiciona classificador puro de urgencia por similaridade de embeddings"
```

---

### Task 3: Cliente de embeddings Gemini (lazy)

**Files:**
- Create: `zela/embeddings/client.py`
- Test: `tests/test_embeddings_client.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `google.genai` (SDK já instalado, `google-genai==2.23.0`).
- Produces: `ClienteEmbeddingGemini(modelo: str = "text-embedding-004", cliente_sdk=None)` com método `obter_embedding(texto: str) -> list[float]`.

**Crítico:** o construtor **não pode** instanciar `genai.Client()` de verdade — isso levanta `ValueError` sem uma chave de API no ambiente, e quebraria toda a suíte de testes (que importa `zela/api/main.py` sem nenhuma chave configurada). A construção real só pode acontecer dentro de `obter_embedding`, e só se `cliente_sdk` não tiver sido injetado.

- [ ] **Step 1: Adicionar a dependência em `pyproject.toml`**

Abra `pyproject.toml` e adicione `"google-genai>=2.0,<3",` à lista `dependencies` (já está instalada transitivamente via `google-adk`, mas passa a ser uma dependência direta e explícita já que `zela/embeddings/client.py` importa `google.genai` diretamente).

- [ ] **Step 2: Escrever os testes que falham**

```python
# tests/test_embeddings_client.py
from zela.embeddings.client import ClienteEmbeddingGemini


class _EmbeddingFalso:
    def __init__(self, values):
        self.values = values


class _RespostaFalsa:
    def __init__(self, values):
        self.embeddings = [_EmbeddingFalso(values)]


class _ModelsFalso:
    def __init__(self, values):
        self._values = values
        self.chamadas = []

    def embed_content(self, model, contents):
        self.chamadas.append((model, contents))
        return _RespostaFalsa(self._values)


class _ClienteSdkFalso:
    def __init__(self, values):
        self.models = _ModelsFalso(values)


def test_obter_embedding_usa_o_sdk_injetado():
    sdk_falso = _ClienteSdkFalso([0.1, 0.2, 0.3])
    cliente = ClienteEmbeddingGemini(cliente_sdk=sdk_falso)

    resultado = cliente.obter_embedding("estou bem hoje")

    assert resultado == [0.1, 0.2, 0.3]
    assert sdk_falso.models.chamadas == [("text-embedding-004", "estou bem hoje")]


def test_obter_embedding_usa_modelo_customizado():
    sdk_falso = _ClienteSdkFalso([0.5])
    cliente = ClienteEmbeddingGemini(modelo="outro-modelo", cliente_sdk=sdk_falso)

    cliente.obter_embedding("oi")

    assert sdk_falso.models.chamadas == [("outro-modelo", "oi")]


def test_construtor_nao_instancia_sdk_real_sem_chave_de_api(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Não deve levantar exceção: a construção do genai.Client() real é
    # adiada até a primeira chamada a obter_embedding, não acontece aqui.
    cliente = ClienteEmbeddingGemini()

    assert cliente is not None
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_embeddings_client.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.embeddings.client'`

- [ ] **Step 4: Implementar `client.py`**

```python
# zela/embeddings/client.py
from google import genai

MODELO_PADRAO = "text-embedding-004"


class ClienteEmbeddingGemini:
    def __init__(self, modelo: str = MODELO_PADRAO, cliente_sdk=None):
        self._modelo = modelo
        self._cliente_sdk_injetado = cliente_sdk
        self._cliente_sdk_lazy = None

    def _obter_cliente_sdk(self):
        if self._cliente_sdk_injetado is not None:
            return self._cliente_sdk_injetado
        if self._cliente_sdk_lazy is None:
            self._cliente_sdk_lazy = genai.Client()
        return self._cliente_sdk_lazy

    def obter_embedding(self, texto: str) -> list[float]:
        resposta = self._obter_cliente_sdk().models.embed_content(model=self._modelo, contents=texto)
        return list(resposta.embeddings[0].values)
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_embeddings_client.py -v`
Expected: PASS (3 testes)

- [ ] **Step 6: Instalar a dependência e rodar a suíte completa**

Run: `pip install -e .` (ou `pip install "google-genai>=2.0,<3"` se preferir instalar direto)
Run: `pytest -q`
Expected: todos os testes (incluindo os pré-existentes) continuam passando — `google-genai` já estava instalado transitivamente, então isso só formaliza a dependência.

- [ ] **Step 7: Commit**

```bash
git add zela/embeddings/client.py tests/test_embeddings_client.py pyproject.toml
git commit -m "feat: adiciona cliente lazy de embeddings do Gemini"
```

---

### Task 4: Vector store (Chroma) isolado por idoso

**Files:**
- Create: `zela/embeddings/vetorial.py`
- Test: `tests/test_embeddings_vetorial.py`
- Modify: `pyproject.toml`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `chromadb` (novo, `chromadb==1.5.9` verificado).
- Produces: `RepositorioVetorial(caminho: str = "./chroma_db", nome_colecao: str = "conhecimento_zela")` com métodos `indexar_documento(idoso_id: str, doc_id: str, texto: str, embedding: list[float], tipo: str) -> None` e `buscar_similares(idoso_id: str, embedding_consulta: list[float], k: int = 3) -> list[str]`.

`indexar_documento` usa `upsert` (idempotente por `doc_id`) — reindexar o mesmo documento atualiza em vez de duplicar. `buscar_similares` sempre filtra por `idoso_id` (isolamento por tenant, mesma preocupação já tratada nos Planos 1/3 para `leitura_sensor`/`alerta`).

- [ ] **Step 1: Adicionar a dependência e o `.gitignore`**

Em `pyproject.toml`, adicione `"chromadb>=1.5,<2",` à lista `dependencies`.

Em `.gitignore`, adicione uma linha `chroma_db/` (mesmo tratamento já dado a `zela.db`).

- [ ] **Step 2: Escrever os testes que falham**

```python
# tests/test_embeddings_vetorial.py
from zela.embeddings.vetorial import RepositorioVetorial


def test_buscar_similares_filtra_por_idoso(tmp_path):
    repo = RepositorioVetorial(caminho=str(tmp_path / "chroma"))
    repo.indexar_documento(
        idoso_id="idosa-1", doc_id="doc-a", texto="bula da losartana",
        embedding=[1.0, 0.0], tipo="bula",
    )
    repo.indexar_documento(
        idoso_id="idosa-2", doc_id="doc-b", texto="bula de outro idoso",
        embedding=[1.0, 0.0], tipo="bula",
    )

    resultados = repo.buscar_similares(idoso_id="idosa-1", embedding_consulta=[1.0, 0.0], k=5)

    assert resultados == ["bula da losartana"]


def test_indexar_documento_e_idempotente_por_id(tmp_path):
    repo = RepositorioVetorial(caminho=str(tmp_path / "chroma"))
    repo.indexar_documento(
        idoso_id="idosa-1", doc_id="doc-a", texto="versão antiga",
        embedding=[1.0, 0.0], tipo="bula",
    )
    repo.indexar_documento(
        idoso_id="idosa-1", doc_id="doc-a", texto="versão nova",
        embedding=[1.0, 0.0], tipo="bula",
    )

    resultados = repo.buscar_similares(idoso_id="idosa-1", embedding_consulta=[1.0, 0.0], k=5)

    assert resultados == ["versão nova"]


def test_buscar_similares_sem_documentos_retorna_lista_vazia(tmp_path):
    repo = RepositorioVetorial(caminho=str(tmp_path / "chroma"))

    resultados = repo.buscar_similares(idoso_id="idosa-1", embedding_consulta=[1.0, 0.0], k=5)

    assert resultados == []


def test_buscar_similares_respeita_k(tmp_path):
    repo = RepositorioVetorial(caminho=str(tmp_path / "chroma"))
    for i in range(5):
        repo.indexar_documento(
            idoso_id="idosa-1", doc_id=f"doc-{i}", texto=f"mensagem {i}",
            embedding=[1.0, 0.0], tipo="mensagem",
        )

    resultados = repo.buscar_similares(idoso_id="idosa-1", embedding_consulta=[1.0, 0.0], k=2)

    assert len(resultados) == 2
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_embeddings_vetorial.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.embeddings.vetorial'` (ou `ModuleNotFoundError: No module named 'chromadb'` se a Step 1 ainda não tiver sido instalada)

- [ ] **Step 4: Implementar `vetorial.py`**

```python
# zela/embeddings/vetorial.py
import chromadb
from chromadb.config import Settings

NOME_COLECAO_PADRAO = "conhecimento_zela"


class RepositorioVetorial:
    def __init__(self, caminho: str = "./chroma_db", nome_colecao: str = NOME_COLECAO_PADRAO):
        self._client = chromadb.PersistentClient(
            path=caminho, settings=Settings(anonymized_telemetry=False)
        )
        self._colecao = self._client.get_or_create_collection(name=nome_colecao)

    def indexar_documento(
        self, idoso_id: str, doc_id: str, texto: str, embedding: list[float], tipo: str
    ) -> None:
        self._colecao.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[texto],
            metadatas=[{"idoso_id": idoso_id, "tipo": tipo}],
        )

    def buscar_similares(self, idoso_id: str, embedding_consulta: list[float], k: int = 3) -> list[str]:
        resultado = self._colecao.query(
            query_embeddings=[embedding_consulta],
            n_results=k,
            where={"idoso_id": idoso_id},
        )
        documentos = resultado.get("documents") or []
        return documentos[0] if documentos else []
```

- [ ] **Step 5: Instalar a dependência**

Run: `pip install "chromadb>=1.5,<2"`

- [ ] **Step 6: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_embeddings_vetorial.py -v`
Expected: PASS (4 testes)

- [ ] **Step 7: Rodar a suíte completa (checagem de regressão)**

Run: `pytest -q`
Expected: todos os testes pré-existentes continuam passando (a instalação do chromadb traz consigo um upgrade de `opentelemetry-api`/`opentelemetry-sdk` que gera um aviso de conflito de dependências do `google-adk` no `pip install` — confirmado nesta máquina que isso **não** quebra nenhum teste, é apenas um aviso).

- [ ] **Step 8: Commit**

```bash
git add zela/embeddings/vetorial.py tests/test_embeddings_vetorial.py pyproject.toml .gitignore
git commit -m "feat: adiciona vector store Chroma isolado por idoso para RAG"
```

---

### Task 5: Campo `bula` em Medicamento

**Files:**
- Modify: `zela/models/rotina.py`
- Modify: `zela/storage/db.py`
- Modify: `zela/storage/rotina.py`
- Modify: `tests/test_storage_rotina.py` (crie o arquivo se ele ainda não existir neste projeto — verifique com `ls tests/test_storage_rotina.py` antes de começar)

**Interfaces:**
- Consumes: nada novo.
- Produces: `Medicamento.bula: str | None` (default `None`); `salvar_medicamento`/`listar_medicamentos` (assinaturas inalteradas) agora persistem/retornam esse campo.

**Nota de migração:** este plano adiciona uma coluna nova (`bula`) a uma tabela já existente desde o Plano 2 (`medicamento`). Como o schema usa `CREATE TABLE IF NOT EXISTS`, um `zela.db` local já criado por uma execução anterior da API **não** ganha a coluna nova automaticamente. Isso é aceitável para este MVP em desenvolvimento (documentado na Task 11/README): apague o `zela.db` local antes de rodar a API depois deste plano.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_storage_rotina.py (adicione a este arquivo se ele já existir, ou crie-o)
from zela.models.rotina import Dosagem, Medicamento
from zela.storage.db import conectar
from zela.storage.rotina import listar_medicamentos, salvar_medicamento
from datetime import time


def test_salvar_e_listar_medicamento_com_bula():
    conn = conectar(":memory:")
    medicamento = Medicamento(
        id="med-1", nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
        bula="Usado para pressão alta. Tomar em jejum.",
    )

    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")
    medicamentos = listar_medicamentos(conn, "idosa-1")

    assert len(medicamentos) == 1
    assert medicamentos[0].bula == "Usado para pressão alta. Tomar em jejum."


def test_salvar_e_listar_medicamento_sem_bula():
    conn = conectar(":memory:")
    medicamento = Medicamento(
        id="med-2", nome="Vitamina D",
        dosagem=Dosagem(quantidade=1, unidade="comprimido"), horarios=[time(9, 0)],
    )

    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")
    medicamentos = listar_medicamentos(conn, "idosa-1")

    assert medicamentos[0].bula is None
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `pytest tests/test_storage_rotina.py -v`
Expected: FAIL — `Medicamento` não aceita o argumento `bula` (`TypeError`/erro de validação Pydantic), ou a coluna `bula` não existe.

- [ ] **Step 3: Adicionar o campo ao modelo**

Em `zela/models/rotina.py`, na classe `Medicamento`, adicione o campo logo após `ativo`:

```python
    ativo: bool = True
    bula: str | None = None
```

- [ ] **Step 4: Adicionar a coluna ao schema**

Em `zela/storage/db.py`, na definição da tabela `medicamento`, adicione a coluna `bula` (nullable) logo após `ativo`:

```python
CREATE TABLE IF NOT EXISTS medicamento (
    id TEXT PRIMARY KEY,
    idoso_id TEXT NOT NULL,
    nome TEXT NOT NULL,
    dosagem_quantidade REAL NOT NULL,
    dosagem_unidade TEXT NOT NULL,
    horarios TEXT NOT NULL,
    dias_semana TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    bula TEXT
);
```

- [ ] **Step 5: Atualizar `salvar_medicamento` e `_linha_para_medicamento`**

Em `zela/storage/rotina.py`, substitua `salvar_medicamento` por:

```python
def salvar_medicamento(conn: sqlite3.Connection, medicamento: Medicamento, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO medicamento
            (id, idoso_id, nome, dosagem_quantidade, dosagem_unidade, horarios, dias_semana, ativo, bula)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nome = excluded.nome,
            dosagem_quantidade = excluded.dosagem_quantidade,
            dosagem_unidade = excluded.dosagem_unidade,
            horarios = excluded.horarios,
            dias_semana = excluded.dias_semana,
            ativo = excluded.ativo,
            bula = excluded.bula
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
            medicamento.bula,
        ),
    )
    conn.commit()
```

E `_linha_para_medicamento`:

```python
def _linha_para_medicamento(linha: sqlite3.Row) -> Medicamento:
    return Medicamento(
        id=linha["id"],
        nome=linha["nome"],
        dosagem=Dosagem(quantidade=linha["dosagem_quantidade"], unidade=linha["dosagem_unidade"]),
        horarios=[time.fromisoformat(h) for h in json.loads(linha["horarios"])],
        dias_semana=json.loads(linha["dias_semana"]),
        ativo=bool(linha["ativo"]),
        bula=linha["bula"],
    )
```

- [ ] **Step 6: Rodar o teste e confirmar que passa**

Run: `pytest tests/test_storage_rotina.py -v`
Expected: PASS (2 testes)

- [ ] **Step 7: Rodar a suíte completa (checagem de regressão)**

Run: `pytest -q`
Expected: todos os testes continuam passando — `Medicamento(...)` sem `bula` continua válido (default `None`), e chamadas existentes a `salvar_medicamento`/`listar_medicamentos` em outros testes não passam esse argumento.

- [ ] **Step 8: Commit**

```bash
git add zela/models/rotina.py zela/storage/db.py zela/storage/rotina.py tests/test_storage_rotina.py
git commit -m "feat: adiciona campo opcional de bula ao medicamento"
```

---

### Task 6: Reindexação em lote (bulas -> Chroma)

**Files:**
- Create: `zela/api/reindexacao.py`
- Test: `tests/test_api_reindexacao.py`

**Interfaces:**
- Consumes: `zela.storage.rotina.listar_medicamentos` (Plano 2, agora retornando `bula`), `RepositorioVetorial.indexar_documento` (Task 4), `ClienteEmbeddingGemini.obter_embedding` (Task 3, via injeção — o teste usa um fake).
- Produces: `reindexar_documentos(conn, idoso_id: str, repositorio_vetorial, cliente_embedding) -> int` (retorna a quantidade de documentos indexados).

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_api_reindexacao.py
from datetime import time

from zela.api.reindexacao import reindexar_documentos
from zela.embeddings.vetorial import RepositorioVetorial
from zela.models.rotina import Dosagem, Medicamento
from zela.storage.db import conectar
from zela.storage.rotina import salvar_medicamento


class _ClienteEmbeddingFalso:
    def obter_embedding(self, texto: str) -> list[float]:
        return [float(len(texto)), 0.0]


def test_reindexar_documentos_indexa_apenas_medicamentos_com_bula(tmp_path):
    conn = conectar(":memory:")
    salvar_medicamento(
        conn,
        Medicamento(
            id="med-1", nome="Losartana",
            dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
            bula="Usado para pressão alta.",
        ),
        idoso_id="idosa-1",
    )
    salvar_medicamento(
        conn,
        Medicamento(
            id="med-2", nome="Vitamina D",
            dosagem=Dosagem(quantidade=1, unidade="comprimido"), horarios=[time(9, 0)],
        ),
        idoso_id="idosa-1",
    )
    repositorio = RepositorioVetorial(caminho=str(tmp_path / "chroma"))
    cliente_embedding = _ClienteEmbeddingFalso()

    quantidade = reindexar_documentos(conn, "idosa-1", repositorio, cliente_embedding)

    assert quantidade == 1
    texto_esperado = "Losartana: Usado para pressão alta."
    resultados = repositorio.buscar_similares(
        idoso_id="idosa-1",
        embedding_consulta=[float(len(texto_esperado)), 0.0],
        k=5,
    )
    assert texto_esperado in resultados


def test_reindexar_documentos_sem_nenhum_medicamento_com_bula_retorna_zero(tmp_path):
    conn = conectar(":memory:")
    salvar_medicamento(
        conn,
        Medicamento(
            id="med-3", nome="Vitamina C",
            dosagem=Dosagem(quantidade=1, unidade="comprimido"), horarios=[time(10, 0)],
        ),
        idoso_id="idosa-1",
    )
    repositorio = RepositorioVetorial(caminho=str(tmp_path / "chroma"))

    quantidade = reindexar_documentos(conn, "idosa-1", repositorio, _ClienteEmbeddingFalso())

    assert quantidade == 0
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_api_reindexacao.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.api.reindexacao'`

- [ ] **Step 3: Implementar `reindexacao.py`**

```python
# zela/api/reindexacao.py
import sqlite3

from zela.storage.rotina import listar_medicamentos


def reindexar_documentos(
    conn: sqlite3.Connection,
    idoso_id: str,
    repositorio_vetorial,
    cliente_embedding,
) -> int:
    """Reindexa no vector store todos os medicamentos cadastrados que têm bula.

    Chamado no boot da API (zela/api/main.py, no ciclo de vida) para manter
    o RAG sincronizado com o que já está persistido no SQLite. Retorna a
    quantidade de documentos (re)indexados.
    """
    medicamentos_com_bula = [m for m in listar_medicamentos(conn, idoso_id) if m.bula]
    for medicamento in medicamentos_com_bula:
        texto = f"{medicamento.nome}: {medicamento.bula}"
        embedding = cliente_embedding.obter_embedding(texto)
        repositorio_vetorial.indexar_documento(
            idoso_id=idoso_id,
            doc_id=f"medicamento:{medicamento.id}",
            texto=texto,
            embedding=embedding,
            tipo="bula",
        )
    return len(medicamentos_com_bula)
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_reindexacao.py -v`
Expected: PASS (2 testes)

- [ ] **Step 5: Commit**

```bash
git add zela/api/reindexacao.py tests/test_api_reindexacao.py
git commit -m "feat: adiciona reindexacao em lote de bulas de medicamentos no vector store"
```

---

### Task 7: Extrair `despachar_alertas` do scheduler

**Files:**
- Modify: `zela/api/scheduler.py`
- Modify: `tests/test_api_scheduler.py`

**Interfaces:**
- Consumes: nada novo (refatoração interna).
- Produces: `despachar_alertas(conn, alertas: list[Alerta], perfil: PerfilIdoso, idoso_id: str, waha_client) -> None` — extraído do corpo de `verificar_e_escalonar_riscos`, para ser reaproveitado pela Task 8 (`monitoramento_mensagem.py`).

Esta task é uma refatoração pura: o comportamento de `verificar_e_escalonar_riscos` não muda, só deixa de ter o bloco de "salvar + enviar" inline.

- [ ] **Step 1: Escrever o teste novo que falha**

Adicione a `tests/test_api_scheduler.py` (o arquivo já importa `conectar`, `PerfilIdoso`, `ContatoFamiliar`, `date` — reaproveite o que já existe no topo do arquivo; a fixture `_perfil()` e a classe `_WahaFalso` já existem nesse arquivo):

```python
from zela.api.scheduler import despachar_alertas  # adicione este import
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta


def test_despachar_alertas_salva_e_envia_alertas_nao_simulados():
    conn = conectar(":memory:")
    perfil = _perfil()
    waha_falso = _WahaFalso()
    alerta_familia = Alerta(
        nivel=NivelAlerta.CRITICO, destinatario="João", canal=CanalAlerta.WHATSAPP,
        mensagem="Atenção, sem resposta.", timestamp=datetime(2026, 9, 17, 10, 0),
    )

    despachar_alertas(conn, [alerta_familia], perfil, "idosa-1", waha_falso)

    assert waha_falso.enviados == [("+5511987654321", "Atenção, sem resposta.")]
    assert len(listar_alertas(conn, "idosa-1")) == 1


def test_despachar_alertas_nao_envia_alerta_simulado():
    conn = conectar(":memory:")
    perfil = _perfil()
    waha_falso = _WahaFalso()
    alerta_simulado = Alerta(
        nivel=NivelAlerta.CRITICO, destinatario="servico_emergencia_simulado",
        canal=CanalAlerta.WHATSAPP, mensagem="[SIMULAÇÃO] ...",
        timestamp=datetime(2026, 9, 17, 10, 0), simulado=True,
    )

    despachar_alertas(conn, [alerta_simulado], perfil, "idosa-1", waha_falso)

    assert waha_falso.enviados == []
    assert len(listar_alertas(conn, "idosa-1")) == 1
```

(`listar_alertas` já é importado no topo do arquivo.)

- [ ] **Step 2: Rodar o teste novo e confirmar que falha**

Run: `pytest tests/test_api_scheduler.py -k despachar_alertas -v`
Expected: FAIL com `ImportError: cannot import name 'despachar_alertas'`

- [ ] **Step 3: Extrair a função em `scheduler.py`**

Em `zela/api/scheduler.py`, adicione a nova função (por exemplo, logo antes de `verificar_e_escalonar_riscos`):

```python
def despachar_alertas(
    conn, alertas: list[Alerta], perfil: PerfilIdoso, idoso_id: str, waha_client
) -> None:
    for alerta in alertas:
        salvar_alerta(conn, alerta, idoso_id)
        if alerta.simulado:
            continue
        telefone = _telefone_por_nome(perfil, alerta.destinatario)
        if telefone is not None:
            waha_client.enviar_texto(telefone, alerta.mensagem)
```

E substitua o final de `verificar_e_escalonar_riscos` (o laço `for alerta in alertas: ...`) por:

```python
    alertas = aplicar_escalonamento(conn, id_idoso, evento, perfil, agora)
    despachar_alertas(conn, alertas, perfil, id_idoso, waha_client)
    return alertas
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_scheduler.py -v`
Expected: PASS — os testes novos e **todos** os testes pré-existentes de `verificar_e_escalonar_riscos` continuam passando sem alteração (comportamento idêntico, só refatorado).

- [ ] **Step 5: Commit**

```bash
git add zela/api/scheduler.py tests/test_api_scheduler.py
git commit -m "refactor: extrai despachar_alertas do scheduler para reaproveitamento"
```

---

### Task 8: Processamento de risco por mensagem

**Files:**
- Create: `zela/api/monitoramento_mensagem.py`
- Test: `tests/test_api_monitoramento_mensagem.py`

**Interfaces:**
- Consumes: `zela.embeddings.classificador.classificar_por_similaridade` (Task 2), `zela.embeddings.exemplos_referencia.ExemploReferencia` (Task 1), `zela.storage.escalonamento.aplicar_escalonamento` (Plano 3), `zela.api.scheduler.despachar_alertas` (Task 7).
- Produces: `processar_risco_mensagem(conn, idoso_id: str, perfil: PerfilIdoso, texto: str, agora: datetime, cliente_embedding, exemplos_com_embedding: list[tuple[ExemploReferencia, list[float]]], repositorio_vetorial, waha_client) -> None`.

Esta função nunca levanta exceção (falha de embedding/indexação é logada e ignorada — spec §10). Ela é o ponto de integração central deste plano: mensagem → embedding → classificação → escalonamento determinístico (Plano 1/3, reaproveitado) → despacho de alertas → indexação da mensagem no RAG.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_api_monitoramento_mensagem.py
import logging
from datetime import date, datetime

from zela.api.monitoramento_mensagem import processar_risco_mensagem
from zela.embeddings.exemplos_referencia import ExemploReferencia
from zela.models.monitoramento import StatusMonitoramento
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.storage.db import conectar
from zela.storage.escalonamento import obter_estado


class _WahaFalso:
    def __init__(self):
        self.enviados = []

    def enviar_texto(self, telefone, texto):
        self.enviados.append((telefone, texto))


class _ClienteEmbeddingFalso:
    def __init__(self, vetor):
        self._vetor = vetor

    def obter_embedding(self, texto: str) -> list[float]:
        return self._vetor


class _ClienteEmbeddingComFalha:
    def obter_embedding(self, texto: str) -> list[float]:
        raise RuntimeError("Gemini fora do ar")


class _RepositorioVetorialFalso:
    def __init__(self):
        self.indexados = []

    def indexar_documento(self, idoso_id, doc_id, texto, embedding, tipo):
        self.indexados.append((idoso_id, doc_id, texto, embedding, tipo))


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def _exemplos_com_embedding():
    exemplo_normal = ExemploReferencia(texto="Estou bem", status=StatusMonitoramento.NORMAL)
    exemplo_risco = ExemploReferencia(texto="Caí e não consigo levantar", status=StatusMonitoramento.RISCO)
    return [(exemplo_normal, [1.0, 0.0]), (exemplo_risco, [0.0, 1.0])]


def test_mensagem_de_risco_inicia_escalonamento_e_indexa_mensagem():
    conn = conectar(":memory:")
    waha_falso = _WahaFalso()
    repositorio_falso = _RepositorioVetorialFalso()
    agora = datetime(2026, 9, 17, 10, 0)

    processar_risco_mensagem(
        conn, "idosa-1", _perfil(), "caí no banheiro", agora,
        _ClienteEmbeddingFalso([0.0, 1.0]), _exemplos_com_embedding(),
        repositorio_falso, waha_falso,
    )

    estado = obter_estado(conn, "idosa-1")
    assert estado.estagio.value == "contato_idoso"
    assert waha_falso.enviados == [("+5511911111111", waha_falso.enviados[0][1])]
    assert len(repositorio_falso.indexados) == 1
    assert repositorio_falso.indexados[0][0] == "idosa-1"
    assert repositorio_falso.indexados[0][2] == "caí no banheiro"
    assert repositorio_falso.indexados[0][4] == "mensagem"


def test_mensagem_normal_nao_aciona_alerta():
    conn = conectar(":memory:")
    waha_falso = _WahaFalso()
    repositorio_falso = _RepositorioVetorialFalso()

    processar_risco_mensagem(
        conn, "idosa-1", _perfil(), "estou bem", datetime(2026, 9, 17, 10, 0),
        _ClienteEmbeddingFalso([1.0, 0.0]), _exemplos_com_embedding(),
        repositorio_falso, waha_falso,
    )

    assert waha_falso.enviados == []
    assert len(repositorio_falso.indexados) == 1


def test_falha_no_embedding_e_isolada_e_nao_levanta(caplog):
    conn = conectar(":memory:")
    waha_falso = _WahaFalso()
    repositorio_falso = _RepositorioVetorialFalso()

    with caplog.at_level(logging.ERROR):
        processar_risco_mensagem(
            conn, "idosa-1", _perfil(), "estou bem", datetime(2026, 9, 17, 10, 0),
            _ClienteEmbeddingComFalha(), _exemplos_com_embedding(),
            repositorio_falso, waha_falso,
        )

    assert waha_falso.enviados == []
    assert repositorio_falso.indexados == []
    assert "Gemini fora do ar" in caplog.text or "Falha ao processar" in caplog.text
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_api_monitoramento_mensagem.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'zela.api.monitoramento_mensagem'`

- [ ] **Step 3: Implementar `monitoramento_mensagem.py`**

```python
# zela/api/monitoramento_mensagem.py
import logging
import sqlite3
from datetime import datetime

from zela.api.scheduler import despachar_alertas
from zela.embeddings.classificador import classificar_por_similaridade
from zela.embeddings.exemplos_referencia import ExemploReferencia
from zela.models.perfil import PerfilIdoso
from zela.storage.escalonamento import aplicar_escalonamento

logger = logging.getLogger(__name__)


def processar_risco_mensagem(
    conn: sqlite3.Connection,
    idoso_id: str,
    perfil: PerfilIdoso,
    texto: str,
    agora: datetime,
    cliente_embedding,
    exemplos_com_embedding: list[tuple[ExemploReferencia, list[float]]],
    repositorio_vetorial,
    waha_client,
) -> None:
    try:
        embedding_mensagem = cliente_embedding.obter_embedding(texto)
        evento = classificar_por_similaridade(embedding_mensagem, exemplos_com_embedding, texto, agora)
        alertas = aplicar_escalonamento(conn, idoso_id, evento, perfil, agora)
        despachar_alertas(conn, alertas, perfil, idoso_id, waha_client)
        doc_id = f"mensagem:{idoso_id}:{agora.isoformat()}"
        repositorio_vetorial.indexar_documento(
            idoso_id=idoso_id, doc_id=doc_id, texto=texto, embedding=embedding_mensagem, tipo="mensagem"
        )
    except Exception:
        logger.exception("Falha ao processar risco/indexação da mensagem do idoso")
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_monitoramento_mensagem.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
git add zela/api/monitoramento_mensagem.py tests/test_api_monitoramento_mensagem.py
git commit -m "feat: adiciona processamento de risco por mensagem via embedding"
```

---

### Task 9: Wiring no webhook

**Files:**
- Modify: `zela/api/webhook.py`
- Modify: `tests/test_api_webhook.py`

**Interfaces:**
- Consumes: nada novo.
- Produces: `montar_roteador(processar_mensagem, waha_client, id_idoso=..., telefones_permitidos=None, processar_risco=None)` — novo parâmetro **opcional**, retrocompatível com todos os testes/chamadas existentes que não o passam.

`processar_risco`, quando fornecido, é chamado com `(telefone, texto, agora)` **depois** de a resposta do LLM já ter sido enviada ao idoso — para não atrasar a resposta ao usuário. Assim como `processar_mensagem`, é decisão da própria função injetada (implementada na Task 10, dentro de `main.py`) decidir se deve agir (ex.: ignorar mensagens de familiares) — `webhook.py` continua agnóstico sobre quem é o idoso.

- [ ] **Step 1: Escrever o teste que falha**

Adicione a `tests/test_api_webhook.py`:

```python
def test_webhook_chama_processar_risco_quando_fornecido():
    waha_falso = _WahaFalso()
    chamadas_risco = []

    def processar_falso(id_idoso, texto, agora):
        return "ok"

    def processar_risco_falso(telefone, texto, agora):
        chamadas_risco.append((telefone, texto))

    app = FastAPI()
    app.include_router(
        montar_roteador(processar_falso, waha_falso, processar_risco=processar_risco_falso)
    )
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={
            "event": "message",
            "payload": {"from": "5511987654321@c.us", "body": "caí no banheiro", "fromMe": False},
        },
    )

    assert resposta.status_code == 200
    assert chamadas_risco == [("+5511987654321", "caí no banheiro")]


def test_webhook_nao_falha_quando_processar_risco_nao_e_fornecido():
    waha_falso = _WahaFalso()

    def processar_falso(id_idoso, texto, agora):
        return "ok"

    app = FastAPI()
    app.include_router(montar_roteador(processar_falso, waha_falso))
    cliente = TestClient(app)

    resposta = cliente.post(
        "/webhook/whatsapp",
        json={"event": "message", "payload": {"from": "5511987654321@c.us", "body": "oi", "fromMe": False}},
    )

    assert resposta.status_code == 200
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_api_webhook.py -k processar_risco -v`
Expected: FAIL — `montar_roteador() got an unexpected keyword argument 'processar_risco'`

- [ ] **Step 3: Atualizar `webhook.py`**

```python
def montar_roteador(
    processar_mensagem,
    waha_client,
    id_idoso: str = _ID_IDOSO_PADRAO,
    telefones_permitidos: list[str] | None = None,
    processar_risco=None,
) -> APIRouter:
    roteador = APIRouter()

    @roteador.post("/webhook/whatsapp")
    async def receber_mensagem(request: Request):
        payload = await request.json()
        extraido = _extrair_telefone_e_texto(payload)
        if extraido is None:
            return {"status": "ignorado"}
        telefone, texto = extraido
        if telefones_permitidos is not None and telefone not in telefones_permitidos:
            return {"status": "ignorado"}

        agora = datetime.now()
        resposta_texto = await run_in_threadpool(processar_mensagem, id_idoso, texto, agora)
        await run_in_threadpool(waha_client.enviar_texto, telefone, resposta_texto)

        if processar_risco is not None:
            await run_in_threadpool(processar_risco, telefone, texto, agora)

        return {"status": "processado"}

    return roteador
```

(Note que `agora = datetime.now()` passa a ser calculado uma única vez e reutilizado nas duas chamadas, em vez de duas chamadas separadas a `datetime.now()` como antes — pequena correção de precisão, sem impacto nos testes existentes.)

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_webhook.py -v`
Expected: PASS — todos os testes, novos e pré-existentes.

- [ ] **Step 5: Commit**

```bash
git add zela/api/webhook.py tests/test_api_webhook.py
git commit -m "feat: webhook aceita callback opcional de processamento de risco por mensagem"
```

---

### Task 10: Ferramenta RAG do Agente de Comunicação

**Files:**
- Modify: `zela/agents/orchestrator.py`
- Create: `tests/test_agents_orchestrator_tools_comunicacao.py`

**Interfaces:**
- Consumes: `ClienteEmbeddingGemini` (Task 3), `RepositorioVetorial` (Task 4).
- Produces: `consultar_conhecimento(idoso_id: str, pergunta: str) -> list[str]` (tool ADK, somente leitura); `montar_agente_comunicacao` passa a incluir essa tool.

Segue o mesmo padrão de `_obter_conexao()` já usado no arquivo: fábricas em nível de módulo, chamadas a cada invocação (não cacheadas), fáceis de substituir via `monkeypatch` nos testes.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_agents_orchestrator_tools_comunicacao.py
from zela.agents.orchestrator import consultar_conhecimento, montar_agente_comunicacao


class _ClienteEmbeddingFalso:
    def obter_embedding(self, texto: str) -> list[float]:
        return [1.0, 0.0]


class _ClienteEmbeddingComFalha:
    def obter_embedding(self, texto: str) -> list[float]:
        raise RuntimeError("Gemini fora do ar")


class _RepositorioVetorialFalso:
    def __init__(self, resultado):
        self._resultado = resultado
        self.chamadas = []

    def buscar_similares(self, idoso_id, embedding_consulta, k=3):
        self.chamadas.append((idoso_id, embedding_consulta, k))
        return self._resultado


def test_agente_comunicacao_tem_uma_ferramenta():
    agente = montar_agente_comunicacao()

    assert len(agente.tools) == 1


def test_consultar_conhecimento_retorna_trechos_relevantes(monkeypatch):
    repositorio_falso = _RepositorioVetorialFalso(["Losartana: usado para pressão alta."])
    monkeypatch.setattr(
        "zela.agents.orchestrator._obter_cliente_embedding", lambda: _ClienteEmbeddingFalso()
    )
    monkeypatch.setattr(
        "zela.agents.orchestrator._obter_repositorio_vetorial", lambda: repositorio_falso
    )

    resultado = consultar_conhecimento("idosa-1", "para que serve a losartana?")

    assert resultado == ["Losartana: usado para pressão alta."]
    assert repositorio_falso.chamadas == [("idosa-1", [1.0, 0.0], 3)]


def test_consultar_conhecimento_retorna_lista_vazia_em_falha(monkeypatch):
    monkeypatch.setattr(
        "zela.agents.orchestrator._obter_cliente_embedding", lambda: _ClienteEmbeddingComFalha()
    )

    resultado = consultar_conhecimento("idosa-1", "para que serve a losartana?")

    assert resultado == []
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_agents_orchestrator_tools_comunicacao.py -v`
Expected: FAIL com `ImportError: cannot import name 'consultar_conhecimento'`

- [ ] **Step 3: Implementar em `orchestrator.py`**

Adicione os imports no topo do arquivo:

```python
from zela.embeddings.client import ClienteEmbeddingGemini
from zela.embeddings.vetorial import RepositorioVetorial
```

Adicione, próximo a `_obter_conexao`:

```python
def _obter_cliente_embedding() -> ClienteEmbeddingGemini:
    return ClienteEmbeddingGemini()


def _obter_repositorio_vetorial() -> RepositorioVetorial:
    return RepositorioVetorial()


def consultar_conhecimento(idoso_id: str, pergunta: str) -> list[str]:
    """Busca trechos relevantes (bulas de medicamentos, mensagens passadas do idoso) para responder à pergunta."""
    try:
        embedding_pergunta = _obter_cliente_embedding().obter_embedding(pergunta)
    except Exception:
        return []
    return _obter_repositorio_vetorial().buscar_similares(idoso_id, embedding_pergunta, k=3)
```

Substitua `montar_agente_comunicacao` por:

```python
def montar_agente_comunicacao(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_comunicacao",
        model=model,
        description="Conversa com o idoso e a família via WhatsApp e Streamlit.",
        instruction=(
            "Formate lembretes de forma simples e acolhedora para o idoso, e "
            "interprete as respostas recebidas. Quando o idoso ou a família "
            "perguntarem algo que possa estar em uma bula de medicamento ou em "
            "uma mensagem anterior do idoso (ex.: 'para que serve esse "
            "remédio?', 'o que a Vó disse ontem?'), use a ferramenta "
            "consultar_conhecimento para buscar trechos relevantes antes de "
            "responder. Se a ferramenta não retornar nada relevante, diga que "
            "não encontrou essa informação em vez de inventar uma resposta.\n\n"
            "Toda mensagem recebida começa com uma linha de contexto do "
            "sistema no formato "
            "'[contexto do sistema: idoso_id=<id>; agora=<timestamp ISO 8601>]', "
            "seguida do texto real da pergunta. Extraia idoso_id dessa linha e "
            "use-o como o argumento idoso_id ao chamar consultar_conhecimento; "
            "use o texto da pergunta em si (sem a linha de contexto) como o "
            "argumento pergunta."
        ),
        tools=[consultar_conhecimento],
    )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_agents_orchestrator_tools_comunicacao.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Rodar a suíte completa (checagem de regressão)**

Run: `pytest -q`
Expected: todos os testes continuam passando — em particular, a construção de `root_agent` no import de `zela/agents/orchestrator.py` (que roda em todo teste que importa esse módulo) não deve falhar, já que `_obter_cliente_embedding`/`_obter_repositorio_vetorial` só são chamadas dentro de `consultar_conhecimento`, nunca no import.

- [ ] **Step 6: Commit**

```bash
git add zela/agents/orchestrator.py tests/test_agents_orchestrator_tools_comunicacao.py
git commit -m "feat: agente de comunicacao ganha ferramenta de consulta RAG"
```

---

### Task 11: Wiring completo em `main.py` + README

**Files:**
- Modify: `zela/api/main.py`
- Modify: `tests/test_api_main.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: tudo das Tasks 1-10.
- Produces: aplicação FastAPI completa — mensagens do idoso disparam classificação por embedding + escalonamento; bulas cadastradas são reindexadas no boot.

- [ ] **Step 1: Escrever/atualizar os testes que falham**

Modifique `tests/test_api_main.py`, atualizando `test_app_sobe_e_desce_com_lifespan` para também isolar a reindexação (que, sem isso, chamaria `cliente_embedding.obter_embedding` de verdade se o `zela.db` local tivesse medicamentos com bula):

```python
def test_app_sobe_e_desce_com_lifespan(monkeypatch):
    class _AgendadorFalso:
        def shutdown(self):
            pass

    monkeypatch.setattr("zela.api.main.iniciar_scheduler", lambda *a, **k: _AgendadorFalso())
    monkeypatch.setattr("zela.api.main.reindexar_documentos", lambda *a, **k: 0)

    from zela.api.main import app

    with TestClient(app) as cliente:
        resposta = cliente.get("/docs")
        assert resposta.status_code == 200
```

Adicione também dois testes novos, exercitando `_processar_risco` diretamente:

```python
from datetime import date, datetime

import zela.api.main as main_module
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.storage.perfil import salvar_perfil


class _WahaFalsoMain:
    def __init__(self):
        self.enviados = []

    def enviar_texto(self, telefone, texto):
        self.enviados.append((telefone, texto))


class _ClienteEmbeddingFalsoMain:
    def obter_embedding(self, texto):
        return [1.0, 0.0]


class _RepositorioVetorialFalsoMain:
    def __init__(self):
        self.indexados = []

    def indexar_documento(self, idoso_id, doc_id, texto, embedding, tipo):
        self.indexados.append((idoso_id, doc_id, texto, embedding, tipo))


def _preparar_main_com_perfil(monkeypatch, tmp_path):
    banco = str(tmp_path / "teste.db")
    monkeypatch.setattr(main_module, "CAMINHO_DB", banco)
    conn = main_module.conectar(banco)
    salvar_perfil(
        conn,
        PerfilIdoso(
            nome="Maria", telefone="+5511911111111", data_nascimento=date(1945, 3, 12),
            contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
        ),
        idoso_id=main_module.ID_IDOSO,
    )
    monkeypatch.setattr(main_module, "cliente_embedding", _ClienteEmbeddingFalsoMain())
    monkeypatch.setattr(main_module, "_exemplos_com_embedding_cache", None)


def test_processar_risco_ignora_mensagem_de_familiar(monkeypatch, tmp_path):
    _preparar_main_com_perfil(monkeypatch, tmp_path)
    waha_falso = _WahaFalsoMain()
    monkeypatch.setattr(main_module, "waha_client", waha_falso)
    monkeypatch.setattr(main_module, "repositorio_vetorial", _RepositorioVetorialFalsoMain())

    # Número do familiar (João), não o do idoso: _processar_risco deve
    # retornar antes de calcular qualquer embedding.
    main_module._processar_risco("+5511987654321", "como ela está?", datetime(2026, 9, 17, 10, 0))

    assert waha_falso.enviados == []


def test_processar_risco_processa_mensagem_do_idoso(monkeypatch, tmp_path):
    _preparar_main_com_perfil(monkeypatch, tmp_path)
    repositorio_falso = _RepositorioVetorialFalsoMain()
    monkeypatch.setattr(main_module, "waha_client", _WahaFalsoMain())
    monkeypatch.setattr(main_module, "repositorio_vetorial", repositorio_falso)

    # Número do próprio idoso: o fluxo completo deve rodar, incluindo a
    # indexação da mensagem no vector store (fake).
    main_module._processar_risco("+5511911111111", "estou bem", datetime(2026, 9, 17, 10, 0))

    assert len(repositorio_falso.indexados) == 1
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `pytest tests/test_api_main.py -v`
Expected: FAIL — `AttributeError: module 'zela.api.main' has no attribute 'cliente_embedding'` (entre outros).

- [ ] **Step 3: Atualizar `main.py`**

```python
# zela/api/main.py
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI

from zela.api.ingestao import montar_roteador_ingestao
from zela.api.monitoramento_mensagem import processar_risco_mensagem
from zela.api.reindexacao import reindexar_documentos
from zela.api.runner import obter_runner_zela, processar_mensagem
from zela.api.scheduler import iniciar_scheduler
from zela.api.webhook import montar_roteador
from zela.embeddings.client import ClienteEmbeddingGemini
from zela.embeddings.exemplos_referencia import EXEMPLOS_REFERENCIA
from zela.embeddings.vetorial import RepositorioVetorial
from zela.integrations.waha_client import WahaClient
from zela.storage.db import conectar
from zela.storage.monitoramento import salvar_leitura as salvar_leitura_sensor
from zela.storage.perfil import obter_perfil

CAMINHO_DB = "zela.db"
ID_IDOSO = "idosa-1"
WAHA_BASE_URL = "http://localhost:3000"

waha_client = WahaClient(base_url=WAHA_BASE_URL)
cliente_embedding = ClienteEmbeddingGemini()
repositorio_vetorial = RepositorioVetorial()
_runner = obter_runner_zela()
_exemplos_com_embedding_cache = None


def _obter_telefones_permitidos() -> list[str] | None:
    conexao = conectar(CAMINHO_DB)
    perfil = obter_perfil(conexao, ID_IDOSO)
    if perfil is None:
        return None
    return [perfil.telefone] + [c.telefone for c in perfil.contatos_familiares]


_TELEFONES_PERMITIDOS = _obter_telefones_permitidos()


def _processar(id_idoso: str, texto: str, agora) -> str:
    return processar_mensagem(_runner, id_idoso, texto, agora)


def _obter_exemplos_com_embedding():
    global _exemplos_com_embedding_cache
    if _exemplos_com_embedding_cache is None:
        _exemplos_com_embedding_cache = [
            (exemplo, cliente_embedding.obter_embedding(exemplo.texto)) for exemplo in EXEMPLOS_REFERENCIA
        ]
    return _exemplos_com_embedding_cache


def _processar_risco(telefone: str, texto: str, agora: datetime) -> None:
    conexao = conectar(CAMINHO_DB)
    perfil = obter_perfil(conexao, ID_IDOSO)
    if perfil is None or telefone != perfil.telefone:
        return
    exemplos = _obter_exemplos_com_embedding()
    processar_risco_mensagem(
        conexao, ID_IDOSO, perfil, texto, agora,
        cliente_embedding, exemplos, repositorio_vetorial, waha_client,
    )


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    reindexar_documentos(conectar(CAMINHO_DB), ID_IDOSO, repositorio_vetorial, cliente_embedding)
    agendador = iniciar_scheduler(CAMINHO_DB, ID_IDOSO, waha_client)
    try:
        yield
    finally:
        agendador.shutdown()


def _salvar_leitura(leitura, idoso_id: str) -> None:
    conexao = conectar(CAMINHO_DB)
    salvar_leitura_sensor(conexao, leitura, idoso_id)


app = FastAPI(lifespan=ciclo_de_vida)
app.include_router(
    montar_roteador(
        _processar, waha_client, id_idoso=ID_IDOSO,
        telefones_permitidos=_TELEFONES_PERMITIDOS, processar_risco=_processar_risco,
    )
)
app.include_router(montar_roteador_ingestao(_salvar_leitura, id_idoso=ID_IDOSO))
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `pytest tests/test_api_main.py -v`
Expected: PASS — todos os testes, novos e pré-existentes.

- [ ] **Step 5: Atualizar o README**

Adicione ao `README.md` uma seção "Embeddings e RAG (Plano 4)" com o seguinte conteúdo:

```markdown
## Embeddings e RAG (Plano 4)

A classificação de urgência por similaridade e o RAG usam a mesma chave de
API do Gemini já configurada para os agentes ADK (`GOOGLE_API_KEY` ou
`GEMINI_API_KEY` — veja a seção de setup acima). Nenhuma credencial nova é
necessária.

O vector store (Chroma) persiste localmente em `./chroma_db/` (ignorado
pelo git, recriado automaticamente na primeira execução).

**Nota de migração:** este plano adiciona a coluna `bula` à tabela
`medicamento`. Se você já tinha um `zela.db` de uma execução anterior à
deste plano, apague o arquivo (`rm zela.db`) antes de subir a API
novamente — o schema não faz migração automática de colunas em tabelas já
existentes, só cria tabelas novas.

Para que um medicamento tenha sua bula pesquisável pelo RAG, cadastre-o
com o campo `bula` preenchido (ex.: via um script de seed usando
`Medicamento(..., bula="...")` e `salvar_medicamento`). A reindexação no
vector store acontece automaticamente a cada subida da API.
```

- [ ] **Step 6: Rodar a suíte completa**

Run: `pytest -q`
Expected: todos os testes passam (pré-existentes + novos deste plano).

- [ ] **Step 7: Commit**

```bash
git add zela/api/main.py tests/test_api_main.py README.md
git commit -m "feat: integra classificacao por embedding e RAG na API principal"
```
