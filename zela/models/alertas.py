from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class NivelAlerta(str, Enum):
    INFO = "info"
    ATENCAO = "atencao"
    CRITICO = "critico"


class CanalAlerta(str, Enum):
    WHATSAPP = "whatsapp"
    STREAMLIT = "streamlit"


class StatusAlerta(str, Enum):
    ENVIADO = "enviado"
    CONFIRMADO = "confirmado"
    FALHOU = "falhou"


class Alerta(BaseModel):
    nivel: NivelAlerta
    destinatario: str
    canal: CanalAlerta
    mensagem: str
    status: StatusAlerta = StatusAlerta.ENVIADO
    timestamp: datetime
    simulado: bool = False
    # Destino explícito, definido por quem cria o alerta. Resolver pelo nome
    # mandava o aviso de um familiar homônimo para o WhatsApp do idoso.
    # Não são persistidos: alertas lidos do banco ficam com os padrões.
    telefone: str | None = None
    para_idoso: bool = False
