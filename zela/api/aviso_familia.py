"""Aviso à família após relato de sintomas (spec 2026-11-02-aviso-familia-60s)."""
import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from zela.domain.sintomas import CategoriaMensagem, classificar_mensagem
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta, StatusAlerta
from zela.models.episodio import (
    EpisodioSintoma,
    EstadoEpisodio,
    StatusNotificacao,
    TipoEpisodio,
    TipoNotificacao,
)
from zela.models.perfil import PerfilIdoso
from zela.storage.alertas import salvar_alerta
from zela.storage.db import conectar
from zela.storage.episodios import (
    abrir_episodio,
    acrescentar_relato,
    atualizar_notificacao,
    encerrar_episodio,
    enfileirar_notificacao,
    houve_notificacao_desde,
    listar_cancelados_desde,
    listar_notificacoes_devidas,
    listar_vencidos,
    marcar_paciente_orientado,
    ninguem_recebeu_aviso,
    obter_episodio_aberto,
)
from zela.storage.perfil import obter_perfil

logger = logging.getLogger(__name__)

PRAZO_CONFIRMACAO = timedelta(seconds=60)
INTERVALO_REENVIO = timedelta(seconds=30)
MAX_TENTATIVAS = 5
JANELA_ADVERTENCIA = timedelta(days=7)
# Até quando um "estou bem" tardio recebe resposta sobre o aviso já enviado, em
# vez de seguir para o LLM como mensagem comum.
JANELA_RESPOSTA_TARDIA = timedelta(minutes=30)

# Mesmo fuso fixo do firmware (UTC-3): o container roda em UTC, e a família
# precisa ler o horário local.
_FUSO_BRASILIA = timezone(timedelta(hours=-3))

# O webhook envia na hora e o job a cada 10 s, ambos no mesmo processo: sem o
# lock, os dois podem enviar a mesma notificação pendente.
_lock_envio = threading.Lock()


def _no_fuso_local(momento: datetime) -> datetime:
    return momento.astimezone(_FUSO_BRASILIA)


def _formatar_hora(momento: datetime) -> str:
    return _no_fuso_local(momento).strftime("%H:%M")


def _descrever_sintomas(sintomas: list[str]) -> str:
    return ", ".join(sintomas) if sintomas else "sintomas"


def _enfileirar_para_familia(
    conn: sqlite3.Connection, perfil: PerfilIdoso, episodio_id: int, tipo: TipoNotificacao, mensagem: str, agora: datetime
) -> None:
    for contato in perfil.contatos_familiares:
        enfileirar_notificacao(conn, episodio_id, tipo, contato.nome, contato.telefone, mensagem, agora)


def _mensagem_sem_resposta(perfil: PerfilIdoso, episodio: EpisodioSintoma) -> str:
    return (
        f"Atenção: {perfil.nome} relatou {_descrever_sintomas(episodio.sintomas)} às "
        f"{_formatar_hora(episodio.iniciado_em)} e não respondeu à confirmação. "
        f'Mensagem original: "{episodio.texto}". Por favor, entre em contato.'
    )


def _mensagem_pedido_ajuda(perfil: PerfilIdoso, texto: str, agora: datetime) -> str:
    return (
        f"Atenção: {perfil.nome} pediu ajuda às {_formatar_hora(agora)}. "
        f'Mensagem original: "{texto}". Por favor, entre em contato.'
    )


def _mensagem_advertencia(perfil: PerfilIdoso, cancelados: list[EpisodioSintoma]) -> str:
    linhas = []
    for episodio in cancelados:
        forma = "disse estar bem" if episodio.estado == EstadoEpisodio.CANCELADO_ESTOU_BEM else "pediu para não avisar"
        quando = _no_fuso_local(episodio.iniciado_em).strftime("%d/%m às %H:%M")
        linhas.append(f"- {quando}: {_descrever_sintomas(episodio.sintomas)} ({forma})")
    return (
        f"Advertência: {perfil.nome} relatou sintomas e cancelou o aviso à família "
        f"{len(cancelados)} vezes nos últimos 7 dias:\n" + "\n".join(linhas) + "\n"
        f"Este aviso existe porque cancelamentos repetidos podem esconder um problema de saúde. "
        f"Vale conversar com {perfil.nome}."
    )


def _tratar_pedido_ajuda(conn, idoso_id, perfil, texto, sintomas, aberto, agora, waha_client) -> str:
    with conn:
        if aberto is not None:
            encerrar_episodio(conn, aberto.id, EstadoEpisodio.NOTIFICADO, agora)
        episodio_id = abrir_episodio(
            conn, idoso_id, TipoEpisodio.PEDIDO_AJUDA, texto, sintomas, agora, agora,
            estado=EstadoEpisodio.NOTIFICADO, encerrado_em=agora,
        )
        _enfileirar_para_familia(
            conn, perfil, episodio_id, TipoNotificacao.AVISO, _mensagem_pedido_ajuda(perfil, texto, agora), agora
        )
    enviar_notificacoes_pendentes(conn, perfil, idoso_id, waha_client, agora)
    return "Estou avisando sua família agora. Em emergência, ligue 192."


def _tratar_sintoma(conn, idoso_id, texto, sintomas, aberto, agora) -> str:
    with conn:
        if aberto is not None:
            acrescentar_relato(conn, aberto, texto, sintomas)
            return "Recebi. Sua família será avisada em instantes, a menos que você responda ESTOU BEM ou NÃO AVISE. Em emergência, ligue 192."
        abrir_episodio(conn, idoso_id, TipoEpisodio.SINTOMA, texto, sintomas, agora, agora + PRAZO_CONFIRMACAO)
    return (
        "Recebi sua mensagem. Você está bem? Vou avisar sua família em 60 segundos. "
        "Para cancelar, responda ESTOU BEM ou NÃO AVISE. Em emergência, ligue 192."
    )


def _tratar_cancelamento(conn, idoso_id, perfil, estado, aberto, agora, waha_client) -> str | None:
    if aberto is None or agora >= aberto.prazo_em:
        if aberto is not None or houve_notificacao_desde(conn, idoso_id, agora - JANELA_RESPOSTA_TARDIA):
            return "O prazo já terminou e sua família já está sendo avisada. Que bom que você está bem."
        return None

    with conn:
        if not encerrar_episodio(conn, aberto.id, estado, agora):
            return "O prazo já terminou e sua família já está sendo avisada."
        cancelados = listar_cancelados_desde(conn, idoso_id, agora - JANELA_ADVERTENCIA)
        repetiu = len(cancelados) >= 2
        if repetiu:
            _enfileirar_para_familia(
                conn, perfil, aberto.id, TipoNotificacao.ADVERTENCIA, _mensagem_advertencia(perfil, cancelados), agora
            )
    if repetiu:
        enviar_notificacoes_pendentes(conn, perfil, idoso_id, waha_client, agora)
        return (
            f"Certo, não vou avisar sobre este episódio. Como isso já aconteceu {len(cancelados)} vezes em 7 dias, "
            "sua família recebeu uma advertência. Se piorar, ligue 192."
        )
    return "Certo, não vou avisar sua família agora. Se piorar, me avise ou ligue 192."


def triar_mensagem(
    conn: sqlite3.Connection, idoso_id: str, perfil: PerfilIdoso, texto: str, agora: datetime, waha_client
) -> str | None:
    """Devolve a resposta ao paciente, ou None se a mensagem deve seguir o fluxo normal."""
    classificacao = classificar_mensagem(texto)
    categoria = classificacao.categoria
    if categoria == CategoriaMensagem.NENHUM:
        return None

    aberto = obter_episodio_aberto(conn, idoso_id)
    sintomas = list(classificacao.sintomas)
    if categoria == CategoriaMensagem.PEDIDO_AJUDA:
        return _tratar_pedido_ajuda(conn, idoso_id, perfil, texto, sintomas, aberto, agora, waha_client)
    if categoria == CategoriaMensagem.SINTOMA_GRAVE:
        return _tratar_sintoma(conn, idoso_id, texto, sintomas, aberto, agora)
    estado = (
        EstadoEpisodio.CANCELADO_ESTOU_BEM
        if categoria == CategoriaMensagem.CANCELAMENTO_ESTOU_BEM
        else EstadoEpisodio.CANCELADO_RECUSA
    )
    return _tratar_cancelamento(conn, idoso_id, perfil, estado, aberto, agora, waha_client)


def _registrar_alerta(conn, notificacao, status: StatusAlerta, idoso_id: str, agora: datetime) -> None:
    salvar_alerta(
        conn,
        Alerta(
            nivel=NivelAlerta.CRITICO if notificacao.tipo == TipoNotificacao.AVISO else NivelAlerta.ATENCAO,
            destinatario=notificacao.destinatario,
            canal=CanalAlerta.WHATSAPP,
            mensagem=notificacao.mensagem,
            status=status,
            timestamp=agora,
        ),
        idoso_id,
    )


def _orientar_paciente_se_ninguem_recebeu(conn, perfil, episodio_id: int, waha_client) -> None:
    with conn:
        if not ninguem_recebeu_aviso(conn, episodio_id) or not marcar_paciente_orientado(conn, episodio_id):
            return
    logger.error("Nenhum familiar recebeu o aviso do episódio %s", episodio_id)
    try:
        waha_client.enviar_texto(
            perfil.lid_whatsapp or perfil.telefone,
            "Não consegui avisar sua família. Se precisar de ajuda, ligue 192.",
        )
    except Exception:
        logger.exception("Falha ao orientar o paciente no episódio %s", episodio_id)


def enviar_notificacoes_pendentes(
    conn: sqlite3.Connection, perfil: PerfilIdoso, idoso_id: str, waha_client, agora: datetime
) -> None:
    with _lock_envio:
        for notificacao in listar_notificacoes_devidas(conn, idoso_id, agora):
            tentativas = notificacao.tentativas + 1
            try:
                waha_client.enviar_texto(notificacao.telefone, notificacao.mensagem)
            except Exception:
                logger.exception(
                    "Falha ao notificar %s (tentativa %s de %s)", notificacao.destinatario, tentativas, MAX_TENTATIVAS
                )
                esgotou = tentativas >= MAX_TENTATIVAS
                status = StatusNotificacao.FALHOU if esgotou else StatusNotificacao.PENDENTE
                with conn:
                    atualizar_notificacao(conn, notificacao.id, status, tentativas, agora + INTERVALO_REENVIO)
                if esgotou:
                    _registrar_alerta(conn, notificacao, StatusAlerta.FALHOU, idoso_id, agora)
                    if notificacao.tipo == TipoNotificacao.AVISO:
                        _orientar_paciente_se_ninguem_recebeu(conn, perfil, notificacao.episodio_id, waha_client)
                continue
            with conn:
                atualizar_notificacao(conn, notificacao.id, StatusNotificacao.ENVIADO, tentativas, agora)
            _registrar_alerta(conn, notificacao, StatusAlerta.ENVIADO, idoso_id, agora)


def processar_episodios(caminho_db: str, idoso_id: str, waha_client, agora: datetime | None = None) -> None:
    conn = conectar(caminho_db)
    perfil = obter_perfil(conn, idoso_id)
    if perfil is None:
        return
    agora = agora or datetime.now()
    for episodio in listar_vencidos(conn, idoso_id, agora):
        with conn:
            if encerrar_episodio(conn, episodio.id, EstadoEpisodio.NOTIFICADO, agora):
                _enfileirar_para_familia(
                    conn, perfil, episodio.id, TipoNotificacao.AVISO, _mensagem_sem_resposta(perfil, episodio), agora
                )
    enviar_notificacoes_pendentes(conn, perfil, idoso_id, waha_client, agora)
