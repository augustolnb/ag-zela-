import sqlite3
from datetime import datetime, timedelta

from zela.domain.monitoramento import classificar_por_regra
from zela.models.monitoramento import (
    EventoMonitoramento,
    FonteSensor,
    MetodoClassificacao,
    StatusMonitoramento,
    TipoLeitura,
)
from zela.models.monitoramento import LeituraSensor

JANELA_LOOKBACK_HORAS = 48.0

# Prefixo estável do motivo retornado quando não há nenhuma leitura de
# presença na janela de lookback (ver `aplicar_classificacao` abaixo). Usado
# por `zela.api.scheduler` para distinguir esse caso técnico ("sem dados") de
# uma classificação de risco real, sem precisar duplicar o texto completo.
MOTIVO_SEM_DADOS_PREFIXO = "Nenhuma leitura de presença recebida nas últimas"


def salvar_leitura(conn: sqlite3.Connection, leitura: LeituraSensor, idoso_id: str) -> None:
    conn.execute(
        """
        INSERT INTO leitura_sensor (idoso_id, fonte, tipo, valor, unidade, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            idoso_id,
            leitura.fonte.value,
            leitura.tipo.value,
            leitura.valor,
            leitura.unidade,
            leitura.timestamp.isoformat(),
        ),
    )
    conn.commit()


def listar_leituras_recentes(
    conn: sqlite3.Connection, idoso_id: str, desde: datetime
) -> list[LeituraSensor]:
    linhas = conn.execute(
        "SELECT * FROM leitura_sensor WHERE idoso_id = ? AND timestamp >= ? ORDER BY timestamp",
        (idoso_id, desde.isoformat()),
    ).fetchall()
    return [
        LeituraSensor(
            fonte=FonteSensor(linha["fonte"]),
            tipo=TipoLeitura(linha["tipo"]),
            valor=linha["valor"],
            unidade=linha["unidade"],
            timestamp=datetime.fromisoformat(linha["timestamp"]),
        )
        for linha in linhas
    ]


def aplicar_classificacao(
    conn: sqlite3.Connection,
    idoso_id: str,
    agora: datetime,
    janela_horas: float = JANELA_LOOKBACK_HORAS,
) -> EventoMonitoramento:
    desde = agora - timedelta(hours=janela_horas)
    leituras = listar_leituras_recentes(conn, idoso_id, desde)

    tem_leitura_presenca = any(l.tipo == TipoLeitura.PRESENCA for l in leituras)
    if not tem_leitura_presenca:
        return EventoMonitoramento(
            status=StatusMonitoramento.ATENCAO,
            motivo=(
                f"{MOTIVO_SEM_DADOS_PREFIXO} "
                f"{janela_horas:.0f}h — possível falha do sensor ou da conexão"
            ),
            timestamp=agora,
            metodo_classificacao=MetodoClassificacao.REGRA,
        )

    return classificar_por_regra(leituras, agora)
