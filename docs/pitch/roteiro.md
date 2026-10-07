# Roteiro do vídeo pitch — Zela+

**Duração máxima: 3 minutos.** Estrutura exigida pelo card: abertura e
contextualização, problema, solução, diferenciais, resultados. Os tempos
abaixo somam 2min50s, deixando ~10s de folga.

Grave a tela (Streamlit + terminal + editor do n8n) com narração ao vivo,
ou grave a narração separadamente e edite por cima — o que for mais fácil
para você. Não precisa aparecer no vídeo; o foco é a tela.

---

## Cena 1 — Abertura e contextualização (0:00–0:25)

**Fala sugerida:**
> "Meu nome é Lucas, e este é o Zela+, um agente de IA que criei pensando
> na minha avó, que mora sozinha. Este é o trabalho final da pós em
> Agentes de IA."

**Tela:** slide de título ou o `README.md` do repositório aberto no
GitHub, mostrando o nome do projeto.

---

## Cena 2 — O problema (0:25–0:55)

**Fala sugerida:**
> "Idosos que moram sozinhos enfrentam três riscos: esquecem medicamentos
> e compromissos, uma queda ou mal-estar pode passar despercebido por
> horas, e a família fica sem visibilidade do dia a dia sem precisar
> ligar toda hora."

**Tela:** pode ficar só em slide/texto, ou cortar rapidamente para o
diagrama de arquitetura do `RELATORIO.md` (seção 2) enquanto fala.

---

## Cena 3 — A solução (0:55–1:50)

**Fala sugerida:**
> "O Zela+ resolve isso com 5 agentes de IA orquestrados pelo Google ADK:
> um cuida da rotina de medicação, outro monitora sinais de risco vindos
> de um smartwatch e de um sensor de presença ESP32, um conversa com o
> idoso e a família por WhatsApp, e um cuida dos alertas de emergência.
> Por exemplo, quando o idoso manda uma mensagem como 'caí no banheiro e
> não consigo levantar', o sistema classifica essa mensagem por
> similaridade de embeddings e aciona a escada de alerta."

**Tela (em ordem):**
1. Painel Streamlit — seção de status (2-3s).
2. Painel Streamlit — seção de medicação/formulário de cadastro (3-4s).
3. Editor do n8n com o workflow importado, disparando o webhook de teste
   com a mensagem de queda e mostrando a resposta roteada para
   "alertar_familia" (15-20s — este é o momento mais importante da
   demonstração técnica).

---

## Cena 4 — Diferenciais (1:50–2:20)

**Fala sugerida:**
> "O diferencial mais importante do projeto: a decisão de disparar um
> alerta real de emergência nunca é tomada por um LLM. É uma máquina de
> estados determinística, testada exaustivamente — os agentes de IA só
> alimentam essa máquina com eventos, nunca decidem sozinhos. Isso torna o
> sistema auditável e seguro para um caso de uso onde um erro tem peso
> real."

**Tela:** pode voltar ao diagrama de arquitetura, ou mostrar rapidamente o
terminal rodando `pytest -v` com a suíte passando.

---

## Cena 5 — Resultados (2:20–2:50)

**Fala sugerida:**
> "O projeto tem 202 testes automatizados, foi construído em 6 fases
> incrementais, cada uma testada e integrada separadamente, e está
> documentado no GitHub com instruções completas de instalação e
> execução. Obrigado!"

**Tela:** terminal com `pytest -v` mostrando o resumo final (`202 passed`),
ou a tela do GitHub do repositório.

---

## Checklist antes de gravar

- [ ] Backend rodando (`uvicorn zela.api.main:app --reload`)
- [ ] Streamlit rodando (`streamlit run zela/streamlit_app/app.py`) com
      pelo menos um medicamento e um alerta já cadastrados (para a tela
      não aparecer vazia)
- [ ] n8n rodando com o workflow `docs/n8n/zela-classificacao-mensagem.json`
      já importado e ativo
- [ ] Mensagem de teste pronta para disparar no n8n (ex.: "caí no banheiro
      e não consigo levantar")
- [ ] `pytest -v` já rodado uma vez (para não gravar o tempo de execução
      real, ~20s, ao vivo — ou tudo bem se quiser mostrar ao vivo)

## Depois de gravar

Salve o arquivo final como `docs/pitch/zela-pitch.mp4` neste repositório.
