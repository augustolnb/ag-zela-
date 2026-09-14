from datetime import datetime, time, timedelta

from zela.models.comunicacao import MensagemEntrada, TipoMensagem
from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.models.rotina import Dosagem, Medicamento
from zela.simulacao import simular_dia


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=datetime(1945, 3, 12).date(),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def test_simulacao_gera_lembrete_e_confirmacao_quando_idoso_responde_positivo():
    agora = datetime(2026, 9, 13, 8, 0)
    medicamento = Medicamento(
        id="med-1",
        nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"),
        horarios=[time(8, 0)],
    )
    leitura_presenca = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=agora,
    )
    resposta = MensagemEntrada(
        remetente="idosa",
        tipo=TipoMensagem.TEXTO,
        conteudo_bruto="tomei sim",
        timestamp=agora,
    )

    relatorio = simular_dia(_perfil(), [medicamento], [leitura_presenca], resposta, agora)

    assert len(relatorio.lembretes_enviados) == 1
    assert len(relatorio.confirmacoes) == 1
    assert relatorio.alertas == []


def test_simulacao_escalona_quando_nao_ha_presenca_por_muitas_horas():
    agora = datetime(2026, 9, 13, 14, 0)
    ultima_presenca = agora - timedelta(hours=8)
    leitura_presenca = LeituraSensor(
        fonte=FonteSensor.ESP32,
        tipo=TipoLeitura.PRESENCA,
        valor=1,
        unidade="deteccao",
        timestamp=ultima_presenca,
    )

    relatorio = simular_dia(_perfil(), [], [leitura_presenca], None, agora)

    assert len(relatorio.alertas) == 1
    assert relatorio.alertas[0].destinatario == "Maria da Silva"
