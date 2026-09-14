from datetime import date

from pydantic import BaseModel, Field

E164_PATTERN = r"^\+[1-9]\d{6,14}$"


class ContatoFamiliar(BaseModel):
    nome: str
    telefone: str = Field(pattern=E164_PATTERN)


class PerfilIdoso(BaseModel):
    nome: str
    telefone: str = Field(pattern=E164_PATTERN)
    data_nascimento: date
    contatos_familiares: list[ContatoFamiliar] = Field(min_length=1)
    condicoes_medicas: list[str] = Field(default_factory=list)
