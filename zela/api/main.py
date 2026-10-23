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
from zela.integrations.google_calendar_client import GoogleCalendarClient
from zela.integrations.waha_client import WahaClient
from zela.storage.db import conectar
from zela.storage.monitoramento import salvar_leitura as salvar_leitura_sensor
from zela.storage.perfil import obter_perfil

# uvicorn só configura handler/nível pros loggers dele mesmo (uvicorn.*) —
# sem isso, logger.info/logger.warning de qualquer módulo nosso (ex.:
# zela.api.ingestao) é descartado silenciosamente em produção, mesmo
# aparecendo normalmente em testes (caplog força um handler próprio).
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAMINHO_DB = os.environ.get("ZELA_DB_PATH", "zela.db")
ID_IDOSO = "idosa-1"
# Default cobre o uso local (venv + WAHA via docker-compose expondo a porta
# no host); em docker-compose, backend e waha são containers separados e
# "localhost" não alcança o waha — ver ZELA_WAHA_BASE_URL=http://waha:3000
# no .env de produção.
WAHA_BASE_URL = os.environ.get("ZELA_WAHA_BASE_URL", "http://localhost:3000")
WAHA_API_KEY = os.environ.get("ZELA_WAHA_API_KEY")
# "or None" (em vez de só os.environ.get) porque docker-compose define a
# variável como string vazia quando ela não está no .env (em vez de omiti-la
# do ambiente do container) — sem isso, "" vira um token que nenhum cliente
# jamais envia, bloqueando os 3 endpoints com 401 por padrão.
TOKEN_INGESTAO = os.environ.get("ZELA_INGESTAO_TOKEN") or None
# Mesmo racional do "or None" de TOKEN_INGESTAO acima: docker-compose define
# essas 4 variáveis como string vazia quando ausentes do .env, em vez de
# omiti-las do ambiente do container.
GOOGLE_CALENDAR_CLIENT_ID = os.environ.get("ZELA_GOOGLE_CALENDAR_CLIENT_ID") or None
GOOGLE_CALENDAR_CLIENT_SECRET = os.environ.get("ZELA_GOOGLE_CALENDAR_CLIENT_SECRET") or None
GOOGLE_CALENDAR_REFRESH_TOKEN = os.environ.get("ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN") or None
GOOGLE_CALENDAR_CALENDAR_ID = os.environ.get("ZELA_GOOGLE_CALENDAR_CALENDAR_ID") or None

waha_client = WahaClient(base_url=WAHA_BASE_URL, api_key=WAHA_API_KEY)
if all(
    [
        GOOGLE_CALENDAR_CLIENT_ID,
        GOOGLE_CALENDAR_CLIENT_SECRET,
        GOOGLE_CALENDAR_REFRESH_TOKEN,
        GOOGLE_CALENDAR_CALENDAR_ID,
    ]
):
    google_calendar_client = GoogleCalendarClient(
        client_id=GOOGLE_CALENDAR_CLIENT_ID,
        client_secret=GOOGLE_CALENDAR_CLIENT_SECRET,
        refresh_token=GOOGLE_CALENDAR_REFRESH_TOKEN,
        calendar_id=GOOGLE_CALENDAR_CALENDAR_ID,
    )
else:
    google_calendar_client = None
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
    agendador = iniciar_scheduler(
        CAMINHO_DB, ID_IDOSO, waha_client, google_calendar_client=google_calendar_client
    )
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
        processar_risco=_processar_risco, token=TOKEN_INGESTAO,
    )
)
app.include_router(montar_roteador_ingestao(_salvar_leitura, id_idoso=ID_IDOSO, token=TOKEN_INGESTAO))
app.include_router(
    montar_roteador_classificacao(cliente_embedding, _obter_exemplos_com_embedding, token=TOKEN_INGESTAO)
)
