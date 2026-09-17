from datetime import date, datetime, time, timedelta

from zela.api.scheduler import verificar_e_enviar_lembretes, verificar_e_escalonar_riscos
from zela.domain.emergencia import EstadoEscalonamento, EstagioEscalonamento
from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.models.rotina import Dosagem, Medicamento
from zela.storage.alertas import listar_alertas
from zela.storage.db import conectar
from zela.storage.escalonamento import obter_estado, salvar_estado
from zela.storage.monitoramento import salvar_leitura
from zela.storage.perfil import salvar_perfil
from zela.storage.rotina import salvar_medicamento


class _WahaFalso:
    def __init__(self):
        self.enviados = []

    def enviar_texto(self, telefone, texto):
        self.enviados.append((telefone, texto))


def _perfil():
    return PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[ContatoFamiliar(nome="João", telefone="+5511987654321")],
    )


def test_verificar_e_enviar_lembretes_envia_para_o_telefone_do_idoso(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")
    medicamento = Medicamento(
        id="med-1", nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
    )
    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")

    class _DatetimeFixo:
        @staticmethod
        def now():
            from datetime import datetime as _dt
            return _dt(2026, 9, 14, 8, 5)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    waha_falso = _WahaFalso()
    enviadas = verificar_e_enviar_lembretes(caminho_db, "idosa-1", waha_falso)

    assert len(enviadas) == 1
    assert "Losartana" in enviadas[0]
    assert waha_falso.enviados[0][0] == "+5511911111111"


def test_verificar_e_enviar_lembretes_sem_perfil_retorna_lista_vazia(tmp_path):
    caminho_db = str(tmp_path / "teste.db")
    conectar(caminho_db)

    waha_falso = _WahaFalso()
    enviadas = verificar_e_enviar_lembretes(caminho_db, "nao-existe", waha_falso)

    assert enviadas == []


def test_verificar_e_enviar_lembretes_nao_reenvia_dentro_da_mesma_janela(tmp_path, monkeypatch):
    monkeypatch.setattr("zela.api.scheduler._lembretes_ja_enviados", set())

    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")
    medicamento = Medicamento(
        id="med-1", nome="Losartana",
        dosagem=Dosagem(quantidade=50, unidade="mg"), horarios=[time(8, 0)],
    )
    salvar_medicamento(conn, medicamento, idoso_id="idosa-1")

    class _DatetimeFixo:
        _agora = None

        @classmethod
        def now(cls):
            return cls._agora

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    waha_falso = _WahaFalso()

    from datetime import datetime as _dt

    _DatetimeFixo._agora = _dt(2026, 9, 14, 8, 5)
    primeira = verificar_e_enviar_lembretes(caminho_db, "idosa-1", waha_falso)
    assert len(primeira) == 1

    _DatetimeFixo._agora = _dt(2026, 9, 14, 8, 12)
    segunda = verificar_e_enviar_lembretes(caminho_db, "idosa-1", waha_falso)
    assert len(segunda) == 0
    assert len(waha_falso.enviados) == 1


def test_verificar_e_escalonar_riscos_risco_envia_para_a_idosa(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=datetime(2026, 9, 16, 6, 0),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    class _DatetimeFixo:
        @staticmethod
        def now():
            return datetime(2026, 9, 16, 14, 0)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    waha_falso = _WahaFalso()
    alertas = verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)

    assert len(alertas) == 1
    assert waha_falso.enviados == [("+5511911111111", alertas[0].mensagem)]
    assert obter_estado(conn, "idosa-1").estagio == EstagioEscalonamento.CONTATO_IDOSO


def test_verificar_e_escalonar_riscos_normal_nao_envia_nada(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")

    class _DatetimeFixo:
        @staticmethod
        def now():
            return datetime(2026, 9, 16, 14, 0)

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=datetime(2026, 9, 16, 13, 45),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    waha_falso = _WahaFalso()
    alertas = verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)

    assert alertas == []
    assert waha_falso.enviados == []


def test_verificar_e_escalonar_riscos_sem_perfil_retorna_lista_vazia(tmp_path):
    caminho_db = str(tmp_path / "teste.db")
    conectar(caminho_db)

    waha_falso = _WahaFalso()
    alertas = verificar_e_escalonar_riscos(caminho_db, "nao-existe", waha_falso)

    assert alertas == []


def test_verificar_e_escalonar_riscos_simulado_nao_envia_e_persiste(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    # O contato "servico_emergencia_simulado" é o mesmo nome sentinela usado
    # em `Alerta.destinatario` pelo alerta de SIMULAR_EMERGENCIA. Ele é
    # incluído aqui de propósito com um telefone resolvível: se a guarda
    # `if alerta.simulado: continue` em `verificar_e_escalonar_riscos` for
    # removida, `_telefone_por_nome` resolveria este nome para um telefone de
    # verdade e o alerta simulado SERIA enviado — o que faria este teste
    # falhar. Isso garante que o teste comprova a guarda em si, e não apenas
    # o acidente de `_telefone_por_nome` retornar None para um nome sem
    # correspondência.
    perfil = PerfilIdoso(
        nome="Maria da Silva",
        telefone="+5511911111111",
        data_nascimento=date(1945, 3, 12),
        contatos_familiares=[
            ContatoFamiliar(nome="João", telefone="+5511987654321"),
            ContatoFamiliar(nome="servico_emergencia_simulado", telefone="+5511900000000"),
        ],
    )
    salvar_perfil(conn, perfil, idoso_id="idosa-1")
    leitura = LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.PRESENCA, valor=1,
        unidade="deteccao", timestamp=datetime(2026, 9, 16, 6, 0),
    )
    salvar_leitura(conn, leitura, idoso_id="idosa-1")

    agora = datetime(2026, 9, 16, 14, 0)
    inicio_notificar_familia = agora - timedelta(minutes=16)
    salvar_estado(
        conn,
        "idosa-1",
        EstadoEscalonamento(
            estagio=EstagioEscalonamento.NOTIFICAR_FAMILIA, iniciado_em=inicio_notificar_familia
        ),
    )

    class _DatetimeFixo:
        @staticmethod
        def now():
            return agora

    monkeypatch.setattr("zela.api.scheduler.datetime", _DatetimeFixo)

    waha_falso = _WahaFalso()
    alertas = verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)

    assert len(alertas) == 1
    assert alertas[0].simulado is True
    assert alertas[0].destinatario == "servico_emergencia_simulado"
    assert obter_estado(conn, "idosa-1").estagio == EstagioEscalonamento.SIMULAR_EMERGENCIA

    # Regra de segurança: um alerta simulado nunca é enviado por WhatsApp de verdade.
    assert waha_falso.enviados == []

    # Mas continua sendo persistido, para auditoria/histórico.
    alertas_persistidos = listar_alertas(conn, "idosa-1")
    assert any(a.simulado for a in alertas_persistidos)
