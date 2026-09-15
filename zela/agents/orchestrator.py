from datetime import datetime

from google.adk.agents import Agent

from zela.storage.db import conectar
from zela.storage.rotina import aplicar_confirmacao, aplicar_lembretes_pendentes, listar_medicamentos

MODELO_PADRAO = "gemini-2.0-flash"

_CAMINHO_DB = "zela.db"


def _obter_conexao():
    return conectar(_CAMINHO_DB)


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
        description="Analisa leituras de sensores e classifica o status de risco do idoso.",
        instruction=(
            "Avalie as leituras de sensores recebidas e classifique o status como "
            "normal, atenção ou risco, explicando o motivo."
        ),
    )


def montar_agente_comunicacao(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_comunicacao",
        model=model,
        description="Conversa com o idoso e a família via WhatsApp e Streamlit.",
        instruction=(
            "Formate lembretes de forma simples e acolhedora para o idoso, e "
            "interprete as respostas recebidas."
        ),
    )


def montar_agente_emergencia(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_emergencia",
        model=model,
        description="Decide o escalonamento de alertas em situações de risco.",
        instruction=(
            "Quando o agente de monitoramento indicar risco, decida a próxima "
            "ação de escalonamento seguindo a política de camadas: contato com "
            "o idoso, depois família, depois simulação de contato de emergência."
        ),
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
