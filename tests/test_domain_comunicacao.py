from datetime import datetime

from zela.domain.comunicacao import formatar_lembrete, interpretar_resposta
from zela.models.comunicacao import MensagemEntrada, TipoMensagem
from zela.models.rotina import Dosagem, Medicamento
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
