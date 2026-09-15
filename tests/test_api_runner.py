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
    def __init__(self, session_id="sessao-1"):
        self.id = session_id


class _ServicoSessaoFalso:
    """Modela o comportamento real do InMemorySessionService: get_session_sync
    retorna None se a sessão não existir, create_session_sync cria a sessão."""

    def __init__(self):
        self._sessoes = {}
        self.chamadas_get = []
        self.chamadas_create = []

    def get_session_sync(self, *, app_name, user_id, session_id):
        self.chamadas_get.append((app_name, user_id, session_id))
        return self._sessoes.get(session_id)

    def create_session_sync(self, *, app_name, user_id, session_id):
        self.chamadas_create.append((app_name, user_id, session_id))
        sessao = _SessaoFalsa("sessao-1")
        self._sessoes[session_id] = sessao
        return sessao


class _RunnerFalso:
    def __init__(self, eventos):
        self.session_service = _ServicoSessaoFalso()
        self._eventos = eventos
        self.chamadas = []

    def run(self, *, user_id, session_id, new_message):
        self.chamadas.append((user_id, session_id, new_message))
        return self._eventos


def test_processar_mensagem_extrai_texto_do_evento_final():
    runner_falso = _RunnerFalso([_EventoFalso("Que bom que tomou!")])

    resposta = processar_mensagem(runner_falso, "idosa-1", "já tomei", datetime(2026, 9, 14, 8, 5))

    assert resposta == "Que bom que tomou!"
    assert len(runner_falso.chamadas) == 1
    user_id, session_id, new_message = runner_falso.chamadas[0]
    assert user_id == "idosa-1"
    assert session_id == "sessao-1"
    assert "já tomei" in new_message.parts[0].text
    assert "idosa-1" in new_message.parts[0].text
    assert datetime(2026, 9, 14, 8, 5).isoformat() in new_message.parts[0].text


def test_processar_mensagem_inclui_idoso_id_e_agora_no_texto_enviado_ao_modelo():
    runner_falso = _RunnerFalso([_EventoFalso("ok")])
    agora = datetime(2026, 9, 14, 12, 30, 0)

    processar_mensagem(runner_falso, "idosa-42", "oi", agora)

    _, _, new_message = runner_falso.chamadas[0]
    texto_enviado = new_message.parts[0].text
    assert "idosa-42" in texto_enviado
    assert agora.isoformat() in texto_enviado


def test_processar_mensagem_reusa_sessao_em_chamadas_consecutivas():
    runner_falso = _RunnerFalso([_EventoFalso("ok")])

    processar_mensagem(runner_falso, "idosa-1", "primeira mensagem", datetime(2026, 9, 14, 8, 5))
    processar_mensagem(runner_falso, "idosa-1", "segunda mensagem", datetime(2026, 9, 14, 8, 6))

    servico = runner_falso.session_service
    assert len(servico.chamadas_get) == 2
    assert len(servico.chamadas_create) == 1
    assert len(runner_falso.chamadas) == 2


def test_processar_mensagem_retorna_mensagem_padrao_sem_evento_final():
    runner_falso = _RunnerFalso([])

    resposta = processar_mensagem(runner_falso, "idosa-1", "oi", datetime(2026, 9, 14, 8, 5))

    assert "não consegui processar" in resposta.lower()


def test_obter_runner_zela_usa_o_agente_orquestrador():
    runner = obter_runner_zela()
    assert runner.agent.name == "orquestrador_zela"
