from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class TipoEpisodio(str, Enum):
    SINTOMA = "sintoma"
    PEDIDO_AJUDA = "pedido_ajuda"


class EstadoEpisodio(str, Enum):
    AGUARDANDO = "aguardando"
    CANCELADO_ESTOU_BEM = "cancelado_estou_bem"
    CANCELADO_RECUSA = "cancelado_recusa"
    NOTIFICADO = "notificado"


class TipoNotificacao(str, Enum):
    AVISO = "aviso"
    ADVERTENCIA = "advertencia"


class StatusNotificacao(str, Enum):
    PENDENTE = "pendente"
    ENVIADO = "enviado"
    FALHOU = "falhou"


class EpisodioSintoma(BaseModel):
    id: int
    idoso_id: str
    tipo: TipoEpisodio
    texto: str
    sintomas: list[str]
    iniciado_em: datetime
    prazo_em: datetime
    estado: EstadoEpisodio
    encerrado_em: datetime | None = None


class NotificacaoFamilia(BaseModel):
    id: int
    episodio_id: int
    tipo: TipoNotificacao
    destinatario: str
    telefone: str
    mensagem: str
    tentativas: int
