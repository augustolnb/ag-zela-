# Zela+ — Agente de IA de Apoio ao Idoso que Mora Sozinho

Trabalho final de pós-graduação em Agentes de IA. Zela+ é um agente
multiagente (ADK) que ajuda idosos que moram sozinhos a não esquecer
medicamentos e compromissos, monitora sinais de risco (saúde e
presença/movimento) via smartwatch e ESP32, e mantém a família informada,
podendo escalar alertas até simular contato com serviço de emergência.

## Status do projeto

Este repositório está sendo construído em fases (planos sequenciais):

1. **Fundação** (Plano 1) — modelos Pydantic + lógica de domínio dos 5
   agentes + esqueleto de orquestração ADK. Tudo testável com `pytest`,
   sem hardware nem APIs externas.
2. **Comunicação real** (WhatsApp via WAHA) ✓ — áudio (STT/TTS) ainda não
   implementado.
3. **Ingestão de sensores reais** (ESP32 + Health Connect/Mi Band 9) ✓
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

## Cadastrando a idosa e os medicamentos

Nenhum caminho do código em produção cadastra dados sozinho — é preciso
popular o banco SQLite usando os repositórios de `zela/storage/`
diretamente. O `idoso_id` usado em todo o código (webhook, scheduler,
ferramentas do agente de rotina) é `"idosa-1"` (veja a constante
`ID_IDOSO` em `zela/api/main.py`); use o mesmo valor ao cadastrar:

```python
from datetime import date, time
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.models.rotina import Dosagem, Medicamento
from zela.storage.db import conectar
from zela.storage.perfil import salvar_perfil
from zela.storage.rotina import salvar_medicamento

conn = conectar("zela.db")

perfil = PerfilIdoso(
    nome="Maria da Silva",
    telefone="+5511900000000",  # número real da idosa, formato E.164
    data_nascimento=date(1945, 3, 12),
    contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
)
salvar_perfil(conn, perfil, idoso_id="idosa-1")

medicamento = Medicamento(
    id="med-1",
    nome="Losartana",
    dosagem=Dosagem(quantidade=50, unidade="mg"),
    horarios=[time(8, 0), time(20, 0)],
)
salvar_medicamento(conn, medicamento, idoso_id="idosa-1")
```

Esse trecho pode ser salvo como um script (`python seed.py`) e executado
uma vez, ou rodado interativamente (`python` / REPL). Um painel Streamlit
de administração para fazer isso pela interface está planejado para uma
fase posterior (ver "Status do projeto" acima).

## Rodando os testes

```bash
pytest -v
```

## Verificando o comportamento do agente (adk run)

A suíte automatizada cobre apenas a camada de domínio (lógica pura, sem
LLM nem rede) e o esqueleto de orquestração ADK (nomes, hierarquia de
sub-agentes). Ela deliberadamente **não** faz nenhuma chamada real a LLM
ou à rede. Para verificar manualmente o comportamento dos agentes
(instruções, delegação entre sub-agentes, respostas do modelo), use o
`adk run` da própria ADK:

```bash
export GOOGLE_API_KEY="sua-chave-aqui"   # ou GEMINI_API_KEY
adk run zela/agents
```

Os agentes usam o modelo `gemini-2.0-flash`, então é necessária uma
chave de API do Gemini disponível como variável de ambiente
(`GOOGLE_API_KEY` tem prioridade; `GEMINI_API_KEY` também é aceita —
confira `adk run --help` ou a documentação do `google-adk` instalado
caso a versão em uso espere algo diferente). O `root_agent`
(orquestrador) é exportado em `zela/agents/__init__.py` /
`zela/agents/orchestrator.py`, que é o que o `adk run` procura ao
receber o caminho `zela/agents`.

Este passo é manual e **não é coberto pelos testes automatizados**
(`pytest -v`), que evitam de propósito qualquer chamada real a
LLM/rede.

## Nota sobre fusos horários

Todos os `datetime` deste código são "naive" (sem informação de fuso
horário) e assumidos como horário local — não há nenhuma normalização
de fuso. Uma futura integração (ingestão de sensores, webhooks) que
receba timestamps com fuso horário (`aware`) precisa remover/normalizar
esse fuso antes de construir qualquer objeto de `zela.models`, ou a
aritmética de datas da camada de domínio (`agora - ultima_presenca`,
`agora - estado.iniciado_em`, `datetime.combine(...)`, etc.) vai lançar
`TypeError`.

## Estrutura do código

- `zela/models/` — contratos de dados Pydantic (validação de entrada).
- `zela/domain/` — regras de negócio de cada agente, puras e testáveis
  sem dependências externas.
- `zela/agents/` — definição dos agentes ADK (orquestrador + 4
  especializados).
- `zela/simulacao.py` — simulação de um "dia" completo do sistema, sem
  hardware nem APIs externas, usada para validar a lógica de domínio de
  ponta a ponta. Ainda não tem ponto de entrada de CLI (`__main__`);
  por enquanto é feito para ser importado e chamado a partir dos testes
  ou de um futuro runner, não executado diretamente pela linha de
  comando.
- `zela/storage/` — repositórios SQLite (perfil, medicamentos,
  confirmações) que persistem os dados usados pelos agentes.
- `zela/integrations/` — cliente WAHA para envio/recebimento de mensagens
  via WhatsApp.
- `zela/api/` — webhook do WhatsApp, ponte com o ADK Runner, scheduler de
  lembretes e montagem do app FastAPI.

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
