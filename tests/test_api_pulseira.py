from zela.api.pulseira import notificar_pulseira
from zela.domain.pulseira import NotificacaoPulseira

N = NotificacaoPulseira(assunto="Zela+: hora do remédio", corpo="Dipirona")


class _Gmail:
    def __init__(self, erro=None):
        self.chamadas = []
        self.erro = erro

    def notificar(self, assunto, corpo):
        if self.erro:
            raise self.erro
        self.chamadas.append((assunto, corpo))
        return "msg-1"


def test_sem_cliente_nao_notifica():
    assert notificar_pulseira(None, N) is False


def test_falha_do_gmail_vira_false():
    assert notificar_pulseira(_Gmail(erro=RuntimeError("fora")), N) is False


def test_sucesso_chama_notificar_com_assunto_e_corpo():
    gmail = _Gmail()
    assert notificar_pulseira(gmail, N) is True
    assert gmail.chamadas == [("Zela+: hora do remédio", "Dipirona")]


def test_encerrar_descarta_a_fila_sem_esperar_e_continua_utilizavel(monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from zela.api import pulseira

    antigo = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(pulseira, "_executor", antigo)
    liberar = threading.Event()
    gmail = _Gmail()
    antigo.submit(liberar.wait, 5)  # ocupa a única thread, como uma chamada travada
    pulseira.notificar_pulseira_em_segundo_plano(gmail, N)  # fica na fila

    pulseira.encerrar_notificacoes()
    liberar.set()
    antigo.shutdown(wait=True)

    assert gmail.chamadas == []
    assert pulseira._executor is not antigo
    pulseira.notificar_pulseira_em_segundo_plano(gmail, N)
    pulseira._executor.submit(lambda: None).result(timeout=5)
    assert len(gmail.chamadas) == 1
