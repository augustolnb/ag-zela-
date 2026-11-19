# Aviso à família em 60 s — plano de implementação

> Execução: tarefas em ordem, TDD, sessão única (o usuário autorizou prosseguir).

**Objetivo:** relato de sintoma grave sem resposta em 60 s notifica todos os familiares, sem depender do Gemini.

**Arquitetura:** classificador determinístico antes do LLM; episódios e fila de notificações persistidos no SQLite; job de 10 s envia, reenvia e retoma após reinício.

**Stack:** Python, FastAPI, APScheduler, SQLite, WAHA, pytest.

**Spec:** `docs/superpowers/specs/2026-11-02-aviso-familia-60s-design.md`

## Restrições globais
Prazo 60 s; job 10 s; reenvio 30 s; 5 tentativas; janela móvel de 7 dias; horários em UTC-3; commits em PT-BR.

## Foco de revisão (cada item tem teste)
1. "Não chame minha filha" não pode virar pedido de ajuda.
2. "Não estou bem" e "estou bem mal" não cancelam.
3. Falha ao confirmar ao paciente não cancela o episódio.
4. Corrida entre job e webhook não duplica envio.
5. Conta com LID recebe pelo `chatId` resolvido.

## Tarefas
1. **Entrega:** `WahaClient.resolver_chat_id`, `StatusAlerta.FALHOU`, status real em `despachar_alertas` e `_enviar_aviso`. Testes: `test_integrations_waha_client.py`, `test_api_scheduler.py`.
2. **Detecção:** `zela/domain/sintomas.py`, `classificar_mensagem(texto) -> ClassificacaoMensagem`. Testes: `test_domain_sintomas.py`.
3. **Estado:** `zela/models/episodio.py`, tabelas `episodio_sintoma` e `notificacao_familia`, `zela/storage/episodios.py`. Testes pelo serviço.
4. **Serviço:** `zela/api/aviso_familia.py`: `triar_mensagem`, `processar_episodios`, `enviar_notificacoes_pendentes`. Testes: `test_api_aviso_familia.py`.
5. **Integração:** parâmetro `processar_emergencia` no webhook, antes do LLM; job de 10 s; ligação em `main.py`; README. Testes: `test_api_webhook.py`, `test_api_scheduler.py`.
6. **Verificação:** suíte completa; validação na VPS após autorização de deploy.
