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
