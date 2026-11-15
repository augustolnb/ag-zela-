import logging
from concurrent.futures import ThreadPoolExecutor

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


# Uma thread, FIFO: as notificações saem na ordem e nunca seguram o chamador
# (webhook ou jobs do scheduler) esperando a API do Google.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pulseira")


def notificar_pulseira_em_segundo_plano(gmail_client, notificacao: NotificacaoPulseira) -> None:
    if gmail_client is None:
        return
    try:
        _executor.submit(notificar_pulseira, gmail_client, notificacao)
    except RuntimeError:
        # Executor já encerrado (desligamento do backend).
        logger.exception("Notificação da pulseira descartada (%s)", notificacao.assunto)


def encerrar_notificacoes() -> None:
    """No desligamento: descarta a fila sem esperar uma chamada travada ao Google.

    Troca por um executor novo (sem threads até o primeiro envio), para o
    módulo continuar utilizável se o app subir de novo no mesmo processo.
    """
    global _executor
    antigo, _executor = _executor, ThreadPoolExecutor(max_workers=1, thread_name_prefix="pulseira")
    antigo.shutdown(wait=False, cancel_futures=True)
