from datetime import datetime, time
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class TipoCompromisso(str, Enum):
    CONSULTA = "consulta"
    EXAME = "exame"
    OUTRO = "outro"


class StatusConfirmacao(str, Enum):
    CONFIRMADO = "confirmado"
    ATRASADO = "atrasado"
    NAO_CONFIRMADO = "nao_confirmado"


class CanalConfirmacao(str, Enum):
    WHATSAPP = "whatsapp"
    MANUAL = "manual"


class Dosagem(BaseModel):
    quantidade: float = Field(gt=0)
    unidade: str


class Medicamento(BaseModel):
    id: str
    nome: str
    dosagem: Dosagem
    horarios: list[time]
    dias_semana: list[int] = Field(default_factory=lambda: list(range(7)))
    ativo: bool = True

    @field_validator("horarios")
    @classmethod
    def horarios_nao_vazios_e_unicos(cls, v: list[time]) -> list[time]:
        if not v:
            raise ValueError("é necessário ao menos um horário")
        if len(v) != len(set(v)):
            raise ValueError("horários devem ser únicos")
        return v

    @field_validator("dias_semana")
    @classmethod
    def dias_semana_validos(cls, v: list[int]) -> list[int]:
        if any(dia < 0 or dia > 6 for dia in v):
            raise ValueError("dias_semana deve conter valores entre 0 (segunda) e 6 (domingo)")
        return v


class Compromisso(BaseModel):
    id: str
    titulo: str
    data_hora: datetime
    local: str
    tipo: TipoCompromisso

    @field_validator("data_hora")
    @classmethod
    def data_hora_deve_ser_futura(cls, v: datetime) -> datetime:
        if v <= datetime.now():
            raise ValueError("data_hora do compromisso deve ser no futuro")
        return v


class ConfirmacaoMedicacao(BaseModel):
    medicamento_id: str
    horario_previsto: datetime
    horario_confirmado: datetime | None = None
    status: StatusConfirmacao
    canal: CanalConfirmacao
