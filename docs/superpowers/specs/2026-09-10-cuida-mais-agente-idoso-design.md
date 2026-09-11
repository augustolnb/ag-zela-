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
- Mi Band 9, via Health Connect (Android), usando o app "Health Auto
  Export" como ponte para enviar leituras por webhook — evita desenvolver
  um app Android próprio.
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
           via Health Auto Export)
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
  WhatsApp/Twilio. Entregue como `.json` do workflow + screenshot.
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
- **WhatsApp (Twilio Sandbox) = canal do idoso:** lembretes de
  remédio/compromisso; aceita respostas em texto ou áudio. Áudio é
  transcrito (STT) antes de entrar no Orquestrador; resposta pode voltar em
  texto e, opcionalmente, em áudio (TTS).

## 8. Ingestão de sensores (ESP32 + Health Connect)

- **ESP32 (presença):** firmware lendo o HC-SR04, enviando leituras via
  HTTP POST a um endpoint de ingestão (FastAPI) a cada mudança de presença
  detectada em um cômodo. Vira um `LeituraSensor(fonte=esp32,
  tipo=presenca)`.
- **Mi Band 9 → Health Connect:** Health Connect é uma API on-device do
  Android sem endpoint de nuvem próprio. Ponte escolhida: app "Health Auto
  Export" (Play Store), que lê o Health Connect e envia dados
  periodicamente via webhook HTTP ao mesmo endpoint de ingestão — evita
  desenvolver um app Android próprio para o MVP.

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
| 3.6 Orquestração ADK | Seção 3, 5 |
| 3.7 Streamlit | Seção 7 |
| 3.8 Comunicação (→ n8n/Twilio) | Seção 7, 5 |
| 3.9 Desenvolvimento e testes | Seção 10 |
| 3.10 Repositório e documentação | A definir no plano de implementação |
