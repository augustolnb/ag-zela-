from datetime import datetime

from zela.domain.comunicacao import (
    formatar_lembrete,
    formatar_lembrete_compromisso,
    interpretar_resposta,
)
from zela.models.comunicacao import MensagemEntrada, TipoMensagem
from zela.models.rotina import Compromisso, Dosagem, Medicamento, TipoCompromisso
from datetime import time


def _medicamento():
    return Medicamento(
        id="med-1",
        nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"),
        horarios=[time(8, 0)],
    )


def test_formatar_lembrete_inclui_nome_e_dosagem():
    texto = formatar_lembrete(_medicamento())
    assert "Losartana" in texto
    assert "50" in texto
    assert "mg" in texto


def test_interpretar_resposta_positiva():
    mensagem = MensagemEntrada(
        remetente="idosa", tipo=TipoMensagem.TEXTO, conteudo_bruto="Sim, já tomei",
        timestamp=datetime(2026, 9, 13, 8, 5),
    )
    assert interpretar_resposta(mensagem) is True


def test_interpretar_resposta_negativa():
    mensagem = MensagemEntrada(
        remetente="idosa", tipo=TipoMensagem.TEXTO, conteudo_bruto="Ainda não, esqueci",
        timestamp=datetime(2026, 9, 13, 8, 5),
    )
    assert interpretar_resposta(mensagem) is False


def test_interpretar_resposta_ambigua_retorna_none():
    mensagem = MensagemEntrada(
        remetente="idosa", tipo=TipoMensagem.TEXTO, conteudo_bruto="Está chovendo hoje",
        timestamp=datetime(2026, 9, 13, 8, 5),
    )
    assert interpretar_resposta(mensagem) is None


def _compromisso():
    return Compromisso(
        id="c1", titulo="Cardiologista", data_hora=datetime(2026, 11, 10, 14, 30),
        local="Clínica Central", tipo=TipoCompromisso.CONSULTA,
    )


def test_formatar_lembrete_compromisso_instantaneo_menciona_titulo_e_data():
    texto = formatar_lembrete_compromisso(_compromisso(), "instantaneo")
    assert "Cardiologista" in texto
    assert "Clínica Central" in texto


def test_formatar_lembrete_compromisso_cancelamento_avisa_que_foi_cancelado():
    texto = formatar_lembrete_compromisso(_compromisso(), "cancelamento")
    assert "cancelado" in texto.lower()
    assert "Cardiologista" in texto


def test_formatar_lembrete_compromisso_todos_os_tipos_incluem_titulo_e_local():
    for tipo in ["instantaneo", "24h", "manha", "1h", "cancelamento"]:
        texto = formatar_lembrete_compromisso(_compromisso(), tipo)
        assert "Cardiologista" in texto, tipo
        assert "Clínica Central" in texto, tipo
