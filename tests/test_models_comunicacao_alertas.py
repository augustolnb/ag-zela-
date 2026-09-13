from datetime import datetime

from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta, StatusAlerta
from zela.models.comunicacao import MensagemEntrada, TipoMensagem


def test_mensagem_texto_preenche_transcricao_automaticamente():
    mensagem = MensagemEntrada(
        remetente="idosa",
        tipo=TipoMensagem.TEXTO,
        conteudo_bruto="já tomei o remédio",
        timestamp=datetime(2026, 9, 13, 8, 5),
    )
    assert mensagem.transcricao == "já tomei o remédio"


def test_mensagem_audio_permite_transcricao_none_inicialmente():
    mensagem = MensagemEntrada(
        remetente="idosa",
        tipo=TipoMensagem.AUDIO,
        conteudo_bruto="<audio-bytes-base64>",
        timestamp=datetime(2026, 9, 13, 8, 5),
    )
    assert mensagem.transcricao is None


def test_alerta_valido_com_status_padrao_enviado():
    alerta = Alerta(
        nivel=NivelAlerta.CRITICO,
        destinatario="João",
        canal=CanalAlerta.WHATSAPP,
        mensagem="Sem resposta da Maria há 20 minutos.",
        timestamp=datetime(2026, 9, 13, 8, 20),
    )
    assert alerta.status == StatusAlerta.ENVIADO
