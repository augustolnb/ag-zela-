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
4. **Embeddings** (classificação de urgência + RAG) ✓
5. **Painel Streamlit para a família** ✓
6. **Fluxo visual em n8n** (substitui Langflow, citado no enunciado
   original do curso — o curso migrou de ferramenta) ✓
7. **Empacotamento final, documentação e vídeo pitch** ✓

O design completo está em
`docs/superpowers/specs/2026-09-10-cuida-mais-agente-idoso-design.md`. O
relatório final do trabalho está em `RELATORIO.md` (também disponível em
`RELATORIO.pdf`, gerado via `scripts/gerar_relatorio_pdf.py`), e o roteiro
do vídeo pitch em `docs/pitch/roteiro.md`.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Cadastrando a idosa e os medicamentos

Até o Plano 5, nenhum caminho do código em produção cadastrava dados
sozinho. Agora o painel Streamlit (veja a seção "Painel Streamlit" abaixo)
permite cadastrar/editar medicamentos e compromissos pela interface. Para
o cadastro inicial da idosa em si (perfil, contatos familiares), ou para
popular dados via script, use os repositórios de `zela/storage/`
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

Para o detalhamento completo da suíte (o que cada camada testa, por que
foi testada dessa forma, cobertura por arquivo, resultado da última
execução e o que fica de fora dos testes automatizados), ver
`docs/testes/estrategia-e-resultados.md`.

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

Os agentes usam o modelo `gemini-3.8-flash` (constante `MODELO_PADRAO` em
`zela/agents/orchestrator.py` — o projeto começou usando `gemini-2.0-flash`,
mas esse modelo foi descontinuado pela API do Gemini durante o
desenvolvimento; se a mesma mensagem de erro `404 NOT_FOUND ... no longer
available` aparecer de novo no futuro, atualize essa constante para o
modelo recomendado pelo próprio erro), então é necessária uma
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

### Alternativa: usando o DeepSeek em vez do Gemini

Se a API do Gemini estiver instável/indisponível (ex.: `503 UNAVAILABLE —
high demand`) e você precisar continuar testando os agentes, é possível
trocar o LLM de orquestração/conversação para o DeepSeek, via
[LiteLLM](https://docs.litellm.ai/):

```bash
pip install -e ".[deepseek]"   # instala o litellm (extra google-adk[extensions])
export DEEPSEEK_API_KEY="sua-chave-aqui"
export ZELA_LLM_PROVEDOR=deepseek
adk run zela/agents
```

Sem `ZELA_LLM_PROVEDOR` (ou com `ZELA_LLM_PROVEDOR=gemini`), o
comportamento padrão com Gemini continua inalterado. A escolha é feita
em `_montar_modelo_padrao()` (`zela/agents/orchestrator.py`), que monta
`MODELO_PADRAO` como a string `"gemini-3.8-flash"` ou como um
`LiteLlm(model="deepseek/deepseek-chat")`, conforme essa variável.

**Importante:** essa troca afeta só o LLM dos agentes ADK. O RAG
(ferramenta `consultar_conhecimento`, usada pelo agente de comunicação)
continua usando embeddings do Gemini (`ClienteEmbeddingGemini`, modelo
`text-embedding-004`) independentemente dessa variável — ou seja, mesmo
testando com `ZELA_LLM_PROVEDOR=deepseek`, ainda é necessária uma
`GOOGLE_API_KEY`/`GEMINI_API_KEY` válida para essa ferramenta específica
funcionar. Além disso, como as instruções dos agentes foram escritas e
validadas com o Gemini, o comportamento de delegação entre sub-agentes
(quando chamar qual ferramenta, como interpretar o prefixo de contexto)
pode variar um pouco com o DeepSeek — isso é diferença de modelo, não um
bug do projeto.

**Atenção ao testar com `adk run`:** em produção (webhook do WhatsApp,
painel Streamlit), toda mensagem passa por `zela/api/runner.py`, que
monta automaticamente uma linha de contexto no formato
`[contexto do sistema: idoso_id=<id>; agora=<timestamp ISO 8601>]` antes
de enviar a mensagem ao agente — é assim que os agentes sabem de qual
idoso se trata e extraem os argumentos das ferramentas. O `adk run` fala
direto com o agente, sem passar por `runner.py`, então **essa linha não
é adicionada automaticamente**. Para testar o roteamento/chamadas de
ferramenta de verdade (e não só se o agente responde algo), digite essa
linha de contexto você mesmo antes da pergunta, por exemplo:
`[contexto do sistema: idoso_id=idosa-1; agora=2026-01-01T08:00:00] já tomei o remédio`
(use `idosa-1`, o `idoso_id` fixo do projeto — ver seção "Cadastrando a
idosa e os medicamentos"). Sem essa linha, o teste só valida que o
agente não trava com uma mensagem fora do padrão, não a orquestração em
si.

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
- `zela/embeddings/` — cliente de embeddings do Gemini, classificador de
  urgência por similaridade (puro), e vector store Chroma para RAG.
- `zela/integrations/` — cliente WAHA para envio/recebimento de mensagens
  via WhatsApp.
- `zela/api/` — webhook do WhatsApp, ponte com o ADK Runner, scheduler de
  lembretes e montagem do app FastAPI.
- `zela/streamlit_app/` — painel Streamlit da família (status, medicação,
  alertas, gráfico de presença, cadastro de medicamentos e compromissos).

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
4.1. Se a instância do WAHA exigir autenticação na API REST (variável
   `WAHA_API_KEY` definida no container — comum em imagens mais recentes),
   defina a mesma chave para o backend, senão todo envio de resposta
   falha com `401 Unauthorized`:
   ```bash
   export ZELA_WAHA_API_KEY=a-mesma-chave-do-container-waha
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

### Identificador de privacidade do WhatsApp (LID)

Esta seção documenta um problema real descoberto durante a validação manual
de ponta a ponta (não um defeito teórico): nenhum dos 199 testes
automatizados do projeto o detectou, porque todos usam payloads sintéticos
no formato "esperado". Só apareceu ao mandar uma mensagem de verdade pelo
WhatsApp.

**O problema.** Ao testar o fluxo real (WhatsApp → WAHA → webhook → ADK →
resposta), a mensagem enviada pelo número cadastrado nunca gerava resposta.
Capturando o payload bruto do webhook (um servidor HTTP mínimo colocado
temporariamente no lugar do backend), o campo do remetente veio como:

```json
"from": "109281332445239@lid"
```

em vez do formato esperado `"<telefone>@c.us"`. Isso é o **LID (Linked
ID)**, um identificador de privacidade que o WhatsApp passou a usar em
parte das conversas: em vez do número de telefone, a conta mostra ao
"destinatário" (aqui, o número que representa o Zela+) um código numérico
opaco e estável, sem revelar o telefone real. Não é um bug do WAHA — é o
próprio cliente WhatsApp que deixa de enviar o número.

Isso quebrava dois pontos do código, ambos escritos assumindo que todo
remetente seria sempre `"<telefone>@c.us"`:

1. `_extrair_telefone_e_texto` (`zela/api/webhook.py`) convertia qualquer
   remetente para um pseudo-telefone `"+" + dígitos`. Para um LID, isso
   gera uma string que nunca bate com o telefone cadastrado no perfil →
   a mensagem era silenciosamente descartada (`{"status": "ignorado"}`).
2. Mesmo ignorando o filtro, a resposta teria sido enviada para o chat
   errado: `WahaClient._para_chat_id` sempre completava o destino com
   `@c.us`, o que aponta para um chat por telefone — inexistente nesse
   caso — em vez do chat `@lid` real de onde a mensagem veio.

**Solução implementada.** Em vez de tentar resolver o LID para um telefone
(o WhatsApp não expõe essa informação para contas com esse recurso de
privacidade ativado — não existe chamada de API que recupere isso), o
projeto passou a tratar o LID como um identificador alternativo,
cadastrado manualmente uma única vez, da mesma forma que já cadastramos o
telefone:

- Novo campo opcional `lid_whatsapp: str | None` em `PerfilIdoso`
  (`zela/models/perfil.py`).
- Migração de schema idempotente para a coluna `lid_whatsapp` em
  `perfil_idoso` (`zela/storage/db.py`), seguindo o mesmo padrão já usado
  para a coluna `bula` de medicamentos — roda a cada `conectar()` e não
  falha se a coluna já existir.
- `_extrair_telefone_e_texto` agora ramifica pelo sufixo do remetente:
  `...@c.us` continua convertido para E.164 (`+<dígitos>`, comportamento
  inalterado); `...@lid` é devolvido como o JID completo, sem conversão.
- `montar_roteador` ganhou o parâmetro `lids_permitidos`, verificado
  apenas quando o remetente é um LID — a lista de telefones permitidos
  continua sendo a única regra para remetentes normais.
- `WahaClient._para_chat_id` passou a reconhecer um JID já completo
  (contém `"@"`) e repassá-lo sem reformatar, em vez de sempre anexar
  `@c.us`. Isso corrige o roteamento da resposta para remetentes LID sem
  alterar nenhuma chamada existente que já passa um telefone puro (os
  lembretes/alertas proativos do `scheduler.py`, por exemplo).
- `_processar_risco` (`zela/api/main.py`) passou a comparar o identificador
  recebido tanto contra `perfil.telefone` quanto contra
  `perfil.lid_whatsapp`.
- O `lid_whatsapp` real capturado durante a validação foi gravado no
  perfil da `idosa-1` no banco local, permitindo testar o fluxo completo
  de verdade pelo WhatsApp.

**Por que essas decisões.** O cadastro manual do LID (em vez de resolução
automática) é proporcional ao escopo de MVP de tenant único: o WhatsApp
não expõe o telefone real por trás de um LID como recurso deliberado de
privacidade, então qualquer automação aqui estaria tentando contornar essa
proteção. Preservar o formato `"+telefone"` para remetentes `@c.us` evitou
tocar na lógica de comparação já testada em `_processar_risco` e no
contrato de lista de permitidos cobertos pelos testes existentes — a
correção ficou isolada por tipo de identificador, reduzindo o risco de
regressão. E a verificação `"@" in valor` em `_para_chat_id` é segura
porque todo JID válido do WAHA contém `"@"`, enquanto um telefone puro
(usado pelo agendador de lembretes) nunca contém — não há ambiguidade
entre os dois formatos de entrada.

**Como funciona agora, passo a passo:**
1. WAHA entrega o webhook com `payload.from` no formato `@c.us` ou `@lid`.
2. `_extrair_telefone_e_texto` identifica o formato e devolve o
   identificador correspondente (telefone E.164 ou JID LID completo).
3. `montar_roteador` escolhe a lista de permissão certa (`telefones_permitidos`
   ou `lids_permitidos`) de acordo com o sufixo do identificador.
4. Se permitido, a mensagem é processada normalmente pelo agente e a
   resposta é enviada de volta usando o mesmo identificador — `_para_chat_id`
   decide se precisa completar com `@c.us` (telefone puro) ou repassar o
   JID como está (já completo).
5. `_processar_risco` aplica a mesma lógica de "é a própria idosa?" nos dois
   formatos, mantendo o escalonamento de risco funcionando
   independentemente de como o WhatsApp identifica o remetente.

**Testes adicionados** cobrindo esse fluxo: `tests/test_storage_db.py`
(migração da coluna), `tests/test_storage_perfil.py` e
`tests/test_models_perfil.py` (persistência e validação do campo),
`tests/test_integrations_waha_client.py` (repasse do JID sem reformatar),
`tests/test_api_webhook.py` (filtro por LID permitido/não permitido, e
resposta enviada para o JID correto) e `tests/test_api_main.py`
(`_processar_risco` e `_obter_lids_permitidos` com um perfil que tem LID
cadastrado).

### Segundo problema encontrado na mesma validação: WAHA exige API key

Depois de corrigir o LID, o teste de ponta a ponta ainda não respondia.
Reproduzindo o payload real diretamente contra o backend (com
`TestClient(app, raise_server_exceptions=True)`, que propaga a exceção em
vez de só devolver um 500 genérico), o traceback mostrou exatamente onde
parava: a mensagem chegava, passava pelo filtro de permissão (LID já
corrigido), o agente ADK processava e gerava a resposta — e o envio de
volta pelo WAHA (`POST /api/sendText`) falhava com `401 Unauthorized`.

**Causa:** `WahaClient` (`zela/integrations/waha_client.py`) nunca enviava
nenhum cabeçalho de autenticação, e esta instância do WAHA está configurada
com `WAHA_API_KEY` (variável de ambiente do container), que passou a
exigir o cabeçalho `X-Api-Key` em toda chamada da API REST — inclusive
`/api/sendText`. Isso não tem relação com o LID; é um problema distinto,
só visível depois que o primeiro foi corrigido e a mensagem passou a
chegar até esse ponto do fluxo.

**Solução:** `WahaClient.__init__` ganhou o parâmetro opcional `api_key`,
incluído como `X-Api-Key` em todas as chamadas (`enviar_texto`,
`enviar_audio`) quando configurado. O backend lê o valor da nova variável
de ambiente `ZELA_WAHA_API_KEY` (`zela/api/main.py`) — veja o passo 4.1
em "Configurando o WAHA (WhatsApp)" acima. Quando não configurada, o
cliente não envia o cabeçalho, preservando o comportamento de instâncias
do WAHA sem autenticação (como as usadas nos testes automatizados).

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

## Embeddings e RAG (Plano 4)

A classificação de urgência por similaridade e o RAG usam a mesma chave de
API do Gemini já configurada para os agentes ADK (`GOOGLE_API_KEY` ou
`GEMINI_API_KEY` — veja a seção de setup acima). Nenhuma credencial nova é
necessária.

O vector store (Chroma) persiste localmente em `./chroma_db/` (ignorado
pelo git, recriado automaticamente na primeira execução).

**Nota de migração:** este plano adiciona a coluna `bula` à tabela
`medicamento`. Se você já tinha um `zela.db` de uma execução anterior a
este plano, não é preciso apagar o arquivo — `zela/storage/db.py::conectar`
verifica a presença da coluna `bula` a cada conexão e adiciona
(`ALTER TABLE`) automaticamente caso ela não exista, além de criar tabelas
novas via `CREATE TABLE IF NOT EXISTS`.

Para que um medicamento tenha sua bula pesquisável pelo RAG, cadastre-o
com o campo `bula` preenchido — pelo painel Streamlit (Plano 5, veja
abaixo) ou via script de seed usando `Medicamento(..., bula="...")` e
`salvar_medicamento`. A reindexação no vector store acontece
automaticamente a cada subida da API.

Os embeddings usam o modelo `gemini-embedding-2` (constante `MODELO_PADRAO`
em `zela/embeddings/client.py` — o projeto começou usando
`text-embedding-004`, mas esse modelo foi descontinuado pela API do
Gemini durante o desenvolvimento, com erro `404 NOT_FOUND ... is not
found for API version v1beta, or is not supported for embedContent`; se
isso acontecer de novo no futuro, rode
`.venv/bin/python -c "from google import genai; [print(m.name) for m in genai.Client().models.list() if 'embedContent' in (m.supported_actions or [])]"`
para listar os modelos atuais com suporte a `embedContent` e atualize essa
constante). Se você trocar o modelo de embeddings depois de já ter
documentos indexados, apague `./chroma_db/` antes de subir a API de novo
— modelos diferentes podem gerar vetores de dimensão diferente, e o
Chroma rejeita misturar dimensões na mesma coleção.

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

**Nota sobre o banco de dados:** o painel usa a variável de ambiente
`ZELA_DB_PATH` para achar o `zela.db` (mesmo padrão usado pelo backend
FastAPI, `zela/api/main.py`) — se você definir `ZELA_DB_PATH` para um dos
dois processos, defina a mesma variável para o outro, e rode ambos a
partir do mesmo diretório de trabalho. Caso contrário, os dois podem
apontar para arquivos diferentes sem nenhum aviso.

**Nota:** a senha é única e compartilhada (não é um sistema de contas por
usuário) — suficiente para o MVP, mas não deve ser considerado um controle
de acesso robusto se o painel for exposto além da rede local/doméstica.

## Workflow n8n (Plano 6)

Este workflow representa, de forma simplificada, a fatia "mensagem
recebida → classificação de urgência → roteamento" do sistema — **não**
substitui a integração real WhatsApp↔backend (WAHA→FastAPI, Plano 2), que
continua funcionando de forma independente. É um webhook próprio, só para
demonstrar a lógica de classificação/roteamento visualmente, conforme os
itens 3.4/3.8 do card.

1. Rode o backend normalmente (`uvicorn zela.api.main:app --reload`).
2. No seu n8n, importe `docs/n8n/zela-classificacao-mensagem.json`
   ("Import from File" ou colar o JSON em "Import from Clipboard").
3. Confira a URL configurada no nó **HTTP Request**
   (`http://localhost:8000/api/classificar-mensagem`) — se o n8n rodar em
   um container Docker separado do backend, troque `localhost` por
   `host.docker.internal` (ou o IP da máquina host); se rodar na mesma
   máquina fora de container, o padrão já funciona.
4. Ative o workflow (ou use "Execute Workflow"/"Listen for Test Event" no
   próprio n8n) e dispare o webhook com uma mensagem de teste:
   ```bash
   curl -X POST http://localhost:5678/webhook/zela-classificar-mensagem \
     -H "Content-Type: application/json" \
     -d '{"telefone": "+5511999999999", "texto": "caí no banheiro e não consigo levantar"}'
   ```
   (ajuste a porta `5678` se seu n8n usar outra, e use
   `/webhook-test/...` em vez de `/webhook/...` se estiver no modo de
   teste do editor, conforme a própria interface do n8n indicar).
5. Confirme que a resposta reflete o roteamento esperado (`"acao":
   "alertar_familia"` para uma mensagem de risco, por exemplo) e tire uma
   captura de tela do workflow no editor do n8n (com uma execução recente
   visível) — salve como `docs/n8n/screenshot.png` para o item 3.4 do
   card.

**Nota:** o endpoint `/api/classificar-mensagem` só classifica — nunca
decide nem dispara escalonamento de verdade (isso continua sendo
responsabilidade exclusiva do scheduler determinístico, Plano 3/4). Testar
este workflow à vontade não aciona nenhum alerta real à família.

**Nota sobre o painel do n8n (bug aparente, não real):** nos nós "Respond
to Webhook" na versão `typeVersion` 1.1 (a usada neste workflow), o
painel do editor e o histórico de execuções mostram os dados de
**entrada** do nó (o `{status, motivo}` cru vindo do nó HTTP Request
anterior), não a resposta HTTP que ele de fato monta e envia. Isso pode
parecer que o campo `acao`/`mensagem_ilustrativa` não foi gerado — mas a
resposta HTTP real (a que chega pelo `curl` ou chegaria para quem chamou
o webhook) já contém o JSON completo. Para conferir a resposta de
verdade, não confie no painel: dispare o webhook via `curl -i` (como no
passo 4 acima) e leia o corpo da resposta ali.

## Limitações conhecidas do Plano 3

1. **Sessão de conversa compartilhada entre idosa e família:** desde que o
   webhook passou a aceitar mensagens de múltiplos números (idosa +
   contatos familiares), a ponte com o ADK Runner (`zela/api/runner.py`)
   ainda usa uma única sessão de conversa fixa por idoso (não por
   remetente) — ou seja, mensagens da idosa e da família compartilham o
   mesmo histórico de contexto do LLM. Isso significa que, em teoria, uma
   mensagem de um familiar poderia acionar `confirmar_medicamento` como se
   fosse a própria idosa confirmando. Corrigir isso exige repensar o
   design de sessão do Plano 2 (ex.: uma sessão por número de telefone) —
   fica como item para um plano futuro.
2. **Sem autenticação nos endpoints de ingestão:** `/ingest/esp32` e
   `/ingest/health-connect` não exigem nenhuma autenticação — qualquer
   requisição que alcance a porta pode injetar leituras de sensor
   fabricadas. Para um MVP local isso é aceitável, mas antes de qualquer
   exposição além da rede local, esses endpoints precisam de um mecanismo
   de autenticação (ex.: um token compartilhado).
3. **Resposta da idosa não interrompe o escalonamento:** quando o Agente
   de Emergência envia a mensagem inicial de verificação ("Tudo bem? Pode
   confirmar que está tudo certo?"), uma resposta da idosa por WhatsApp
   ainda não interrompe automaticamente a escada de escalonamento (que
   segue avançando para notificar a família e, depois, simular contato de
   emergência). Implementar isso exige um caminho determinístico (não
   dependente de LLM) para interpretar a resposta da idosa e resetar o
   estado de escalonamento — fica como item para um plano futuro.
   **Atualização (Plano 4):** parcialmente endereçado — mensagens de texto
   da idosa agora são classificadas por similaridade de embedding e
   alimentam essa mesma máquina de escalonamento; uma resposta
   classificada como `NORMAL` reseta o escalonamento para `RESOLVIDO`.
   Ver "Limitações conhecidas do Plano 4" abaixo para as ressalvas.

## Limitações conhecidas do Plano 4

1. **Um risco originado por mensagem não avança sozinho até a família:**
   a classificação por embedding de uma mensagem da idosa entra na mesma
   escada de escalonamento dos sensores (`aplicar_escalonamento`), mas
   nada além do job periódico de sensores (`verificar_e_escalonar_riscos`,
   a cada 15 min) avança essa escada adiante. Na prática, isso produz um
   de dois resultados: (a) se não houver leituras de presença recentes
   (instalação sem ESP32, o cenário mais provável em demonstração), o
   job de sensores trata isso como "sem dados" e nunca chama
   `aplicar_escalonamento` de novo — a escada fica congelada em
   `CONTATO_IDOSO` indefinidamente; (b) se as leituras de presença
   parecerem normais, o próximo tick do job classifica `NORMAL` e reseta
   o escalonamento para `RESOLVIDO` em até 15 minutos. Ou seja: uma
   mensagem como "caí no banheiro e não consigo levantar" hoje gera a
   pergunta de verificação para a idosa, mas não necessariamente chega a
   notificar a família sozinha. Corrigir isso exige persistir o evento
   que originou o escalonamento para que o próprio job de sensores possa
   reconhecê-lo e continuar avançando a escada — fica como item para um
   plano futuro.
2. **Isso também atualiza (parcialmente) a Limitação 3 do Plano 3
   ("resposta da idosa não interrompe o escalonamento"):** uma mensagem
   da idosa classificada como `NORMAL` agora reseta qualquer
   escalonamento em andamento (inclusive um iniciado por sensor) para
   `RESOLVIDO` — de fato, uma forma de interrupção. Mas o classificador
   por similaridade não tem um piso mínimo de similaridade: uma mensagem
   fora do padrão dos exemplos de referência (ex.: "oi", enviada por uma
   idosa desorientada) ainda recebe a classificação do exemplo mais
   próximo, que pode ser `NORMAL` e fechar um escalonamento real por
   engano. Calibrar um piso de similaridade exige testar contra
   embeddings reais do Gemini — fica para um plano futuro.
3. **Histórico de mensagens no RAG não sobrevive à perda do `chroma_db/`:**
   a reindexação automática no boot (`reindexar_documentos`) só cobre
   bulas de medicamentos (lidas do SQLite, fonte de verdade). Mensagens
   passadas da idosa são indexadas apenas em tempo real, direto no
   Chroma — não há cópia em SQLite. Se `./chroma_db/` for apagado ou
   corrompido, o histórico de mensagens pesquisável pelo RAG se perde
   (as bulas são reconstruídas automaticamente no próximo boot; as
   mensagens, não).

## Limitações conhecidas do Plano 6

1. **Sem autenticação no endpoint `/api/classificar-mensagem`:** consistente
   com a postura de MVP já documentada para `/ingest/esp32`,
   `/ingest/health-connect` e `/webhook/whatsapp` (nenhum desses tem
   autenticação também) — não é uma lacuna nova introduzida por este
   plano. Mas, diferente dos endpoints de ingestão, este consome cota da
   API do Gemini a cada chamada e não impõe um tamanho máximo para o
   campo `texto` — antes de expor esse endpoint além da rede local, vale
   adicionar um limite de tamanho e/ou autenticação.
2. **Sem teste automatizado da execução real do workflow n8n:** o arquivo
   `docs/n8n/zela-classificacao-mensagem.json` tem um teste estrutural
   (`tests/test_n8n_workflow.py`, valida tipos de nó, parâmetros e
   conexões), mas nenhum teste executa o workflow de verdade dentro do
   n8n — isso não é possível a partir da suíte `pytest` deste repositório
   (o n8n é uma ferramenta externa). A verificação de que o workflow
   funciona de ponta a ponta é manual, feita pelo usuário ao importar e
   testar o arquivo (veja "Workflow n8n (Plano 6)" acima).
