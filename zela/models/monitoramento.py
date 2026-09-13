from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class FonteSensor(str, Enum):
    SMARTWATCH = "smartwatch"
    ESP32 = "esp32"


class TipoLeitura(str, Enum):
    FREQUENCIA_CARDIACA = "frequencia_cardiaca"
    PASSOS = "passos"
    SONO = "sono"
    PRESENCA = "presenca"


class StatusMonitoramento(str, Enum):
    NORMAL = "normal"
    ATENCAO = "atencao"
    RISCO = "risco"


class MetodoClassificacao(str, Enum):
    REGRA = "regra"
    EMBEDDING = "embedding"


FAIXAS_PLAUSIVEIS: dict[TipoLeitura, tuple[float, float]] = {
    TipoLeitura.FREQUENCIA_CARDIACA: (30, 220),
    TipoLeitura.PASSOS: (0, 60000),
    TipoLeitura.SONO: (0, 24),
    TipoLeitura.PRESENCA: (0, 1),
}


class LeituraSensor(BaseModel):
    fonte: FonteSensor
    tipo: TipoLeitura
    valor: float
    unidade: str
    timestamp: datetime
    plausivel: bool = True

    @model_validator(mode="after")
    def calcular_plausibilidade(self) -> "LeituraSensor":
        minimo, maximo = FAIXAS_PLAUSIVEIS[self.tipo]
        self.plausivel = minimo <= self.valor <= maximo
        return self


class EventoMonitoramento(BaseModel):
    status: StatusMonitoramento
    motivo: str
    leituras_relacionadas: list[LeituraSensor] = Field(default_factory=list)
    timestamp: datetime
    metodo_classificacao: MetodoClassificacao
