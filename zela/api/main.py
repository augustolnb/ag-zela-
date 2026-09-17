from contextlib import asynccontextmanager

from fastapi import FastAPI

from zela.api.ingestao import montar_roteador_ingestao
from zela.api.runner import obter_runner_zela, processar_mensagem
from zela.api.scheduler import iniciar_scheduler
from zela.api.webhook import montar_roteador
from zela.integrations.waha_client import WahaClient
from zela.storage.db import conectar
from zela.storage.monitoramento import salvar_leitura as salvar_leitura_sensor
from zela.storage.perfil import obter_perfil

CAMINHO_DB = "zela.db"
ID_IDOSO = "idosa-1"
WAHA_BASE_URL = "http://localhost:3000"

waha_client = WahaClient(base_url=WAHA_BASE_URL)
_runner = obter_runner_zela()


def _obter_telefones_permitidos() -> list[str] | None:
    conexao = conectar(CAMINHO_DB)
    perfil = obter_perfil(conexao, ID_IDOSO)
    if perfil is None:
        return None
    return [perfil.telefone] + [c.telefone for c in perfil.contatos_familiares]


_TELEFONES_PERMITIDOS = _obter_telefones_permitidos()


def _processar(id_idoso: str, texto: str, agora) -> str:
    return processar_mensagem(_runner, id_idoso, texto, agora)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    agendador = iniciar_scheduler(CAMINHO_DB, ID_IDOSO, waha_client)
    try:
        yield
    finally:
        agendador.shutdown()


def _salvar_leitura(leitura, idoso_id: str) -> None:
    conexao = conectar(CAMINHO_DB)
    salvar_leitura_sensor(conexao, leitura, idoso_id)


app = FastAPI(lifespan=ciclo_de_vida)
app.include_router(
    montar_roteador(_processar, waha_client, id_idoso=ID_IDOSO, telefones_permitidos=_TELEFONES_PERMITIDOS)
)
app.include_router(montar_roteador_ingestao(_salvar_leitura, id_idoso=ID_IDOSO))
