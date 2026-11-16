from datetime import date, datetime, time

from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta, StatusAlerta
from zela.models.rotina import (
    CanalConfirmacao,
    Compromisso,
    ConfirmacaoMedicacao,
    Dosagem,
    Medicamento,
    StatusConfirmacao,
    TipoCompromisso,
)
from zela.streamlit_app.historico import (
    TIPO_AVISO,
    TIPO_COMPROMISSO,
    TIPO_MEDICACAO,
    ItemHistorico,
    filtrar_historico,
    montar_historico,
)

AGORA = datetime(2026, 11, 16, 12, 0)
DIPIRONA = Medicamento(id="m1", nome="Dipirona", dosagem=Dosagem(quantidade=1, unidade="comprimido"), horarios=[time(8, 0)])


def _alerta():
    return Alerta(
        nivel=NivelAlerta.CRITICO, destinatario="Augusto", canal=CanalAlerta.WHATSAPP,
        mensagem="Atenção: relatou tontura", status=StatusAlerta.ENVIADO, timestamp=datetime(2026, 11, 15, 19, 34),
    )


def _compromisso(titulo="Cardiologista", quando=datetime(2026, 11, 19, 8, 0)):
    return Compromisso.model_construct(
        id=titulo, titulo=titulo, data_hora=quando, local="AMAS 303 sul", tipo=TipoCompromisso.CONSULTA
    )


def _confirmacao(status=StatusConfirmacao.CONFIRMADO, confirmado=datetime(2026, 11, 14, 8, 10)):
    return ConfirmacaoMedicacao(
        medicamento_id="m1", horario_previsto=datetime(2026, 11, 14, 8, 0), horario_confirmado=confirmado,
        status=status, canal=CanalConfirmacao.WHATSAPP,
    )


def test_monta_os_tres_tipos_do_mais_recente_ao_mais_antigo():
    itens = montar_historico(
        alertas=[_alerta()],
        compromissos=[(_compromisso(), False)],
        confirmacoes=[_confirmacao()],
        medicamentos=[DIPIRONA],
        agora=AGORA,
    )

    assert [i.tipo for i in itens] == [TIPO_COMPROMISSO, TIPO_AVISO, TIPO_MEDICACAO]
    assert itens[1] == ItemHistorico(
        data_hora=datetime(2026, 11, 15, 19, 34), tipo=TIPO_AVISO,
        descricao="Atenção: relatou tontura", situacao="CRÍTICO · para Augusto · enviado",
    )
    assert itens[2].descricao == "Dipirona (1.0 comprimido), previsto às 08:00"
    assert itens[2].situacao == "Tomado"
    assert itens[2].data_hora == datetime(2026, 11, 14, 8, 10)


def test_situacao_do_compromisso_e_do_remedio():
    itens = montar_historico(
        alertas=[],
        compromissos=[
            (_compromisso("Futuro", datetime(2026, 11, 19, 8, 0)), False),
            (_compromisso("Passado", datetime(2026, 11, 1, 8, 0)), False),
            (_compromisso("Cancelado", datetime(2026, 11, 2, 8, 0)), True),
        ],
        confirmacoes=[_confirmacao(StatusConfirmacao.ATRASADO), _confirmacao(StatusConfirmacao.NAO_CONFIRMADO, None)],
        medicamentos=[DIPIRONA],
        agora=AGORA,
    )
    situacoes = {i.descricao.split(" (")[0]: i.situacao for i in itens if i.tipo == TIPO_COMPROMISSO}

    assert situacoes == {"Futuro": "Agendado", "Passado": "Realizado", "Cancelado": "Removido"}
    remedios = [i for i in itens if i.tipo == TIPO_MEDICACAO]
    assert sorted(i.situacao for i in remedios) == ["Não confirmado", "Tomado com atraso"]
    # Sem horário de confirmação, o item fica no horário previsto.
    assert any(i.data_hora == datetime(2026, 11, 14, 8, 0) for i in remedios)


def test_remedio_removido_aparece_pelo_id():
    itens = montar_historico(alertas=[], compromissos=[], confirmacoes=[_confirmacao()], medicamentos=[], agora=AGORA)
    assert itens[0].descricao == "m1, previsto às 08:00"


def _itens():
    return montar_historico(
        alertas=[_alerta()],
        compromissos=[(_compromisso(), False)],
        confirmacoes=[_confirmacao()],
        medicamentos=[DIPIRONA],
        agora=AGORA,
    )


def test_filtra_por_dia():
    assert [i.tipo for i in filtrar_historico(_itens(), dia=date(2026, 11, 15))] == [TIPO_AVISO]
    assert filtrar_historico(_itens(), dia=date(2026, 1, 1)) == []


def test_busca_ignora_maiusculas_e_acentos():
    assert [i.tipo for i in filtrar_historico(_itens(), busca="DIPIRONA")] == [TIPO_MEDICACAO]
    assert [i.tipo for i in filtrar_historico(_itens(), busca="atencao")] == [TIPO_AVISO]
    assert [i.tipo for i in filtrar_historico(_itens(), busca="  cardio ")] == [TIPO_COMPROMISSO]


def test_filtra_por_tipo_e_combina_filtros():
    assert [i.tipo for i in filtrar_historico(_itens(), tipos={TIPO_MEDICACAO, TIPO_AVISO})] == [TIPO_AVISO, TIPO_MEDICACAO]
    assert filtrar_historico(_itens(), dia=date(2026, 11, 15), busca="dipirona") == []


def test_sem_filtros_devolve_tudo():
    assert filtrar_historico(_itens()) == _itens()
