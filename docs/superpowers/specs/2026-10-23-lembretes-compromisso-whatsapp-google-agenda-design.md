# Lembretes automáticos de Compromisso (WhatsApp + Google Agenda)

Spec de design (fase de brainstorming), previamente ao plano de implementação.

## 1. Contexto e motivação

Hoje o painel permite cadastrar `Compromisso` (consulta, exame, outro — ver
`zela/models/rotina.py`), mas **não existe nenhum lembrete automático** para
eles. O `scheduler.py` atual só dispara lembretes de `Medicamento`
(recorrente, por `horarios`/`dias_semana`) e alertas de escalonamento de
risco — `Compromisso` só é consultado pelo agente de IA quando alguém
pergunta na conversa.

Motivação (relato do autor): depender só de um lembrete por texto (WhatsApp)
é insuficiente e não aproveita o hardware já presente no projeto — o
Xiaomi Smart Band 10 Pro do idoso, pareado via Mi Fitness no celular dele
(Redmi 13, HyperOS). O objetivo é que um compromisso importante dispare
lembrete tanto por WhatsApp quanto no pulso do idoso, sem depender de
nenhum recurso exclusivo de uma marca de celular — o card é avaliado/vendido
como conceito de produto, então a entrega no relógio precisa funcionar em
qualquer Android, não só em HyperOS/MIUI.

**Investigação prévia (descartada):** o app "Tarefas" do relógio, que o
autor lembrava ter mostrado anotações do Google, não é uma integração
dedicada com Google Tasks/Keep — é a função nativa de sincronização de
eventos do Mi Fitness, que é **limitada oficialmente a celulares
MIUI/HyperOS ou iPhone** (não documentada para Android genérico). Por isso
este design **não depende** dela. Em vez disso, usa o caminho que já
funciona em qualquer Android desde o Android 4.3: a permissão padrão de
"acesso a notificações", que o Mi Fitness usa para espelhar no relógio a
notificação de qualquer app do celular — incluindo a notificação de
lembrete (popup) do próprio app Google Agenda.

Conclusão de desenho: **não são duas integrações independentes**, é uma
única integração (Google Calendar API) com dois canais de entrega em
paralelo (WhatsApp direto do backend; Google Agenda → notificação nativa do
Android → espelhamento Mi Fitness → vibração no pulso).

## 2. Escopo (o que este design cobre)

Para `Compromisso` (consulta, exame, outro — tem `data_hora` única e
futura), ao ser cadastrado, editado ou removido no painel:

- **Canal WhatsApp:** reaproveita o padrão do `scheduler.py`/`WahaClient`
  já usado para medicamento. Enviado **tanto para o idoso quanto para os
  contatos familiares** (`PerfilIdoso.contatos_familiares`).
- **Canal Google Agenda:** cria/atualiza/remove um evento via Google
  Calendar API numa conta Google dedicada da família, com lembretes
  (overrides) configurados no próprio evento.

Disparos por WhatsApp (4, direto do backend):

1. **Instantâneo** — ao cadastrar o compromisso.
2. **24h antes** de `data_hora`.
3. **Pela manhã do dia do compromisso** — horário fixo `HORARIO_LEMBRETE_MANHA`
   (constante no código, default 08:00 hora local), só se for antes de
   `data_hora`.
4. **1h antes** de `data_hora`.

Disparos por Google Agenda (3 *overrides* no evento — ver seção 5.2 sobre
por que não existe um "instantâneo" equivalente num evento de calendário):

1. **24h antes** de `data_hora`.
2. **Pela manhã do dia do compromisso** — mesma constante `HORARIO_LEMBRETE_MANHA`.
3. **1h antes** de `data_hora`.

Qualquer disparo cujo horário calculado já tenha passado no momento do
cadastro (ex.: compromisso criado com 10h de antecedência não dispara o
lembrete de "24h antes") é descartado silenciosamente — não há
"disparo atrasado" retroativo, exceto o instantâneo, que sempre dispara.

Além dos 4 disparos de criação, **remover um compromisso dispara um aviso
de cancelamento por WhatsApp** (pro idoso e pros familiares) — ver seção
5.4/5.5. Não existe equivalente de cancelamento no Google Agenda porque lá
a remoção do evento já é o próprio aviso (o evento simplesmente some da
agenda).

## 3. Fora de escopo (non-goals)

- **`Medicamento`** — é recorrente (sem uma única `data_hora`), então o
  mesmo esquema de 4 disparos não se aplica da mesma forma. Fica para uma
  rodada futura (issue separada).
- **Armazenamento de credencial multi-família/multi-tenant.** O app hoje é
  single-tenant (`ID_IDOSO = "idosa-1"` fixo em `zela/api/main.py`); a
  credencial OAuth da conta Google é guardada como variável de ambiente,
  no mesmo padrão de `ZELA_WAHA_API_KEY`. Modelo de dados multi-família
  (uma credencial por `idoso_id`) é trabalho futuro, quando o pivô
  multi-tenant comercial de fato acontecer.
- **Confirmação/ACK do lembrete de compromisso** (análogo a
  `ConfirmacaoMedicacao`/`StatusConfirmacao`). Não foi pedido — os lembretes
  são "dispara e esquece", sem rastrear se a família confirmou leitura.
- **Qualquer dependência do widget nativo "eventos" do Mi Fitness**
  (MIUI/HyperOS/iOS-only) — ver seção 1.

## 4. Anti-objetivos

Isso seria considerado uma falha mesmo que "funcione técnicamente":

- A entrega no relógio depender de o celular ser Xiaomi/MIUI/HyperOS — tem
  que funcionar em qualquer Android com Mi Fitness instalado.
- Uma falha na API do Google Calendar (token expirado, rede fora) **bloquear
  ou quebrar o cadastro do compromisso** no painel, ou impedir o envio do
  lembrete por WhatsApp. Os dois canais são independentes: falha em um não
  pode afetar o outro, e nenhum dos dois pode impedir salvar o compromisso.
- Reenvio em massa de lembretes duplicados após um restart/crash-loop do
  processo (ver seção 6, estado persistido em vez de em memória).

## 5. Decisões de arquitetura (a cargo do builder, já definidas aqui)

### 5.1 Conta Google e comissionamento

Conta Google dedicada por família (não uma conta única global compartilhada
entre clientes — isso misturaria compromissos de famílias diferentes). Hoje,
com o app single-tenant, isso é uma única conta, configurada manualmente no
comissionamento:

1. Criar a conta Google dedicada (ex.: `familia-sobrenome.zela@gmail.com`).
2. Criar um projeto no Google Cloud, ativar a Calendar API, criar
   credencial OAuth (tipo "Desktop app" basta — não precisa de verificação
   do Google nem publicar o app, só adicionar essa conta como "test user").
3. Rodar uma vez um script local (`scripts/obter_refresh_token_google.py`,
   a ser criado) que faz o fluxo OAuth interativo e imprime o
   `refresh_token`.
4. Colocar `client_id`, `client_secret` e `refresh_token` nas variáveis de
   ambiente do deploy (`ZELA_GOOGLE_CALENDAR_CLIENT_ID`,
   `_CLIENT_SECRET`, `_REFRESH_TOKEN`, `_CALENDAR_ID`).
5. No celular do idoso, adicionar essa mesma conta Google como conta
   secundária no app Google/Agenda (Android permite múltiplas contas),
   habilitar notificações de lembrete do Google Agenda para ela, e
   habilitar/whitelistar o Google Agenda no espelhamento de notificações do
   Mi Fitness.

Passos 1–4 e o script de 3 entram neste trabalho; o passo 5 é operacional
(documentar no README/comissionamento, não é código).

Credencial só existe no container `backend` (variáveis `ZELA_GOOGLE_*`,
seção 5.5) — o container `streamlit` nunca recebe essas variáveis nem
instancia o cliente da Calendar API diretamente (ver seção 5.5).

### 5.2 Novo cliente de integração

`zela/integrations/google_calendar_client.py`, mesmo espírito de
`waha_client.py`: uma classe fina (`GoogleCalendarClient`) com métodos
`criar_evento`, `atualizar_evento`, `remover_evento`, usando
`google-api-python-client` + `google-auth` (novas dependências no
`pyproject.toml`). Internamente troca o `refresh_token` por um
`access_token` a cada chamada (sem persistir access token).

Cada evento é criado/atualizado com 3 *overrides* (não 4 — não existe
"instantâneo" num evento de calendário: um lembrete é sempre "N minutos
antes do início", e "0 minutos antes da criação" não é uma opção da API;
o disparo instantâneo fica só no canal WhatsApp, seção 2):
```
reminders: {
  useDefault: false,
  overrides: [
    {method: "popup", minutes: <24h em minutos, se ainda no futuro>},
    {method: "popup", minutes: <minutos até HORARIO_LEMBRETE_MANHA, se ainda no futuro>},
    {method: "popup", minutes: 60},
  ]
}
```
(minutos sempre calculados em relação a `data_hora`, já que a Calendar API
só aceita overrides relativos ao início do evento — `HORARIO_LEMBRETE_MANHA`
é convertido para minutos-antes no momento da criação/edição. Se menos de 3
overrides ainda fazem sentido no futuro — ex.: compromisso criado a menos
de 24h — a lista enviada à API tem só os que sobraram.)

### 5.3 Esquema de dados

Novas colunas em `compromisso`:
- `google_event_id TEXT` (nullable) — id retornado pela Calendar API,
  usado depois para atualizar/remover o evento.
- `google_sync_pendente INTEGER NOT NULL DEFAULT 1` — marcado em 1 por
  `salvar_compromisso` (tanto no insert quanto no `ON CONFLICT DO UPDATE`);
  o job do scheduler (seção 5.5) processa as linhas com esse flag e marca
  de volta para 0 só depois de uma chamada bem-sucedida à Calendar API.
- `removido INTEGER NOT NULL DEFAULT 0` — soft-delete: `listar_compromissos`
  passa a filtrar `WHERE removido = 0`; remover um compromisso pelo painel
  só seta essa coluna (mais `google_sync_pendente = 1`, pra o scheduler
  saber que precisa chamar `remover_evento`), sem exigir que o `streamlit`
  faça nenhuma chamada de saída (ver seção 5.5).

Nova tabela `lembrete_compromisso_enviado`:
```sql
CREATE TABLE IF NOT EXISTS lembrete_compromisso_enviado (
    id INTEGER PRIMARY KEY,
    compromisso_id TEXT NOT NULL,
    tipo_lembrete TEXT NOT NULL,  -- instantaneo | 24h | manha | 1h | cancelamento
    enviado_em TEXT NOT NULL,
    UNIQUE(compromisso_id, tipo_lembrete)
);
```
Estado **persistido** (não em memória como `_lembretes_ja_enviados` do
medicamento) — diferente do lembrete de medicação (recorrente diário, onde
reenviar após um restart é inofensivo), aqui cada tipo de lembrete dispara
só uma vez na vida do compromisso, então precisa sobreviver a um restart do
processo para não duplicar nem perder o controle.

### 5.4 Edição e remoção de compromisso

- **Editar `data_hora`:** `salvar_compromisso` marca `google_sync_pendente
  = 1` (sempre, em qualquer edição) e apaga as linhas de
  `lembrete_compromisso_enviado` dessa `compromisso_id` cujo horário-alvo
  (recalculado com a nova `data_hora`) ainda está no futuro — permite
  reenviar lembretes que ainda fazem sentido com o novo horário, mesmo que
  já tivessem sido enviados com o horário antigo.
- **Remover compromisso:** só grava `removido = 1` e
  `google_sync_pendente = 1` na linha — nenhuma chamada de saída feita
  pelo `streamlit` (ver seção 5.5 sobre por quê). `listar_compromissos`
  passa a filtrar `removido = 0`, então o compromisso desaparece do painel
  na hora, mesmo antes do scheduler processar a remoção do evento do
  Google Agenda e o aviso de cancelamento por WhatsApp. A linha
  soft-deleted (`removido = 1`) não é apagada da tabela depois — fica lá
  como histórico; não há janela de corrida entre o job de WhatsApp e o de
  Google Agenda porque nenhum dos dois depende da linha ser removida pelo
  outro (ver seção 5.5).
- Falha na chamada à Calendar API (criação, atualização ou remoção) é
  **logada e não bloqueia** nada — como agora é sempre o scheduler quem
  faz essas chamadas (assíncrono), uma falha só significa que
  `google_sync_pendente` continua 1 e a linha é tentada de novo no próximo
  tick (retry automático, de graça).

### 5.5 Scheduler — único lugar com acesso a integrações externas

**Correção importante em relação a uma versão anterior deste documento:**
o `salvar_compromisso`/remoção são chamados de dentro de
`zela/streamlit_app/formularios.py`, que roda no container `streamlit` —
um processo separado do `backend` (ver `docker-compose.yml`). Hoje o
`streamlit` não tem nenhum cliente de integração (nem `WahaClient`, nem
nada) e nunca faz chamada de saída; toda integração externa (WAHA) vive só
no `backend`, acionada pelo polling do scheduler. Fazer a sincronização
com o Google Agenda de forma síncrona a partir do formulário do painel
quebraria esse padrão — duplicaria a credencial Google num container que
hoje não tem superfície de rede nenhuma pra isso. Em vez disso, **a
sincronização com o Google Agenda também é assíncrona, via scheduler no
`backend`**, igual ao lembrete por WhatsApp.

Dois jobs novos no `iniciar_scheduler` (mesmo padrão dos jobs existentes,
`BackgroundScheduler`/`interval`, a cada `INTERVALO_MINUTOS` = 5 min):

1. **Lembretes WhatsApp:** dois casos, independentes entre si:
   - Compromissos ativos (`removido = 0`) com algum dos 4 horários-alvo de
     criação dentro da janela atual e ainda sem linha em
     `lembrete_compromisso_enviado` para esse tipo. Envia WhatsApp pro
     idoso e pros familiares, grava a linha de controle.
   - Compromissos com `removido = 1` e ainda sem linha
     `tipo_lembrete = "cancelamento"` em `lembrete_compromisso_enviado`.
     Envia o aviso de cancelamento pro idoso e pros familiares, grava a
     linha de controle (sem janela de tempo — dispara assim que detectado,
     uma única vez).
2. **Sincronização Google Agenda:** compromissos com `google_sync_pendente
   = 1`. Se `removido = 1`: chama `remover_evento(google_event_id)` (se
   houver). Se `google_event_id` é `NULL` (e não removido): chama
   `criar_evento`, salva o id retornado. Senão: chama `atualizar_evento`.
   Em qualquer caso de sucesso, zera `google_sync_pendente` (a linha
   continua existindo — ver seção 5.4).

Consequência aceita: tanto o lembrete WhatsApp "instantâneo" quanto a
criação do evento no Google Agenda disparam dentro de até ~5 minutos do
cadastro (próximo tick do scheduler), não de forma síncrona — mesma
granularidade que já existe hoje pro lembrete de medicação
(`JANELA_LEMBRETE` de 15 min). Isso mantém o `streamlit` livre de qualquer
credencial ou chamada de integração, consistente com a arquitetura atual.

## 6. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Token OAuth expira/é revogado | `refresh_token` não expira por tempo (só se revogado manualmente ou app ficar "unused" por 6 meses); logar erro 401/403 da Calendar API como alerta técnico, sem quebrar o resto |
| Mi Fitness não está espelhando notificação do Google Agenda no celular do idoso | Fora do controle do código — é configuração de comissionamento (seção 5.1, passo 5); documentar no README como passo obrigatório de instalação |
| Guardar `client_secret`/`refresh_token` em variável de ambiente em texto puro | Mesmo nível de risco que `ZELA_WAHA_API_KEY` hoje (já aceito no projeto); não introduz um padrão novo |
| Duplicar lembrete por restart do processo no meio de uma janela | Estado persistido em tabela (seção 5.3), não em memória |

## 7. Testes

Seguindo o padrão existente (`tests/test_domain_rotina.py`,
`tests/test_storage_rotina.py`, `tests/test_api_scheduler.py`):

- `zela/domain/compromisso_lembretes.py` (função pura: dado um
  `Compromisso` e um "agora", retorna a lista de
  `(tipo_lembrete, horario_alvo)` ainda no futuro) — testes de domínio sem
  I/O, cobrindo os casos de borda (compromisso criado a menos de 24h,
  manhã fixa depois de `data_hora`, etc.).
- `GoogleCalendarClient` — testado com `httpx`/transport mockado (mesmo
  padrão usado pra `WahaClient`), sem bater na API real do Google nos
  testes automatizados.
- Novo job do scheduler — testado como os jobs existentes em
  `test_api_scheduler.py`, com `waha_client` e `google_calendar_client`
  fake/mock.

## 8. Fases sugeridas de implementação

(Decisão final de quebra em PRs fica para o plano de implementação, não
para este design — registrado aqui só como ponto de partida.)

1. Domínio: cálculo dos horários-alvo + colunas `removido`/
   `google_sync_pendente` + tabela `lembrete_compromisso_enviado` + job de
   lembretes/cancelamento por WhatsApp.
2. `GoogleCalendarClient` + coluna `google_event_id` + job de sincronização
   assíncrona (criar/atualizar/remover evento) no scheduler.
3. Script de comissionamento (`obter_refresh_token_google.py`) +
   documentação do fluxo de comissionamento no README.
