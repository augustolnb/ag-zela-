# Aviso à família em 60 s após relato de sintomas — design

Status: aguardando aprovação.

## Por que isto existe

Em um teste real, o usuário relatou coração acelerado e tontura e pediu para
chamar um familiar. O bot pediu confirmação e nada mais aconteceu. Quem está
passando mal pode não conseguir responder, então a falta de resposta precisa
levar a uma ação, nunca à espera indefinida.

Uma falha aqui é mais grave que um aviso desnecessário: na dúvida, o sistema
avisa a família.

## Comportamento

### Definido pelo usuário

1. Depois de um relato de sintomas, o sistema pode pedir confirmação e esperar
   cerca de 60 s.
2. Sem resposta, **todos** os familiares cadastrados do paciente são notificados.
3. Se a pessoa pedir explicitamente para não avisar ninguém, o sistema obedece.
4. Se esse comportamento se repetir em 1 semana, os familiares recebem uma
   mensagem de advertência explicando a situação e o motivo.
5. "Estou bem" só conta para a advertência quando vem depois de um relato de
   sintomas.

### Confirmado na conversa, a partir de proposta do Claude

- A notificação é por WhatsApp. O sistema não faz ligações.
- "Estou bem" cancela o aviso.
- Falha de entrega é registrada e tentada de novo, sem silêncio.

### Decisões do Claude, para revisão

- **Início da contagem:** um relato de sintoma grave inicia os 60 s, mesmo sem
  pedido de ajuda.
- **Pedido explícito de ajuda:** "chame minha filha", "preciso de ajuda" e
  frases parecidas notificam na hora, sem espera, com ou sem sintomas.
- **Repetição:** a advertência sai na 2ª recusa em uma janela móvel de 7 dias e
  de novo a cada recusa seguinte dentro dessa janela.
- **O que conta como recusa:** só o cancelamento dentro dos 60 s de um episódio.
  "Não avise ninguém" sem episódio aberto não conta.
- **Novo relato após recusa:** abre outro episódio com outros 60 s. Novos
  sintomas durante um episódio aberto não reiniciam o prazo.
- **Mensagem ambígua:** só cancela se for claramente "estou bem" ou recusa, sem
  sintoma ou negação junto. "Estou bem mal" e "não estou bem" não cancelam.
- **Resposta depois do prazo:** não desfaz o aviso. O bot informa que a família
  já foi avisada.
- **Orientação ao paciente:** a mensagem de confirmação inclui o SAMU (192). O
  bot não dá diagnóstico.
- **Remetente:** só mensagens do próprio paciente (telefone ou LID) abrem ou
  cancelam episódios. Mensagens de familiares seguem o fluxo atual.

### Mensagens (texto final pode ser ajustado na implementação)

- **Ao paciente:** "Recebi sua mensagem. Você está bem? Vou avisar sua família
  em 60 segundos. Para cancelar, responda ESTOU BEM ou NÃO AVISE. Em emergência,
  ligue 192."
- **À família:** "Atenção: {nome} relatou {sintomas} às {hora} e não respondeu à
  confirmação. Mensagem original: \"{texto}\". Por favor, entre em contato."
- **Pedido de ajuda:** igual ao aviso à família, dizendo que {nome} pediu ajuda.
- **Advertência:** "Advertência: {nome} relatou sintomas e cancelou o aviso à
  família {n} vezes nos últimos 7 dias: {data, hora, sintomas e tipo de
  cancelamento}. Este aviso existe porque cancelamentos repetidos podem esconder
  um problema de saúde. Vale conversar com {nome}."

## Causas encontradas no sistema atual

1. **Entrega à família quebrada.** `_telefone_por_nome` envia para
   `<telefone>@c.us`. Em conta com LID, o WAHA responde 500 `No LID for user`
   (visto em produção em 02/11/2026, 12:08 e 12:23). `check-exists` do WAHA
   devolve o `chatId` correto a partir do telefone.
2. **Status falso.** `despachar_alertas` e `_enviar_aviso` salvam o alerta como
   `enviado` antes do envio. No laço, uma falha também impede os contatos seguintes.
3. **Aviso repetido.** Em `_enviar_aviso`, a exceção impede a marcação em
   `_avisos_ja_enviados`, e o aviso é gravado de novo a cada 15 min.
4. **Risco depende da IA.** `webhook.py` chama o LLM e envia a resposta antes de
   avaliar o risco. Se o Gemini demorar ou falhar, o risco atrasa ou nem roda.
5. **Prazo longo.** A escada tem janela de 10 min e checagem a cada 15 min. Ela
   também não reage a um sintoma novo com escalonamento já aberto.
6. **Agente sem ação.** O LLM não tem como avisar a família, só responder texto.

## Arquitetura

Tudo fica em código determinístico, sem depender do Gemini.

### Detecção — `zela/domain/sintomas.py` (novo)

Função pura que classifica o texto como `PEDIDO_AJUDA`, `SINTOMA_GRAVE`,
`CANCELAMENTO_ESTOU_BEM`, `CANCELAMENTO_RECUSA` ou `NENHUM`. Normaliza caixa e
acentos e usa listas de termos em português. Lista inicial de sintomas: coração
acelerado, palpitação, tontura, desmaio, dor no peito, falta de ar, formigamento,
fala enrolada, queda/caí, sangramento, confusão, muita dor. Falso positivo é
aceitável. Negações como "não estou com tontura" não abrem episódio.

### Estado — tabela `episodio_sintoma` (nova)

`id, idoso_id, tipo, texto, sintomas, iniciado_em, prazo_em, estado, encerrado_em`.
Estados: `AGUARDANDO`, `CANCELADO_ESTOU_BEM`, `CANCELADO_RECUSA`, `NOTIFICADO`.
Migração idempotente, como em `zela/storage/db.py`. O prazo fica no banco para
sobreviver a reinícios. Há no máximo um episódio `AGUARDANDO` por paciente.

### Fluxo

1. O webhook classifica a mensagem **antes** do LLM.
2. Sintoma grave com o paciente sem episódio aberto: grava o episódio, confirma ao
   paciente e não chama o LLM para essa mensagem.
3. Pedido de ajuda: notifica já e encerra o episódio aberto, se houver.
4. Cancelamento com episódio aberto: encerra, confirma e aplica a regra dos 7 dias.
5. Qualquer outro caso: segue o fluxo atual, sem cancelar o episódio aberto.
6. Um novo job do APScheduler roda a cada 10 s, notifica episódios vencidos e
   retoma os que venceram durante um reinício. Tolerância: de 60 a cerca de 70 s.

Se o envio da confirmação ao paciente falhar, o episódio continua e a família é
avisada no prazo.

### Entrega — `WahaClient`

- Novo método resolve telefone para `chatId` com `check-exists`, com cache em
  memória. Se a consulta falhar, tenta o formato atual.
- `Alerta` passa a ser gravado com o resultado real: `enviado` ou `falhou`. Isso
  corrige o aviso repetido da causa 3 para `_enviar_aviso` e `despachar_alertas`.
- Cada familiar é tratado de forma independente. A falha de um não bloqueia os outros.
- Falhas de notificação são reenviadas pelo job a cada 30 s, até 5 tentativas, só
  para quem falhou. Esgotadas as tentativas, grava log de erro e, se nenhum familiar
  recebeu, avisa o paciente para ligar 192.
- Não há envio duplicado a quem já recebeu.

## Fora do escopo

- Ligações telefônicas.
- Mudar a escada existente de sensores e os alertas por similaridade (como a
  classificação de "esqueci o remédio"). A entrega corrigida também vale para eles.
- Permitir que a família confirme que viu o aviso.
- Detecção por IA. Pode entrar depois como reforço, nunca como único caminho.
- Vários pacientes: o projeto segue com `idosa-1`.

## Não pode acontecer

- Gemini fora do ar impedir o aviso.
- Reinício do backend perder um episódio aberto.
- Alerta aparecer como `enviado` sem ter sido entregue.
- Um familiar não receber porque outro falhou.
- O sistema avisar a família depois de um cancelamento válido dentro do prazo.

## Testes (TDD)

- Domínio: cada categoria, negações, ambiguidades e acentos, incluindo a frase
  real do teste (coração acelerado e tontura).
- Armazenamento: migração, episódio único aberto, contagem móvel nos limites de
  7 dias.
- Webhook: sintoma confirma sem chamar LLM; LLM com exceção não afeta o episódio;
  remetente de familiar não cancela.
- Job: 59 s não notifica, 60 s notifica; episódio vencido durante reinício notifica;
  não duplica.
- Entrega: falha de um familiar não afeta os outros; status real; reenvio limitado;
  `No LID for user` resolvido com o `chatId`.
- Advertência: 1ª recusa não envia, 2ª envia; "estou bem" sem episódio não conta;
  recusa de 8 dias atrás não conta.
- Validação na VPS com o perfil de teste: frase real, espera de 60 s sem responder,
  cancelamento e duas recusas seguidas.

## Implementação

Depende de `scheduler.py` do PR #52. Seguir o fluxo do projeto: issue, branch,
TDD, suíte completa, commit em PT-BR, PR, squash, deploy e verificação. A branch
parte de `main` depois do merge do PR #52.

Ficam a critério de quem implementa: nomes internos, lista final de termos e
texto das mensagens, respeitando as regras acima.
