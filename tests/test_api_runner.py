from datetime import datetime

from zela.api.runner import obter_runner_zela, processar_mensagem


class _ParteFalsa:
    def __init__(self, text):
        self.text = text


class _ConteudoFalso:
    def __init__(self, texto):
        self.parts = [_ParteFalsa(texto)]


class _EventoFalso:
    def __init__(self, texto, final=True):
        self.content = _ConteudoFalso(texto)
        self._final = final

    def is_final_response(self):
        return self._final


class _SessaoFalsa:
    id = "sessao-1"


class _ServicoSessaoFalso:
    def create_session_sync(self, app_name, user_id, session_id):
        return _SessaoFalsa()


class _RunnerFalso:
    def __init__(self, eventos):
        self.session_service = _ServicoSessaoFalso()
        self._eventos = eventos
        self.chamadas = []

    def run(self, user_id, session_id, new_message):
        self.chamadas.append((user_id, session_id, new_message))
        return self._eventos


def test_processar_mensagem_extrai_texto_do_evento_final():
    runner_falso = _RunnerFalso([_EventoFalso("Que bom que tomou!")])

    resposta = processar_mensagem(runner_falso, "idosa-1", "já tomei", datetime(2026, 9, 14, 8, 5))

    assert resposta == "Que bom que tomou!"
    assert len(runner_falso.chamadas) == 1


def test_processar_mensagem_retorna_mensagem_padrao_sem_evento_final():
    runner_falso = _RunnerFalso([])

    resposta = processar_mensagem(runner_falso, "idosa-1", "oi", datetime(2026, 9, 14, 8, 5))

    assert "não consegui processar" in resposta.lower()


def test_obter_runner_zela_usa_o_agente_orquestrador():
    runner = obter_runner_zela()
    assert runner.agent.name == "orquestrador_zela"
