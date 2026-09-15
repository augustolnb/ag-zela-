from contextlib import asynccontextmanager

from fastapi import FastAPI

from zela.api.runner import obter_runner_zela, processar_mensagem
from zela.api.scheduler import iniciar_scheduler
from zela.api.webhook import montar_roteador
from zela.integrations.waha_client import WahaClient
from zela.storage.db import conectar
from zela.storage.perfil import obter_perfil

CAMINHO_DB = "zela.db"
ID_IDOSO = "idosa-1"
WAHA_BASE_URL = "http://localhost:3000"

waha_client = WahaClient(base_url=WAHA_BASE_URL)
_runner = obter_runner_zela()


def _obter_telefone_idoso() -> str | None:
    conexao = conectar(CAMINHO_DB)
    perfil = obter_perfil(conexao, ID_IDOSO)
    return perfil.telefone if perfil is not None else None


_TELEFONE_IDOSO = _obter_telefone_idoso()


def _processar(id_idoso: str, texto: str, agora) -> str:
    return processar_mensagem(_runner, id_idoso, texto, agora)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    agendador = iniciar_scheduler(CAMINHO_DB, ID_IDOSO, waha_client)
    try:
        yield
    finally:
        agendador.shutdown()


app = FastAPI(lifespan=ciclo_de_vida)
app.include_router(
    montar_roteador(_processar, waha_client, id_idoso=ID_IDOSO, telefone_idoso=_TELEFONE_IDOSO)
)
