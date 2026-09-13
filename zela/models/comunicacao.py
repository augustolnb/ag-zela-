from datetime import datetime
from enum import Enum

from pydantic import BaseModel, model_validator


class TipoMensagem(str, Enum):
    TEXTO = "texto"
    AUDIO = "audio"


class MensagemEntrada(BaseModel):
    remetente: str
    tipo: TipoMensagem
    conteudo_bruto: str
    transcricao: str | None = None
    timestamp: datetime

    @model_validator(mode="after")
    def preencher_transcricao_de_texto(self) -> "MensagemEntrada":
        if self.tipo == TipoMensagem.TEXTO and self.transcricao is None:
            self.transcricao = self.conteudo_bruto
        return self
