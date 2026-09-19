# Zela+ — Agente Inteligente de Apoio ao Idoso que Mora Sozinho

Spec de design (fase de brainstorming), previamente ao plano de implementação.

## 1. Contexto e enquadramento no card

Este projeto é o trabalho final de pós-graduação em Agentes de IA, conforme
`card14-instrucoes.txt`. O card exige, entre outros pontos: um problema
específico e delimitado na área da saúde; arquitetura de agente único ou
multiagente (ReAct); validação de dados com Pydantic; um fluxo de trabalho
básico em Langflow; uso de embeddings para uma finalidade específica;
orquestração multiagente com ADK; interface Streamlit; integração de
comunicação (ex.: WhatsApp); e um repositório GitHub documentado, com
relatório e vídeo pitch (≤3min).

**Nota de substituição de ferramenta:** o enunciado formal cita "Langflow"
nos itens 3.4 e 3.8, mas o curso migrou dessa ferramenta para o **n8n**
durante o período letivo. Este projeto usa n8n em todos os pontos em que o
card menciona Langflow, pois ambas são ferramentas de orquestração visual de
workflows com paridade de funcionalidades (webhooks, HTTP requests, export
de workflow em `.json`) — a justificativa deve constar no relatório final
para o avaliador.

**Nota de substituição de ferramenta (canal WhatsApp):** o canal de
comunicação com o idoso usa **WAHA** (WhatsApp HTTP API, open-source,
self-hosted) em vez de Twilio. Decisão tomada por combinar melhor com a
escolha do n8n (nó nativo na comunidade, sem exigir conta/sandbox Twilio) —
trade-off registrado: WAHA opera sobre o protocolo WhatsApp Web via QR code
com um número real, então carrega um risco baixo, mas real, de limitação
do número por automação, ao contrário do Twilio Sandbox (oficial, sem esse
risco, porém mais burocrático de configurar).

**Sem pressão de prazo no momento da escrita desta spec:** o autor ainda não
"copiou o card" (o que dispararia o prazo formal de 7 dias), e já possui
hardware disponível (Mi Band 9, ESP32, Arduino, motores de passo,
componentes eletrônicos), o que permite um MVP mais ambicioso do que o
estritamente necessário, incluindo duas integrações reais de hardware.

## 2. Problema e escopo do MVP

**Problema:** idosos que moram sozinhos esquecem horários de medicação e
compromissos (consultas, exames), e familiares à distância não têm
visibilidade do dia a dia nem um mecanismo de alerta em caso de risco
(queda, inatividade prolongada, sinais vitais anômalos).

**Escopo do MVP (pesos iguais):**
1. **Adesão a medicação/rotina** — lembretes de remédios e compromissos,
   registro de confirmação.
2. **Segurança/risco** — monitoramento de sinais de saúde (smartwatch) e
   presença/movimento (ESP32), classificação de urgência, e escalonamento
   de alertas até a família e, em último caso, simulação de contato com
   serviço de emergência.

**Fora do escopo do MVP (mas documentado como roadmap):** v-plotter físico
que escreve a agenda do dia em um quadro branco (seção 9).

**Integrações reais de hardware no MVP:**
- Mi Band 9, via Health Connect (Android), usando o app "Health Connect
  Webhook" (Play Store, `com.hcwebhook.app`) como ponte para enviar
  leituras por webhook — evita desenvolver um app Android próprio.
- ESP32 com sensor ultrassônico (HC-SR04) para detecção de
  presença/movimento nos cômodos da casa.
- Pressão arterial e glicemia **não** entram como sensores reais no MVP
  (dispositivos médicos regulados, sem opção hobbista confiável) — ficam
  fora de escopo, não simulados.

## 3. Arquitetura — visão geral

```
                         ┌─────────────────────────┐
        WhatsApp ───────▶│   Agente de Comunicação  │◀──────── Streamlit
     (idoso, texto/áudio)│  (STT/TTS, roteamento)   │      (dashboard família)
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │   Agente Orquestrador    │  (ADK root agent)
                         └──┬──────┬──────┬─────────┘
                            │      │      │
              ┌─────────────┘      │      └─────────────┐
              ▼                    ▼                     ▼
   ┌──────────────────┐ ┌────────────────────┐ ┌────────────────────┐
   │ Agente de Rotina/ │ │ Agente de          │ │ Agente de          │
   │ Medicação         │ │ Monitoramento de   │ │ Emergência/Alertas │
   │ (agenda, lembrete)│ │ Saúde/Risco        │ │ (aciona família /  │
   └──────────────────┘ │ (embeddings p/     │ │  serviço emerg.,   │
                         │  classificar risco)│ │  simulado)         │
                         └─────────┬───────────┘ └────────────────────┘
                                   │
                     ┌─────────────┴─────────────┐
                     ▼                            ▼
           Mi Band 9 (Health Connect,       ESP32 (HC-SR04 presença)
           via Health Connect Webhook)
```

Arquitetura escolhida (dentre 3 avaliadas) para o Zela+: **5 agentes especializados**
(Orquestrador + Rotina/Medicação + Monitoramento de Saúde/Risco +
Comunicação + Emergência/Alertas), cada um com responsabilidade única e
contrato de dados Pydantic próprio. A decisão de emergência fica isolada em
seu próprio agente por ser a decisão de maior risco do sistema.

### Fluxo do dia a dia (exemplo)

1. Hora de um remédio → Agente de Rotina dispara lembrete → Agente de
   Comunicação envia WhatsApp (texto/áudio) ao idoso.
2. Idoso responde por áudio/texto → transcrito (se áudio) → Orquestrador
   registra confirmação (ou ausência dela).
3. Em paralelo, o Agente de Monitoramento consome leituras do smartwatch e
   do ESP32, aplicando regras + classificação por embeddings, gerando um
   status: `normal` / `atenção` / `risco`.
4. `atenção` → aviso à família via WhatsApp/Streamlit.
5. `risco` → Agente de Emergência aplica a política de escalonamento
   (seção 7).
6. Família consulta o Streamlit a qualquer momento (histórico de
   medicação, status de saúde/presença, alertas).

## 4. Modelos de dados (Pydantic)

Entidades centrais que validam as entradas críticas do sistema:

- **`PerfilIdoso`** — nome, data_nascimento, contatos_familiares (telefones
  em formato E.164), condições médicas (opcional).
- **`Medicamento`** — nome, dosagem (> 0), horários (lista de `time`,
  únicos), dias da semana, ativo (bool).
- **`Compromisso`** — título, data_hora (deve ser futura na criação),
  local, tipo (enum: consulta/exame/outro).
- **`ConfirmacaoMedicacao`** — referência ao medicamento, horário previsto,
  horário confirmado (opcional), status (enum: confirmado/atrasado/
  não_confirmado), canal (whatsapp/manual).
- **`LeituraSensor`** — fonte (enum: `smartwatch`/`esp32`), tipo (enum:
  frequência_cardíaca/passos/sono/presença), valor, unidade, timestamp.
  Validação de faixas plausíveis por tipo (ex.: FC entre 30–220bpm);
  leituras fora da faixa são flagueadas, não travam o sistema.
- **`EventoMonitoramento`** — status (enum: normal/atenção/risco), motivo,
  leituras relacionadas, timestamp, método de classificação
  (regra/embedding).
- **`MensagemEntrada`** — remetente, tipo (texto/áudio), conteúdo bruto,
  transcrição (preenchida após STT), timestamp.
- **`Alerta`** — nível (info/atenção/crítico), destinatário, canal,
  mensagem, status (enviado/confirmado).

Esses modelos são o contrato de dados entre os agentes: cada agente só
aceita/emite objetos validados (cobre o item 3.3 do card).

## 5. Papel do n8n vs ADK

- **n8n (substitui Langflow, itens 3.4 e 3.8)** — desenha visualmente o
  fluxo de **entrada de mensagem → classificação de urgência (via
  embeddings) → roteamento de resposta**, e hospeda a integração com
  WhatsApp via WAHA (WhatsApp HTTP API). Entregue como `.json` do workflow
  + screenshot.
- **ADK (item 3.6)** — implementa em código Python a orquestração real dos
  5 agentes definidos na arquitetura (o "motor" do sistema).

O fluxo do n8n é uma representação simplificada de uma fatia do sistema
(classificação/roteamento de mensagens); o ADK implementa a orquestração
completa. Isso evita duplicar trabalho e cumpre os dois itens do card de
forma coerente.

## 6. Embeddings

- **Classificação de urgência:** cada evento (mensagem do idoso ou leitura
  anômala de sensor) vira um embedding comparado por similaridade a um
  conjunto de exemplos de referência rotulados (`normal`/`atenção`/
  `risco`) — classificação por vizinho mais próximo, simples e explicável.
- **RAG / busca semântica:** indexação de bulas/instruções de medicamentos
  e histórico de interações em um vetor store leve (Chroma ou FAISS,
  local). Usado pelo Agente de Comunicação para responder perguntas do
  idoso/família (ex.: "para que serve esse remédio?", "o que a Vó disse
  ontem?").
- Modelo de embeddings: mesmo provedor do LLM principal do projeto (a
  definir na fase de implementação — Gemini ou OpenAI), para simplificar
  dependências.

## 7. Streamlit e WhatsApp/Áudio

- **Streamlit = painel da família:** status atual (normal/atenção/risco),
  histórico de medicação (confirmado/atrasado), últimos alertas, gráfico
  simples de presença/atividade do dia. Permite à família cadastrar/editar
  medicamentos e compromissos (evita depender do idoso digitar isso).
- **WhatsApp (WAHA) = canal do idoso:** lembretes de remédio/compromisso;
  aceita respostas em texto ou áudio. WAHA é um serviço open-source
  self-hosted (container Docker) que expõe uma API HTTP + webhooks sobre o
  protocolo WhatsApp Web (conexão via QR code com um número real), com nó
  nativo no n8n — evita depender de conta/sandbox Twilio. Áudio é
  transcrito (STT) antes de entrar no Orquestrador; resposta pode voltar em
  texto e, opcionalmente, em áudio (TTS).

## 8. Ingestão de sensores (ESP32 + Health Connect)

- **ESP32 (presença):** firmware lendo o HC-SR04, enviando leituras via
  HTTP POST a um endpoint de ingestão (FastAPI) a cada mudança de presença
  detectada em um cômodo. Vira um `LeituraSensor(fonte=esp32,
  tipo=presenca)`.
- **Mi Band 9 → Health Connect:** Health Connect é uma API on-device do
  Android sem endpoint de nuvem próprio. Ponte escolhida: app "Health
  Connect Webhook" (Play Store, `com.hcwebhook.app`), que lê o Health
  Connect e envia dados periodicamente via webhook HTTP a um endpoint de
  ingestão — evita desenvolver um app Android próprio para o MVP.
  ("Health Auto Export", cogitado inicialmente, é exclusivo do
  ecossistema Apple Health/iOS — não se aplica ao Android/Health
  Connect; descoberto e corrigido durante o brainstorming do Plano 3.)

## 9. Política de escalonamento de emergência

Fluxo em camadas, para evitar falsos positivos e não colocar em risco o uso
de canais reais de emergência sem validação humana:

1. **Detecção de risco** (Agente de Monitoramento) → aciona Agente de
   Emergência.
2. **Tentativa de contato direto com o idoso** (WhatsApp, texto/áudio),
   janela de resposta (ex.: 10 min).
3. **Sem resposta →** notificação automática aos familiares cadastrados via
   WhatsApp, nível "crítico", com contexto do que foi detectado (ex.: "sem
   movimentação há 6h + remédio das 14h não confirmado").
4. **Gravidade máxima e sem resposta da família** (janela adicional) → o
   MVP **simula** o acionamento de serviço de emergência (registra e
   notifica como se tivesse ligado), em vez de discar de verdade. Acionar
   serviços reais de emergência (SAMU/192) automaticamente é uma
   responsabilidade regulatória séria — não deve ser feito sem validação
   humana e testes extensivos. Fica documentado como próximo passo, com um
   "hook" claro no código para integração real futura.
5. Todo alerta é registrado (`Alerta`) para auditoria/histórico, visível no
   Streamlit.

## 10. Tratamento de erros e testes

- **Testes (pytest):** validação dos modelos Pydantic (casos
  válidos/inválidos), lógica de classificação de urgência com casos
  determinísticos, fluxo do orquestrador com mocks dos agentes e sensores
  (cobre o item 3.9 — testes básicos).
- **Falha de sensores:** se ESP32 ou a ponte do Health Connect pararem de
  enviar dados, o sistema gera um alerta de "sem dados" (distinto de "risco
  de saúde") — evita alarme falso por falha técnica.
- **Falha de envio WhatsApp:** retry simples + log; não trava o restante do
  sistema.

## 11. Roadmap técnico do v-plotter (fora do MVP)

Hardware já disponível: motores de passo, Arduino, ESP32, componentes
eletrônicos — plano registrado para um protótipo futuro, sem entrar no
código do MVP agora:

- **Mecânica a decidir:** v-plotter suspenso (2 motores + fio — mais
  simples/barato e mais prático para quadro branco grande) vs.
  cartesiano/CoreXY (mais preciso, mais peças).
- **Controle:** firmware tipo GRBL no Arduino (compatível com G-code,
  ecossistema maduro), recebendo comandos do ESP32 (via Wi-Fi) ou do
  backend via serial/USB.
- **Conversão texto → desenho:** fonte vetorial simples (ex.: Hershey
  fonts) para converter a "agenda do dia" (texto curto: remédios, horários,
  compromissos) em G-code.
- **Papel do agente:** um futuro "Agente de Atuação Física" receberia do
  Orquestrador um resumo diário e enviaria os comandos de desenho —
  plugaria na mesma arquitetura de 5 agentes sem redesenho.

## 12. Entregáveis mapeados ao card

| Item do card | Como é atendido |
|---|---|
| 3.1 Problema/escopo | Seção 2 |
| 3.2 Arquitetura | Seção 3 |
| 3.3 Pydantic | Seção 4 |
| 3.4 Langflow (→ n8n) | Seção 5, 17 |
| 3.5 Embeddings | Seção 6 |
| 3.6 Orquestração ADK | Seção 3, 5, 13, 14 |
| 3.7 Streamlit | Seção 7, 16 |
| 3.8 Comunicação (→ n8n/WAHA) | Seção 7, 5, 13, 17 |
| 3.9 Desenvolvimento e testes | Seção 10 |
| 3.10 Repositório e documentação | A definir no plano de implementação |

## 13. Detalhamento do Plano 2 — Comunicação Real (WAHA + persistência + runtime ADK)

O Plano 1 deixou deliberadamente em aberto a camada de persistência e o
runtime real dos agentes ADK (que ficaram só com o esqueleto estrutural,
`tools=[]`). O Plano 2 resolve essas duas lacunas ao mesmo tempo em que
implementa o canal de comunicação real com o idoso.

### Arquitetura

```
WAHA (container Docker, pareado via QR code com um número real)
   │  webhook (mensagem recebida: texto ou áudio)
   ▼
FastAPI (endpoint /webhook/whatsapp)
   │
   ▼
Runner (ADK Runner + sessão de conversa em memória, por idoso)
   │  chama ferramentas dos agentes
   ▼
Camada de serviço (lê/grava zela/storage, chama as funções puras de
zela/domain — que NÃO mudam em relação ao Plano 1)
   │
   ▼
SQLite (perfil, medicamentos, compromissos, confirmações, leituras de
sensor, alertas, estado de escalonamento)

+ um scheduler (APScheduler) rodando em paralelo ao FastAPI, checando
  lembretes de medicação/compromisso pendentes periodicamente e disparando
  mensagens de saída via WAHA.
```

### Decisões

- **Persistência:** SQLite local (arquivo único, sem servidor separado —
  adequado ao escopo de MVP e fácil de inspecionar/reproduzir). Uma nova
  camada `zela/storage/` (repositórios) fica entre o runtime e os modelos
  Pydantic; a camada `zela/domain/` do Plano 1 continua 100% pura e
  inalterada — os repositórios leem o estado necessário, chamam a função de
  domínio correspondente, e gravam o resultado de volta.
- **Ferramentas dos agentes ADK:** agora que existe onde ler/gravar estado,
  os 4 agentes especializados (Plano 1, `zela/agents/orchestrator.py`)
  ganham `tools=[...]` de verdade, apontando para funções na camada de
  serviço (que por sua vez chamam `zela/domain/`).
- **STT (voz do idoso → texto):** entrada multimodal nativa do Gemini (o
  áudio é enviado diretamente ao modelo via ADK), sem serviço de STT
  externo — decisão tomada para simplificar dependências, já que o Gemini
  já é o LLM principal do projeto.
- **TTS (resposta em áudio):** tentativa dentro do próprio Plano 2 (API de
  fala do Gemini), mas não bloqueia o plano — se a integração complicar
  demais, o MVP cai para resposta só em texto sem prejuízo ao restante do
  escopo.
- **Sessão de conversa vs. dados de domínio:** o histórico de conversa do
  ADK Runner fica em memória (aceitável perder ao reiniciar o processo); os
  dados de domínio (remédios, confirmações, alertas, leituras) persistem no
  SQLite.
- **Papel do n8n permanece adiado para o Plano 6:** o Plano 2 conecta o
  FastAPI diretamente ao WAHA (webhook de entrada, chamadas HTTP de saída),
  sem n8n no meio. O n8n entra depois como uma camada/visão adicional do
  fluxo (itens 3.4/3.8), sem reescrever a integração que já está
  funcionando.
- **Scheduler de lembretes:** um job periódico (APScheduler, embutido no
  processo do FastAPI) consulta `calcular_lembretes_pendentes` para os
  medicamentos/compromissos cadastrados e dispara mensagens via WAHA — essa
  peça não existia no Plano 1 (os testes chamavam a função de domínio
  diretamente com um `agora` fixo).
- **Setup do WAHA:** roda como container Docker separado, pareado via QR
  code com um número de WhatsApp real. Isso precisa de instruções claras no
  README (item 3.10 do card) — como subir o container, como parear o
  número, como configurar a URL do webhook apontando para o FastAPI local.

## 14. Detalhamento do Plano 3 — Ingestão de Sensores e Detecção de Risco

O Plano 1 deixou os agentes de Monitoramento e Emergência sem ferramentas
(`tools=[]`) por não haver, ainda, nenhum dado de sensor real fluindo pelo
sistema. O Plano 3 resolve isso: ingestão real do ESP32 e do smartwatch,
mais o ciclo automático de detecção de risco e escalonamento.

### Arquitetura

```
ESP32 (HC-SR04)              Mi Band 9 → Health Connect → app "Health
     │ POST                          │ Connect Webhook" (com.hcwebhook.app)
     ▼                               ▼ POST (webhook configurado no app)
POST /ingest/esp32          POST /ingest/health-connect
   (zela/api/ingestao.py, novo módulo FastAPI)
                     └──────────────┬───────────────┘
                                    ▼
                  zela/storage/monitoramento.py
                  (valida com LeituraSensor, persiste em leitura_sensor)

Scheduler (novo job, junto ao de lembretes do Plano 2, a cada 15 min):
  lê leituras recentes → classificar_por_regra (domínio, Plano 1)
  → EventoMonitoramento
  → zela/storage/escalonamento.py: lê/grava EstadoEscalonamento
    → decidir_proxima_acao (domínio, Plano 1) → list[Alerta]
  → zela/storage/alertas.py: persiste os Alertas
  → WahaClient envia cada Alerta por WhatsApp

ADK (consulta pela família via WhatsApp — o LLM nunca decide risco,
apenas responde a perguntas sobre o status já calculado pelo scheduler):
  agente_monitoramento ganha tool: consultar_status_atual(idoso_id)
    -> status mais recente + últimas leituras
  agente_emergencia ganha tool: consultar_historico_alertas(idoso_id)
    -> alertas recentes
```

### Decisões

- **Ponte do smartwatch corrigida:** o app "Health Auto Export" (decisão
  original do Plano 1) é exclusivo do ecossistema Apple Health/iOS e não
  se aplica ao Health Connect/Android. Substituído por **"Health Connect
  Webhook"** (Play Store, `com.hcwebhook.app`), feito especificamente para
  ler o Health Connect e enviar dados via webhook HTTP configurável —
  descoberto durante o brainstorming deste plano (ver seção 1 e seção 8,
  já corrigidas).
- **Detecção de risco é 100% determinística:** o ciclo automático
  (classificação + escalonamento) roda via scheduler chamando as funções
  puras de domínio diretamente — o LLM nunca participa da decisão de
  "há risco?" ou "devo escalar?". Isso é deliberado: uma decisão de
  segurança não deve depender do comportamento não determinístico de um
  LLM. O LLM só entra para a família **consultar** o status já calculado.
- **Storage finalmente completo:** `zela/storage/monitoramento.py`,
  `escalonamento.py` e `alertas.py` — todos deliberadamente adiados desde
  o Plano 2 por falta de dados de sensor — são construídos agora. O
  schema SQLite (todas as tabelas já existem desde o Plano 2, Task 3) não
  muda.
- **Ajuste retroativo no webhook do Plano 2:** a trava de segurança
  adicionada na correção final do Plano 2 (`telefone_idoso`) restringe o
  webhook a aceitar mensagens só do número da idosa. Para a família poder
  consultar o status pelo WhatsApp, essa lista precisa aceitar também os
  números de `contatos_familiares` — ajuste incluído neste plano
  (`montar_roteador` passa a aceitar uma lista de números permitidos, não
  só um).
- **Firmware do ESP32:** código Arduino/C++ real (não Python, não testável
  via `pytest`) lendo o HC-SR04 e enviando `POST /ingest/esp32` a cada
  mudança de presença detectada. Entregue como um arquivo `.ino` com
  instruções de fiação e flash no README — sem teste automatizado,
  mesmo tratamento dado ao `docker-compose.yml` do WAHA (infraestrutura
  documentada, verificação manual).
- **Risco real de API (payload do "Health Connect Webhook"):** o formato
  exato do payload que esse app envia não foi verificado neste momento —
  mesmo tratamento de risco dado ao WAHA e ao ADK Runner nos planos
  anteriores (nota explícita no plano de implementação, endpoint
  projetado para ser fácil de ajustar após inspeção real).
- **"Sem dados" como alerta distinto (spec §10):** se nenhuma leitura
  chegar por um período (ESP32 ou ponte do Health Connect param de
  enviar), o scheduler gera um alerta de nível informativo diferenciado
  de "risco de saúde" — evita alarme falso por falha técnica, conforme já
  previsto na seção 10.

## 15. Detalhamento do Plano 4 — Embeddings (classificação por similaridade + RAG)

A seção 6 previa dois usos de embeddings, ainda não implementados: classificar
a urgência de mensagens de texto do idoso por vizinho mais próximo, e
responder perguntas ("para que serve esse remédio?", "o que a Vó disse
ontem?") por busca semântica. O modelo `MetodoClassificacao.EMBEDDING`, já
previsto desde o Plano 1 em `zela/models/monitoramento.py`, é usado pela
primeira vez neste plano.

### Arquitetura

```
Mensagem do idoso chega em POST /webhook/whatsapp (zela/api/webhook.py)
  │
  ├──▶ processar_mensagem (ADK Runner, já existente) → resposta ao idoso
  │
  └──▶ processar_risco_mensagem (novo, zela/api/monitoramento_mensagem.py)
          │  (só roda se o remetente é o idoso, não familiares)
          ▼
        client.obter_embedding(texto)      [zela/embeddings/client.py — I/O, Gemini]
          ▼
        classificar_por_similaridade(...)  [zela/embeddings/classificador.py — puro]
          → EventoMonitoramento(metodo_classificacao=EMBEDDING)
          ▼
        storage/escalonamento.py::aplicar_escalonamento   (Plano 3, reaproveitado)
          → decidir_proxima_acao (domínio, Plano 1, intocado)  → list[Alerta]
          ▼
        despachar_alertas(...)  [extraído de scheduler.py] → WahaClient
          │
          └──▶ vetorial.indexar_documento(...)  [zela/embeddings/vetorial.py — Chroma]
                 (a mesma mensagem também vira um documento indexado)

RAG (consulta pela família/idoso via WhatsApp):
  agente_comunicacao ganha tool: consultar_conhecimento(pergunta)
    → vetorial.buscar_similares(...) → trechos de bulas + mensagens passadas
    → LLM usa os trechos para responder (tool só leitura, não decide nada)

Reindexação em lote (bulas/medicamentos já cadastrados):
  main.py (lifespan, na subida da API)
    → reindexar_documentos(conn, idoso_id) [zela/embeddings/vetorial.py]
```

### Decisões

- **Provedor único (Gemini) e vector store local (Chroma):** mesmo provedor
  do LLM principal (`text-embedding-004`), evitando uma segunda credencial
  de API só para embeddings. Chroma persiste em `./chroma_db/` (adicionado
  ao `.gitignore`), simples o suficiente para o volume de dados do MVP
  (um idoso, poucos medicamentos, histórico de mensagens moderado).
- **Classificação por embedding entra pela mesma porta que os sensores:**
  `classificar_por_similaridade` produz um `EventoMonitoramento` como
  qualquer outro método de classificação — quem decide se isso vira
  contato/notificação/simulação de emergência continua sendo
  `decidir_proxima_acao` (domínio, Plano 1, determinístico, intocado). Isso
  preserva a propriedade central de segurança já estabelecida nos Planos
  1-3: nem o LLM nem o embedding decidem escalonamento, apenas relatam um
  status. Mesmo um `RISCO` vindo de embedding entra pela etapa
  `CONTATO_IDOSO` (10 min de espera) antes de qualquer notificação à
  família — não pula etapas.
- **Refatoração pequena em `scheduler.py`:** extração de
  `despachar_alertas(conn, alertas, perfil, waha_client)` (salvar +
  enviar por WhatsApp, pulando alertas `simulado=True`), hoje inline em
  `verificar_e_escalonar_riscos` (Plano 3). Passa a ser reaproveitada pelo
  novo caminho de mensagem, evitando duas implementações divergentes do
  mesmo comportamento de despacho.
- **Novo campo `Medicamento.bula`** (`str | None`, com coluna
  correspondente no schema SQLite): texto curto de instrução/uso,
  cadastrado manualmente por ora — não há API real de bulas no MVP. O
  script de seed pode incluir um texto de exemplo genérico por
  medicamento cadastrado.
- **Indexação em lote no boot, não por hook de escrita:** como o Streamlit
  (Plano 5) ainda não existe para editar medicamentos ao vivo, uma
  reindexação completa no `lifespan` da API (em vez de instrumentar cada
  ponto de escrita em `storage/rotina.py`) é suficiente para o MVP e mais
  simples. Mensagens do idoso, por serem eventos contínuos em tempo real,
  são indexadas inline no momento em que chegam.
- **Falha graciosa (spec §10):** falha na API de embeddings ou no Chroma
  (rede fora do ar, quota excedida) é isolada em try/except, loga e não
  bloqueia nem o webhook nem a resposta do LLM — mesma filosofia já usada
  para falha de envio de WhatsApp. Sem embedding disponível naquele ciclo,
  a detecção de risco por sensores (Plano 3) continua cobrindo o
  monitoramento normalmente.
- **Testes sem rede real:** `classificador.py` é puro (testado com vetores
  fake e similaridade de cosseno calculável à mão); `client.py` e
  `vetorial.py` são testados via fakes injetados, mesmo padrão já usado
  para `WahaClient`. Um teste de integração real (manual, documentado no
  README) valida a chave de API do Gemini e a persistência do Chroma em
  disco — mesmo tratamento dado a WAHA e ao firmware do ESP32.

## 16. Detalhamento do Plano 5 — Painel Streamlit (família)

A seção 7 previa o Streamlit como painel da família (status, histórico de
medicação, alertas, gráfico de presença, cadastro de medicamentos e
compromissos), ainda não construído. Este plano fecha essa lacuna.

### Arquitetura

```
Família abre o navegador em localhost:8501 (streamlit run)
  │
  ▼
zela/streamlit_app/app.py (entrypoint)
  │  gate de senha: STREAMLIT_SENHA (env var) -> st.session_state["autenticado"]
  ▼
zela/streamlit_app/secoes.py (somente leitura, reaproveita storage já existente)
  ├── renderizar_status       -> storage/monitoramento.py::aplicar_classificacao (Plano 3)
  ├── renderizar_medicacao    -> storage/rotina.py::listar_confirmacoes_do_dia (Plano 1/2)
  ├── renderizar_alertas      -> storage/alertas.py::listar_alertas (Plano 3)
  └── renderizar_grafico      -> storage/monitoramento.py::listar_leituras_recentes (Plano 3)
                                  -> pandas.DataFrame -> st.line_chart

zela/streamlit_app/formularios.py (escrita)
  ├── formulario_medicamento  -> storage/rotina.py::salvar_medicamento (Plano 2, upsert existente)
  └── formulario_compromisso  -> storage/rotina.py::salvar_compromisso (NOVO, upsert)
                                  storage/rotina.py::listar_compromissos (NOVO)

Todo acesso a dados é direto no SQLite (zela.db) via zela/storage/*,
mesmo padrão já usado por zela/api/scheduler.py e
zela/agents/orchestrator.py — sem API HTTP nova.
```

### Decisões

- **Acesso direto ao SQLite, sem API HTTP nova:** consistente com o resto
  do projeto (scheduler, orquestrador ADK, processamento de mensagem por
  embedding — todos conectam direto em `zela.db` via `zela/storage/*`).
  Evita construir e manter uma camada REST só para o painel.
- **Uma página única, com seções** (em vez de multipage nativo do
  Streamlit): mais simples de navegar para uma família não-técnica, sem
  menu lateral. `secoes.py` e `formularios.py` mantêm cada seção como uma
  função de renderização isolada, facilitando tanto a leitura do código
  quanto o teste individual.
- **Gráfico nativo do Streamlit (`st.line_chart` via pandas), sem
  dependência de gráfico adicional (ex.: Altair):** suficiente para
  "picos de atividade ao longo do dia" e evita uma dependência nova só
  para isso.
- **Autenticação por senha simples via variável de ambiente
  (`STREAMLIT_SENHA`):** mais forte que "sem autenticação" (que seria o
  padrão dos outros planos, ex. endpoints de ingestão do Plano 3), porque
  este painel expõe dados de saúde. Se a variável não estiver definida, o
  app recusa subir — evita rodar sem senha por esquecimento. Ainda assim,
  é uma senha única compartilhada, não um sistema de contas por usuário;
  documentado como limitação conhecida.
- **`salvar_compromisso`/`listar_compromissos` novos em
  `zela/storage/rotina.py`:** a tabela `compromisso` e o modelo
  `Compromisso` já existem desde o Plano 2 (schema e Pydantic prontos),
  mas nenhuma camada de storage foi construída até agora — não havia
  nenhum consumidor. O padrão de upsert por `id` é idêntico ao já usado
  em `salvar_medicamento`.
- **IDs gerados no cliente:** medicamentos/compromissos novos criados
  pelo formulário recebem `id=str(uuid.uuid4())` antes de chamar
  `salvar_*` — o schema já trata `id` como chave primária fornecida pelo
  chamador (não é autoincremento), então isso é consistente com o padrão
  já usado pelos scripts de seed dos planos anteriores.
- **Testes com `streamlit.testing.v1.AppTest`** (framework oficial de
  testes do Streamlit, execução real do script, sem mocks do próprio
  Streamlit) — verificado nesta máquina (`streamlit==1.64.0`) que
  simular digitação/cliques (`at.text_input[...].input(...).run()`,
  `at.button[...].click().run()`) e ler o que foi renderizado
  (`at.metric`, `at.warning`, `at.success`, etc.) funciona de ponta a
  ponta. O caminho do banco é lido de uma variável de ambiente
  (`ZELA_DB_PATH`, fallback `"zela.db"`), permitindo que os testes
  apontem para um banco isolado em `tmp_path` via
  `monkeypatch.setenv(...)` antes de rodar o `AppTest` — mesmo padrão de
  configuração por variável de ambiente já usado no projeto
  (`GOOGLE_API_KEY`, `WAHA_BASE_URL`, etc.), sem precisar de rede real.
- **Erros de validação (Pydantic) e de storage são capturados e exibidos
  via `st.error`**, nunca deixando o Streamlit quebrar com uma stack
  trace visível para a família — mesma filosofia de falha graciosa já
  aplicada nos Planos 3 e 4.
- **Fora do escopo de teste automatizado:** aparência visual e experiência
  de uso real no navegador — verificação manual, documentada no README
  (mesmo tratamento já dado ao WAHA e ao firmware do ESP32).

## 17. Detalhamento do Plano 6 — Workflow n8n (itens 3.4/3.8 do card)

A seção 5 previa o n8n como uma representação visual simplificada de uma
fatia do sistema (entrada de mensagem → classificação de urgência →
roteamento), adiada desde o Plano 2. Este plano entrega essa peça.

### Arquitetura

```
n8n (instância já existente do usuário — fora do escopo deste plano)
  │
  ▼
Webhook (trigger, POST, corpo: {"telefone": "...", "texto": "..."})
  │  n8n aninha o corpo da requisição em $json.body.* (verificado no
  │  código-fonte do nó Webhook, não assumido pela documentação)
  ▼
HTTP Request -> POST /api/classificar-mensagem (backend Zela+, novo)
  │  corpo: {"texto": $json.body.texto} via expressão JS (evita bugs de
  │  escape manual de string)
  ▼
zela/api/classificacao.py (NOVO)
  │  obter_embedding (Plano 4) -> classificar_por_similaridade (Plano 4)
  │  SOMENTE classifica -- nunca chama aplicar_escalonamento
  ▼
{"status": "normal"|"atencao"|"risco", "motivo": "..."}
  │
  ▼
If #1: status == "risco"?  --sim--> Respond to Webhook (alertar família)
  │ não
  ▼
If #2: status == "atencao"? --sim--> Respond to Webhook (verificar idosa)
  │ não
  ▼
Respond to Webhook (normal, sem ação)
```

### Decisões

- **Webhook próprio do n8n, independente da integração real WAHA→FastAPI
  do Plano 2:** o fluxo n8n tem seu próprio endpoint de entrada (disparado
  manualmente com `curl` ou pela ferramenta de teste do próprio n8n) — não
  reconfigura o WAHA nem o webhook real, exatamente como a seção 13 já
  havia decidido. Isso cumpre os itens 3.4/3.8 do card sem colocar em
  risco a integração que já está funcionando.
- **Novo endpoint `POST /api/classificar-mensagem`, somente classificação:**
  reaproveita o classificador de embeddings do Plano 4
  (`obter_embedding` + `classificar_por_similaridade`), mas **nunca** chama
  `aplicar_escalonamento` — preserva a propriedade central de segurança do
  projeto (nem o n8n, nem esse endpoint, decidem escalonamento de
  verdade). Erros de embedding retornam HTTP 503 com corpo JSON de erro,
  em vez de deixar a exceção propagar — mesma filosofia de falha graciosa
  dos planos anteriores, expressa como código de status HTTP (não há
  `st.error` fora do contexto Streamlit).
- **Roteamento com 2 nós "If" encadeados, não um "Switch":** o schema JSON
  do nó Switch do n8n não pôde ser verificado com confiança contra uma
  versão real durante o brainstorming; o nó "If" (`n8n-nodes-base.if`,
  typeVersion 2) foi verificado contra um exemplo real e contra o código-
  fonte do n8n (GitHub). Dois "If" encadeados (risco? / atenção?) produzem
  o mesmo roteamento de 3 ramos com um schema confiável.
- **Todo o JSON do workflow foi verificado contra o código-fonte do n8n
  antes de ser escrito** (tipos de nó, `typeVersion`, nomes exatos de
  parâmetros, e o formato de saída do nó Webhook — `$json.body.*`, não
  `$json.*` direto) — mesmo tratamento de rigor já dado a payloads de
  APIs externas neste projeto (WAHA, Health Connect Webhook), evitando
  entregar um `.json` que falha ao importar ou quebra silenciosamente na
  primeira execução.
- **Sem teste automatizado para o workflow n8n em si** (mesmo tratamento
  já dado ao WAHA e ao firmware do ESP32): verificação manual — importar
  o `.json`, disparar com uma mensagem de teste, confirmar o roteamento,
  tirar o screenshot exigido pelo item 3.4 do card. O endpoint novo
  (`classificar-mensagem`) tem teste `pytest` completo (sucesso e erro
  503), com cliente de embedding fake — sem chamada real ao Gemini.
- **Entregáveis:** `docs/n8n/zela-classificacao-mensagem.json` (workflow
  exportável) e um screenshot (adicionado pelo usuário após testar no seu
  n8n) — mesmo padrão de "arquivo + captura de tela" já pedido pelo item
  3.4 do card original.
