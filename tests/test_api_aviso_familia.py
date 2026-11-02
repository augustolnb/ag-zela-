from datetime import date, datetime, timedelta, timezone

import pytest

from zela.api.aviso_familia import _formatar_hora, enviar_notificacoes_pendentes, processar_episodios, triar_mensagem
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.storage.alertas import listar_alertas
from zela.storage.db import conectar
from zela.storage.perfil import salvar_perfil

T0 = datetime(2026, 11, 2, 10, 0, 0)
PACIENTE = "+5511900000000"
ANA = "+5511911111111"
BETO = "+5511922222222"


class _Waha:
    def __init__(self, quebrados=()):
        self.enviados = []
        self.quebrados = set(quebrados)

    def enviar_texto(self, telefone, texto):
        if telefone in self.quebrados:
            raise RuntimeError("falha")
        self.enviados.append((telefone, texto))

    def para(self, telefone):
        return [t for f, t in self.enviados if f == telefone]


@pytest.fixture
def perfil():
    return PerfilIdoso(
        nome="Maria",
        telefone=PACIENTE,
        data_nascimento=date(1945, 1, 1),
        contatos_familiares=[
            ContatoFamiliar(nome="Ana", telefone=ANA),
            ContatoFamiliar(nome="Beto", telefone=BETO),
        ],
    )


@pytest.fixture
def db(tmp_path, perfil):
    caminho = str(tmp_path / "t.db")
    salvar_perfil(conectar(caminho), perfil, idoso_id="idosa-1")
    return caminho


def _triar(db, perfil, texto, agora, waha):
    return triar_mensagem(conectar(db), "idosa-1", perfil, texto, agora, waha)


def _job(db, waha, agora):
    processar_episodios(db, "idosa-1", waha, agora=agora)


def test_sintoma_pede_confirmacao_com_prazo_e_192(db, perfil):
    waha = _Waha()
    resposta = _triar(db, perfil, "coração acelerado e tontura", T0, waha)
    assert "60 segundos" in resposta and "192" in resposta
    assert waha.enviados == []


def test_59s_nao_notifica_e_60s_notifica_todos(db, perfil):
    waha = _Waha()
    _triar(db, perfil, "coração acelerado e tontura", T0, waha)

    _job(db, waha, T0 + timedelta(seconds=59))
    assert waha.enviados == []

    _job(db, waha, T0 + timedelta(seconds=60))
    assert len(waha.para(ANA)) == len(waha.para(BETO)) == 1
    mensagem = waha.para(ANA)[0]
    assert "Maria" in mensagem and "tontura" in mensagem and "não respondeu" in mensagem


def test_job_repetido_nao_duplica(db, perfil):
    waha = _Waha()
    _triar(db, perfil, "tontura", T0, waha)
    _job(db, waha, T0 + timedelta(seconds=60))
    _job(db, waha, T0 + timedelta(seconds=70))
    _job(db, waha, T0 + timedelta(seconds=200))
    assert len(waha.para(ANA)) == 1


def test_episodio_vencido_durante_reinicio_notifica(db, perfil):
    waha = _Waha()
    _triar(db, perfil, "tontura", T0, waha)
    _job(db, waha, T0 + timedelta(hours=1))
    assert len(waha.para(ANA)) == 1


@pytest.mark.parametrize("texto", ["estou bem", "não avise ninguém"])
def test_cancelamento_no_prazo_nao_notifica(db, perfil, texto):
    waha = _Waha()
    _triar(db, perfil, "tontura", T0, waha)
    resposta = _triar(db, perfil, texto, T0 + timedelta(seconds=30), waha)
    assert resposta is not None and "não vou avisar" in resposta
    _job(db, waha, T0 + timedelta(seconds=90))
    assert waha.enviados == []


@pytest.mark.parametrize("texto", ["não estou bem", "estou bem mal", "bom dia"])
def test_resposta_que_nao_cancela_mantem_prazo(db, perfil, texto):
    waha = _Waha()
    _triar(db, perfil, "tontura", T0, waha)
    _triar(db, perfil, texto, T0 + timedelta(seconds=30), waha)
    _job(db, waha, T0 + timedelta(seconds=60))
    assert len(waha.para(ANA)) == 1


def test_novo_sintoma_nao_reinicia_prazo_e_entra_no_aviso(db, perfil):
    waha = _Waha()
    _triar(db, perfil, "tontura", T0, waha)
    _triar(db, perfil, "agora dor no peito", T0 + timedelta(seconds=50), waha)
    _job(db, waha, T0 + timedelta(seconds=60))
    assert "dor no peito" in waha.para(ANA)[0]


def test_resposta_depois_do_prazo_nao_desfaz(db, perfil):
    waha = _Waha()
    _triar(db, perfil, "tontura", T0, waha)
    resposta = _triar(db, perfil, "estou bem", T0 + timedelta(seconds=61), waha)
    assert "já" in resposta
    _job(db, waha, T0 + timedelta(seconds=65))
    assert len(waha.para(ANA)) == 1

    assert "já" in _triar(db, perfil, "estou bem", T0 + timedelta(seconds=90), waha)


def test_pedido_de_ajuda_notifica_na_hora(db, perfil):
    waha = _Waha()
    resposta = _triar(db, perfil, "chame minha filha", T0, waha)
    assert resposta is not None
    assert "pediu ajuda" in waha.para(ANA)[0]
    assert len(waha.para(BETO)) == 1


def test_pedido_de_ajuda_encerra_episodio_aberto(db, perfil):
    waha = _Waha()
    _triar(db, perfil, "tontura", T0, waha)
    _triar(db, perfil, "chame minha filha", T0 + timedelta(seconds=10), waha)
    _job(db, waha, T0 + timedelta(seconds=70))
    assert len(waha.para(ANA)) == 1


def test_mensagens_sem_episodio_seguem_fluxo_normal(db, perfil):
    waha = _Waha()
    assert _triar(db, perfil, "estou bem", T0, waha) is None
    assert _triar(db, perfil, "não avise ninguém", T0, waha) is None
    assert _triar(db, perfil, "bom dia", T0, waha) is None


def _recusar(db, perfil, waha, inicio, texto="não avise"):
    _triar(db, perfil, "tontura", inicio, waha)
    return _triar(db, perfil, texto, inicio + timedelta(seconds=10), waha)


def test_primeira_recusa_nao_adverte_e_segunda_adverte_todos(db, perfil):
    waha = _Waha()
    _recusar(db, perfil, waha, T0)
    assert waha.enviados == []

    resposta = _recusar(db, perfil, waha, T0 + timedelta(days=2), texto="estou bem")
    assert "advertência" in resposta
    mensagem = waha.para(ANA)[0]
    assert "Advertência" in mensagem and "2 vezes" in mensagem and "tontura" in mensagem
    assert len(waha.para(BETO)) == 1


def test_recusa_de_8_dias_atras_nao_conta(db, perfil):
    waha = _Waha()
    _recusar(db, perfil, waha, T0)
    _recusar(db, perfil, waha, T0 + timedelta(days=8))
    assert waha.enviados == []


def test_terceira_recusa_adverte_de_novo(db, perfil):
    waha = _Waha()
    for dia in range(3):
        _recusar(db, perfil, waha, T0 + timedelta(days=dia))
    assert len(waha.para(ANA)) == 2
    assert "3 vezes" in waha.para(ANA)[1]


def test_falha_de_um_familiar_nao_afeta_outro_e_reenvia_so_para_ele(db, perfil):
    waha = _Waha(quebrados={ANA})
    _triar(db, perfil, "tontura", T0, waha)
    _job(db, waha, T0 + timedelta(seconds=60))
    assert len(waha.para(BETO)) == 1

    _job(db, waha, T0 + timedelta(seconds=70))  # antes dos 30 s de reenvio
    waha.quebrados.clear()
    _job(db, waha, T0 + timedelta(seconds=90))

    assert len(waha.para(ANA)) == 1
    assert len(waha.para(BETO)) == 1
    status = {a.destinatario: a.status.value for a in listar_alertas(conectar(db), "idosa-1")}
    assert status == {"Ana": "enviado", "Beto": "enviado"}


def test_cinco_falhas_de_todos_orientam_paciente_a_ligar_192_uma_vez(db, perfil):
    waha = _Waha(quebrados={ANA, BETO})
    _triar(db, perfil, "tontura", T0, waha)
    for i in range(8):
        _job(db, waha, T0 + timedelta(seconds=60 + 30 * i))

    assert len(waha.para(PACIENTE)) == 1
    assert "192" in waha.para(PACIENTE)[0]
    assert {a.status.value for a in listar_alertas(conectar(db), "idosa-1")} == {"falhou"}


def test_falha_de_um_so_familiar_nao_orienta_paciente(db, perfil):
    waha = _Waha(quebrados={ANA})
    _triar(db, perfil, "tontura", T0, waha)
    for i in range(8):
        _job(db, waha, T0 + timedelta(seconds=60 + 30 * i))
    assert waha.para(PACIENTE) == []


def test_enviar_pendentes_em_paralelo_nao_duplica(db, perfil):
    import threading

    waha = _Waha()
    _triar(db, perfil, "tontura", T0, waha)
    agora = T0 + timedelta(seconds=60)
    _job(db, waha, agora)
    fios = [
        threading.Thread(
            target=lambda: enviar_notificacoes_pendentes(conectar(db), perfil, "idosa-1", waha, agora)
        )
        for _ in range(4)
    ]
    for f in fios:
        f.start()
    for f in fios:
        f.join()
    assert len(waha.para(ANA)) == 1


def test_processar_sem_perfil_nao_falha(tmp_path):
    processar_episodios(str(tmp_path / "vazio.db"), "idosa-1", _Waha(), agora=T0)


def test_hora_em_brasilia():
    assert _formatar_hora(datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)) == "12:00"
