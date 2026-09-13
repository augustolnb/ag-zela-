from google.adk.agents import Agent

MODELO_PADRAO = "gemini-2.0-flash"


def montar_agente_rotina(model: str = MODELO_PADRAO) -> Agent:
    return Agent(
        name="agente_rotina",
        model=model,
        description="Gerencia lembretes de medicamentos e compromissos do idoso.",
        instruction=(
            "Verifique a agenda de medicamentos do idoso e avise quando houver "
            "lembretes pendentes. Registre confirmações quando o idoso informar "
            "que tomou o medicamento."
        ),
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
