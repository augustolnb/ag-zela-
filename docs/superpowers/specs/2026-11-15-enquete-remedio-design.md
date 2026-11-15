# Lembrete de remédio com enquete no WhatsApp: design

Status: aguardando aprovação.

## Por que isto existe

O usuário pediu um botão "tomei o remédio" no WhatsApp para facilitar a vida
do idoso, que hoje precisa digitar "tomei" para a IA registrar a dose.

O WhatsApp só libera botões na API oficial da Meta. O Zela+ usa o WAHA
(WhatsApp Web), e a documentação dele diz que os botões não funcionam
("DEPRECATED - Buttons do not work at the moment!"). Enquetes funcionam no
motor WEBJS da produção. O idoso toca numa opção e o WAHA avisa o backend com
o evento `poll.vote`.

**Teste em produção (15/11/2026).** Uma enquete enviada ao número do perfil
de teste foi votada em "✅ Tomei". O voto chegou legível, como `poll.vote`,
com `selectedOptions: ['✅ Tomei']` e o mesmo identificador da enquete
enviada. Não houve `poll.vote.failed`. A configuração do WAHA foi revertida
depois do teste.

## Comportamento

### Envio do lembrete

O lembrete de remédio do scheduler passa a sair como enquete de escolha
única:

> **Hora de tomar dapagliflozina (1.0 comprimido). Já tomou?**
> ◯ ✅ Tomei
> ◯ ⏰ Ainda não

- O pedido da enquete ao WAHA tem até 40 caracteres por opção. A pergunta
  segue o texto atual do lembrete, sem o "Responda 'tomei'".
- **Se o envio da enquete falhar** (exceção do WAHA), o scheduler manda o
  texto atual (`formatar_lembrete`) como antes. O idoso nunca fica sem
  lembrete.
- A notificação no Gmail da pulseira continua igual e é independente.
- Cada enquete enviada é guardada no banco, com o remédio e o horário
  previsto, para relacionar o voto ao lembrete.

### Voto

| Voto | O que o Zela+ faz |
|---|---|
| "✅ Tomei" | Registra a confirmação do remédio naquele horário previsto, igual à confirmação por texto (`aplicar_confirmacao`; vira ATRASADO depois de 30 min). Responde: "Anotado! ✅ Dose de dapagliflozina registrada." |
| "⏰ Ainda não" | Não registra nada. Responde: "Tudo bem! Quando tomar, é só tocar em ✅ Tomei ou me escrever 'tomei'." |
| Voto removido (lista vazia) | Ignorado. |

- **Sem a IA:** o voto é tratado por código, sem passar pelo LLM.
- **Idempotente:** se aquele remédio naquele horário já tem confirmação, um
  novo voto não registra outra nem responde de novo.
- **Escrever "tomei" continua funcionando**, pelo agente, como hoje.
- Só votos do idoso valem. O `vote.from` passa pela mesma lista de
  permitidos (telefone ou LID) do webhook. Votos em enquetes desconhecidas
  são ignorados.
- `poll.vote.failed` (voto que o WAHA não conseguiu ler) gera um aviso no
  log. O lembrete segue como não confirmado, e o texto continua como reserva.

### Configuração do WAHA

O webhook da sessão passa de `["message"]` para
`["message", "poll.vote", "poll.vote.failed"]`, no mesmo endereço e com o
mesmo `X-Api-Key`. É um passo de deploy feito uma única vez, com cópia de
segurança da configuração (como no teste) e documentado no `vps.md`.

## Não objetivos

- Não reenviar o lembrete depois de "Ainda não". Hoje não existe reenvio
  para o texto também.
- Não desfazer a confirmação se o idoso trocar o voto para "Ainda não".
- Não usar enquetes para os avisos à família, para o "ESTOU BEM" do episódio
  de sintoma nem para compromissos.
- Não trocar o WAHA pela API oficial da Meta.

## Decisões técnicas (escolhas do Claude, para revisar)

1. **Chave da enquete:** a resposta do `sendPoll` e o `poll.id` do voto
   podem vir com prefixos diferentes (`true_…@lid_…`). O banco guarda só a
   parte depois do último `_`, o identificador da mensagem. Ela coincidiu no
   teste (`…47657A643465`). Se a resposta vier como objeto, usa
   `id._serialized`.
2. **Opções reconhecidas pelo texto exato** (`✅ Tomei` e `⏰ Ainda não`),
   definidas como constantes.
3. **Tabela nova** `enquete_lembrete (chave TEXT PRIMARY KEY, idoso_id,
   medicamento_id, horario_previsto, enviada_em)`, criada com
   `CREATE TABLE IF NOT EXISTS`, como as outras.
4. **Webhook:** um evento `poll.vote` é desviado antes da extração de texto
   para um callback novo, `processar_voto`, injetado em `montar_roteador`,
   no mesmo padrão de `processar_emergencia`. Falhas no callback viram log,
   não erro 500, para o WAHA não repetir o evento.
5. **Resposta ao voto** vai para o JID de quem votou (`vote.from`), como na
   resposta a mensagens.

## Riscos

- O WAHA avisa que pode falhar ao decifrar votos (`poll.vote.failed`). A
  mitigação é o texto continuar valendo e o evento aparecer no log.
- Uma mudança futura no formato do `poll.id` quebraria a relação com o
  lembrete. O teste de integração pela chave normalizada cobre o formato
  observado em produção.
