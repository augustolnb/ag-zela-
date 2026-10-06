import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI

from zela.api.classificacao import montar_roteador_classificacao
from zela.api.ingestao import montar_roteador_ingestao
from zela.api.monitoramento_mensagem import processar_risco_mensagem
from zela.api.reindexacao import reindexar_documentos
from zela.api.runner import obter_runner_zela, processar_mensagem
from zela.api.scheduler import iniciar_scheduler
from zela.api.webhook import montar_roteador
from zela.embeddings.client import ClienteEmbeddingGemini
from zela.embeddings.exemplos_referencia import EXEMPLOS_REFERENCIA
from zela.embeddings.vetorial import RepositorioVetorial
from zela.integrations.waha_client import WahaClient
from zela.storage.db import conectar
from zela.storage.monitoramento import salvar_leitura as salvar_leitura_sensor
from zela.storage.perfil import obter_perfil

logger = logging.getLogger(__name__)

CAMINHO_DB = os.environ.get("ZELA_DB_PATH", "zela.db")
ID_IDOSO = "idosa-1"
WAHA_BASE_URL = "http://localhost:3000"

waha_client = WahaClient(base_url=WAHA_BASE_URL)
cliente_embedding = ClienteEmbeddingGemini()
repositorio_vetorial = RepositorioVetorial()
_runner = obter_runner_zela()
_exemplos_com_embedding_cache = None


def _obter_telefones_permitidos() -> list[str] | None:
    conexao = conectar(CAMINHO_DB)
    perfil = obter_perfil(conexao, ID_IDOSO)
    if perfil is None:
        return None
    return [perfil.telefone] + [c.telefone for c in perfil.contatos_familiares]


def _obter_lids_permitidos() -> list[str] | None:
    conexao = conectar(CAMINHO_DB)
    perfil = obter_perfil(conexao, ID_IDOSO)
    if perfil is None or perfil.lid_whatsapp is None:
        return None
    return [perfil.lid_whatsapp]


_TELEFONES_PERMITIDOS = _obter_telefones_permitidos()
_LIDS_PERMITIDOS = _obter_lids_permitidos()


def _processar(id_idoso: str, texto: str, agora) -> str:
    return processar_mensagem(_runner, id_idoso, texto, agora)


def _obter_exemplos_com_embedding():
    global _exemplos_com_embedding_cache
    if _exemplos_com_embedding_cache is None:
        _exemplos_com_embedding_cache = [
            (exemplo, cliente_embedding.obter_embedding(exemplo.texto)) for exemplo in EXEMPLOS_REFERENCIA
        ]
    return _exemplos_com_embedding_cache


def _processar_risco(telefone: str, texto: str, agora: datetime) -> None:
    conexao = conectar(CAMINHO_DB)
    perfil = obter_perfil(conexao, ID_IDOSO)
    if perfil is None or telefone not in (perfil.telefone, perfil.lid_whatsapp):
        return
    try:
        exemplos = _obter_exemplos_com_embedding()
    except Exception:
        logger.exception("Falha ao carregar exemplos de referência para classificação por embedding")
        return
    processar_risco_mensagem(
        conexao, ID_IDOSO, perfil, texto, agora,
        cliente_embedding, exemplos, repositorio_vetorial, waha_client,
    )


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    try:
        reindexar_documentos(conectar(CAMINHO_DB), ID_IDOSO, repositorio_vetorial, cliente_embedding)
    except Exception:
        logger.exception("Falha ao reindexar documentos no boot da API")
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
    montar_roteador(
        _processar, waha_client, id_idoso=ID_IDOSO,
        telefones_permitidos=_TELEFONES_PERMITIDOS, lids_permitidos=_LIDS_PERMITIDOS,
        processar_risco=_processar_risco,
    )
)
app.include_router(montar_roteador_ingestao(_salvar_leitura, id_idoso=ID_IDOSO))
app.include_router(montar_roteador_classificacao(cliente_embedding, _obter_exemplos_com_embedding))
