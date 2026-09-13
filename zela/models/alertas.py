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


class Alerta(BaseModel):
    nivel: NivelAlerta
    destinatario: str
    canal: CanalAlerta
    mensagem: str
    status: StatusAlerta = StatusAlerta.ENVIADO
    timestamp: datetime
    simulado: bool = False
