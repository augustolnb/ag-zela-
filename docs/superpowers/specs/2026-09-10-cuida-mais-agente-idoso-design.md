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
| 3.4 Langflow (→ n8n) | Seção 5 |
| 3.5 Embeddings | Seção 6 |
| 3.6 Orquestração ADK | Seção 3, 5, 13, 14 |
| 3.7 Streamlit | Seção 7 |
| 3.8 Comunicação (→ n8n/WAHA) | Seção 7, 5, 13 |
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
