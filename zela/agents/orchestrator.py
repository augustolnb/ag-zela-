import logging
from datetime import datetime

from google.adk.agents import Agent

from zela.embeddings.client import ClienteEmbeddingGemini
from zela.embeddings.vetorial import RepositorioVetorial
from zela.storage.alertas import listar_alertas
from zela.storage.db import conectar
from zela.storage.monitoramento import aplicar_classificacao
from zela.storage.rotina import aplicar_confirmacao, aplicar_lembretes_pendentes, listar_medicamentos

MODELO_PADRAO = "gemini-2.0-flash"

_CAMINHO_DB = "zela.db"

logger = logging.getLogger(__name__)


def _obter_conexao():
    return conectar(_CAMINHO_DB)


def _obter_cliente_embedding() -> ClienteEmbeddingGemini:
    return ClienteEmbeddingGemini()


def _obter_repositorio_vetorial() -> RepositorioVetorial:
    return RepositorioVetorial()


def consultar_conhecimento(idoso_id: str, pergunta: str) -> list[str]:
    """Busca trechos relevantes (bulas de medicamentos, mensagens passadas do idoso) para responder à pergunta."""
    try:
        embedding_pergunta = _obter_cliente_embedding().obter_embedding(pergunta)
        return _obter_repositorio_vetorial().buscar_similares(idoso_id, embedding_pergunta, k=3)
    except Exception:
        logger.exception("Falha ao consultar conhecimento (embedding ou busca vetorial)")
        return []


def verificar_lembretes_pendentes(idoso_id: str, agora_iso: str) -> list[dict]:
    """Retorna os medicamentos com lembrete pendente para o idoso no horário informado (ISO 8601)."""
    try:
        agora = datetime.fromisoformat(agora_iso)
    except ValueError:
        return [{"erro": f"agora_iso inválido: {agora_iso!r}"}]
    conn = _obter_conexao()
    pendentes = aplicar_lembretes_pendentes(conn, idoso_id, agora)
    return [m.model_dump(mode="json") for m in pendentes]


def confirmar_medicamento(
    idoso_id: str, medicamento_id: str, horario_previsto_iso: str, agora_iso: str
) -> dict:
    """Registra que o idoso confirmou ter tomado um medicamento."""
    try:
        horario_previsto = datetime.fromisoformat(horario_previsto_iso)
        agora = datetime.fromisoformat(agora_iso)
    except ValueError as exc:
        return {"erro": f"data/hora inválida: {exc}"}
    conn = _obter_conexao()
    medicamentos = {m.id: m for m in listar_medicamentos(conn, idoso_id)}
    medicamento = medicamentos.get(medicamento_id)
    if medicamento is None:
        return {"erro": f"medicamento {medicamento_id} não encontrado"}
    confirmacao = aplicar_confirmacao(
        conn,
        medicamento,
        horario_previsto=horario_previsto,
        agora=agora,
    )
    return confirmacao.model_dump(mode="json")


def consultar_status_atual(idoso_id: str, agora_iso: str) -> dict:
    """Retorna o status de monitoramento mais recente do idoso (normal, atenção ou risco) e o motivo.

    O argumento `agora_iso` é validado (para preservar o comportamento de erro
    esperado pelo agente), mas o valor efetivamente usado na classificação é
    sempre `datetime.now()` — esta é uma consulta somente-leitura relevante
    para segurança, e não pode depender de um timestamp potencialmente
    alucinado pelo LLM.
    """
    try:
        datetime.fromisoformat(agora_iso)
    except ValueError:
        return {"erro": f"agora_iso inválido: {agora_iso!r}"}
    conn = _obter_conexao()
    evento = aplicar_classificacao(conn, idoso_id, datetime.now())
    return evento.model_dump(mode="json")


def consultar_historico_alertas(idoso_id: str) -> list[dict]:
    """Retorna os alertas registrados para o idoso, do mais antigo ao mais recente."""
    conn = _obter_conexao()
    alertas = listar_alertas(conn, idoso_id)
    return [a.model_dump(mode="json") for a in alertas]


def montar_agente_rotina(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_rotina",
        model=model,
        description="Gerencia lembretes de medicamentos e compromissos do idoso.",
        instruction=(
            "Verifique a agenda de medicamentos do idoso usando "
            "verificar_lembretes_pendentes, e registre confirmações com "
            "confirmar_medicamento quando o idoso informar que tomou o "
            "medicamento.\n\n"
            "Toda mensagem recebida começa com uma linha de contexto do "
            "sistema no formato "
            "'[contexto do sistema: idoso_id=<id>; agora=<timestamp ISO 8601>]', "
            "seguida do texto real do idoso. Extraia o valor exato de "
            "idoso_id e de agora dessa linha e use-os como os argumentos "
            "idoso_id e agora_iso ao chamar suas ferramentas. Ao confirmar "
            "que um medicamento foi tomado agora (sem outro horário "
            "explícito informado pelo idoso), use esse mesmo valor de "
            "agora também como horario_previsto_iso."
        ),
        tools=[verificar_lembretes_pendentes, confirmar_medicamento],
    )


def montar_agente_monitoramento(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_monitoramento",
        model=model,
        description="Relata o status de saúde/risco do idoso já calculado automaticamente pelo sistema.",
        instruction=(
            "Quando a família perguntar sobre o estado de saúde/segurança do "
            "idoso, use a ferramenta consultar_status_atual para obter a "
            "classificação mais recente (normal, atenção ou risco) e o "
            "motivo. Nunca decida o status você mesmo — sempre consulte a "
            "ferramenta, que reflete um cálculo já feito automaticamente.\n\n"
            "Toda mensagem recebida começa com uma linha de contexto do "
            "sistema no formato "
            "'[contexto do sistema: idoso_id=<id>; agora=<timestamp ISO 8601>]', "
            "seguida do texto real da pergunta. Extraia idoso_id e agora "
            "dessa linha e use-os como os argumentos idoso_id e agora_iso."
        ),
        tools=[consultar_status_atual],
    )


def montar_agente_comunicacao(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_comunicacao",
        model=model,
        description="Conversa com o idoso e a família via WhatsApp e Streamlit.",
        instruction=(
            "Formate lembretes de forma simples e acolhedora para o idoso, e "
            "interprete as respostas recebidas. Quando o idoso ou a família "
            "perguntarem algo que possa estar em uma bula de medicamento ou em "
            "uma mensagem anterior do idoso (ex.: 'para que serve esse "
            "remédio?', 'o que a Vó disse ontem?'), use a ferramenta "
            "consultar_conhecimento para buscar trechos relevantes antes de "
            "responder. Se a ferramenta não retornar nada relevante, diga que "
            "não encontrou essa informação em vez de inventar uma resposta.\n\n"
            "Toda mensagem recebida começa com uma linha de contexto do "
            "sistema no formato "
            "'[contexto do sistema: idoso_id=<id>; agora=<timestamp ISO 8601>]', "
            "seguida do texto real da pergunta. Extraia idoso_id dessa linha e "
            "use-o como o argumento idoso_id ao chamar consultar_conhecimento; "
            "use o texto da pergunta em si (sem a linha de contexto) como o "
            "argumento pergunta."
        ),
        tools=[consultar_conhecimento],
    )


def montar_agente_emergencia(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_emergencia",
        model=model,
        description="Relata alertas e ocorrências de emergência já registrados pelo sistema.",
        instruction=(
            "Quando a família perguntar sobre alertas ou ocorrências "
            "recentes, use a ferramenta consultar_historico_alertas para "
            "obter o histórico já registrado. O escalonamento de risco em "
            "si é decidido automaticamente por um processo separado, não "
            "por você — sua função aqui é relatar o que já foi registrado, "
            "nunca decidir se algo é uma emergência.\n\n"
            "Toda mensagem recebida começa com uma linha de contexto do "
            "sistema no formato "
            "'[contexto do sistema: idoso_id=<id>; agora=<timestamp ISO 8601>]', "
            "seguida do texto real da pergunta. Extraia idoso_id dessa linha "
            "e use-o como o argumento idoso_id."
        ),
        tools=[consultar_historico_alertas],
    )


def montar_orquestrador(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="orquestrador_zela",
        model=model,
        description="Coordena os agentes especializados do Zela+.",
        instruction=(
            "Você é o orquestrador do Zela+. Direcione cada solicitação ao "
            "agente especializado apropriado: rotina/medicação, monitoramento "
            "de saúde/risco, comunicação, ou emergência."
        ),
        sub_agents=[
            montar_agente_rotina(model=model),
            montar_agente_monitoramento(model=model),
            montar_agente_comunicacao(model=model),
            montar_agente_emergencia(model=model),
        ],
    )


root_agent = montar_orquestrador()
