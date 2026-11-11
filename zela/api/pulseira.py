import logging

from zela.domain.pulseira import NotificacaoPulseira

logger = logging.getLogger(__name__)


def notificar_pulseira(gmail_client, notificacao: NotificacaoPulseira) -> bool:
    """Canal adicional: nunca levanta exceção, para não afetar o WhatsApp nem os avisos."""
    if gmail_client is None:
        return False
    try:
        gmail_client.notificar(notificacao.assunto, notificacao.corpo)
    except Exception:
        logger.exception("Falha ao notificar a pulseira pelo Gmail (%s)", notificacao.assunto)
        return False
    return True
