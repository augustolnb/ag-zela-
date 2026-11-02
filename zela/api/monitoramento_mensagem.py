import logging
import sqlite3
from datetime import datetime

from zela.embeddings.classificador import classificar_por_similaridade
from zela.embeddings.exemplos_referencia import ExemploReferencia
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.models.monitoramento import StatusMonitoramento
from zela.models.perfil import PerfilIdoso
from zela.storage.alertas import salvar_alerta
from zela.storage.escalonamento import aplicar_escalonamento

logger = logging.getLogger(__name__)


def processar_risco_mensagem(
    conn: sqlite3.Connection,
    idoso_id: str,
    perfil: PerfilIdoso,
    texto: str,
    agora: datetime,
    cliente_embedding,
    exemplos_com_embedding: list[tuple[ExemploReferencia, list[float]]],
    repositorio_vetorial,
) -> None:
    try:
        embedding_mensagem = cliente_embedding.obter_embedding(texto)
        evento = classificar_por_similaridade(embedding_mensagem, exemplos_com_embedding, texto, agora)
        if evento.status == StatusMonitoramento.NORMAL:
            # "Estou bem" continua encerrando uma escalada aberta pelos sensores.
            aplicar_escalonamento(conn, idoso_id, evento, perfil, agora)
        else:
            # Só registra: a similaridade gerava alarme falso até com pergunta sobre
            # remédio. Sintomas reais seguem o fluxo de zela/api/aviso_familia.py.
            salvar_alerta(
                conn,
                Alerta(
                    nivel=NivelAlerta.ATENCAO,
                    destinatario="painel",
                    canal=CanalAlerta.STREAMLIT,
                    mensagem=evento.motivo,
                    timestamp=agora,
                ),
                idoso_id,
            )
        doc_id = f"mensagem:{idoso_id}:{agora.isoformat()}"
        repositorio_vetorial.indexar_documento(
            idoso_id=idoso_id, doc_id=doc_id, texto=texto, embedding=embedding_mensagem, tipo="mensagem"
        )
    except Exception:
        logger.exception("Falha ao processar risco/indexação da mensagem do idoso")
