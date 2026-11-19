# Notificações na pulseira via Gmail — design

Status: aguardando aprovação.

## Por que isto existe

O usuário quer usar os recursos do Gmail para mandar mensagens que apareçam
na pulseira do idoso (Xiaomi Smart Band 10 Pro) e ganhar crédito no
trabalho com isso. O Mi Fitness espelha na pulseira as notificações de apps
do celular, e o Gmail é um deles. A conta de teste, criada pelo usuário, é a
mesma que o Google Agenda já usa (PR #64) e fica logada no celular do idoso.

Valor além do WhatsApp:

- **canal redundante:** não depende da sessão do WAHA nem do WhatsApp;
- **assunto curto e legível** na tela pequena da pulseira;
- **mesmo login do Google** usado pelo Google Agenda, sem conta ou serviço
  novo.

## Comportamento

### O que vai para a pulseira (decisão do usuário: "Você está bem?" e lembretes)

| Momento | Assunto (até 40 caracteres) | Corpo |
|---|---|---|
| Lembrete de remédio (scheduler) | `Zela+: hora do remédio` | nome e dose, "responda no WhatsApp" |
| Relato de sintoma que abre episódio | `Zela+: você está bem?` | "responda ESTOU BEM no WhatsApp em 60 s", "em emergência, ligue 192" |
| Checagem da escada de risco ao idoso | `Zela+: está tudo bem?` | a mensagem do alerta |

Os avisos à família continuam só no WhatsApp. Os lembretes de compromisso
continuam no Google Agenda.

### Regras

1. O Gmail é um canal **adicional**: nunca atrasa, bloqueia ou cancela o
   WhatsApp, o episódio de 60 s ou a escada. Uma falha do Gmail só gera log.
2. Sem as variáveis de ambiente, a função fica desligada e nada muda.
3. Cada evento gera no máximo uma notificação, com a mesma desduplicação do
   envio por WhatsApp.
4. No webhook, a notificação do sintoma roda em segundo plano, para a
   resposta ao idoso não esperar a API do Google.

## Decisões técnicas (do Claude, para revisão)

- **Como a mensagem chega à caixa de entrada:** um e-mail enviado da conta
  para ela mesma pode não gerar notificação no app do Gmail. O cliente
  suporta dois modos, escolhidos por `ZELA_GMAIL_MODO`:
  - `insert` (padrão): `users.messages.insert` com rótulos `INBOX` e
    `UNREAD`, que coloca a mensagem direto na caixa de entrada como não
    lida;
  - `send`: `users.messages.send` da conta para ela mesma.

  Um script de teste envia uma mensagem de cada modo, e o usuário confere
  qual vibra na pulseira antes de fixar o modo.
- **Escopos OAuth:** o script de token passa a pedir `calendar`,
  `gmail.insert` e `gmail.send` em um único consentimento. O `gmail.insert`
  é um escopo restrito: se o Google recusar o consentimento sem
  verificação, o modo `send` é o reserva.
- **Credenciais:** reaproveita `ZELA_GOOGLE_CALENDAR_CLIENT_ID`, `_SECRET` e
  `_REFRESH_TOKEN`. Novas variáveis: `ZELA_GMAIL_PULSEIRA_EMAIL` (endereço
  da conta, que liga a função) e `ZELA_GMAIL_MODO`.
- **Sem registro no painel:** as notificações por e-mail espelham mensagens
  que já existem e só vão para o log.

## Fora do escopo

- Ler respostas por e-mail: o idoso continua respondendo pelo WhatsApp.
- Avisos por e-mail à família.
- Verificação do app OAuth pelo Google.
