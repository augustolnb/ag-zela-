from datetime import date, datetime, time, timedelta

import pytest

from zela.api.scheduler import (
    despachar_alertas,
    iniciar_scheduler,
    verificar_sono_e_avisar,
    verificar_e_enviar_lembretes,
    verificar_e_escalonar_riscos,
)
from zela.domain.emergencia import EstadoEscalonamento, EstagioEscalonamento
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.models.monitoramento import FonteSensor, LeituraSensor, TipoLeitura
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.models.rotina import Dosagem, Medicamento
from zela.storage.alertas import listar_alertas
from zela.storage.db import conectar
from zela.storage.escalonamento import obter_estado, salvar_estado
from zela.storage.monitoramento import salvar_leitura
from zela.storage.perfil import salvar_perfil
from zela.storage.rotina import salvar_medicamento


@pytest.fixture(autouse=True)
def _limpa_avisos(monkeypatch):
    monkeypatch.setattr("zela.api.scheduler._avisos_ja_enviados", set())


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


def test_verificar_e_enviar_lembretes_usa_lid_quando_disponivel(tmp_path, monkeypatch):
    monkeypatch.setattr("zela.api.scheduler._lembretes_ja_enviados", set())

    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    perfil = _perfil()
    perfil.lid_whatsapp = "109281332445239@lid"
    salvar_perfil(conn, perfil, idoso_id="idosa-1")
    medicamento = Medicamento(
        id="med-lid-1", nome="Losartana",
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
    verificar_e_enviar_lembretes(caminho_db, "idosa-1", waha_falso)

    assert waha_falso.enviados[0][0] == "109281332445239@lid"


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
    salvar_leitura(conn, _fc(datetime(2026, 9, 16, 13, 55)), idoso_id="idosa-1")
    salvar_leitura(conn, _sinal(datetime(2026, 9, 16, 13, 55)), idoso_id="idosa-1")

    waha_falso = _WahaFalso()
    alertas = verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)

    assert alertas == []
    assert waha_falso.enviados == []


def _fc(timestamp):
    return LeituraSensor(
        fonte=FonteSensor.SMARTWATCH, tipo=TipoLeitura.FREQUENCIA_CARDIACA, valor=70,
        unidade="bpm", timestamp=timestamp,
    )


def _sinal(timestamp):
    return LeituraSensor(
        fonte=FonteSensor.ESP32, tipo=TipoLeitura.SINAL_DE_VIDA, valor=1,
        unidade="sinal", timestamp=timestamp,
    )


class _Relogio:
    atual = datetime(2026, 9, 16, 14, 0)

    @classmethod
    def now(cls):
        return cls.atual


def _cenario_com_pulseira_viva(tmp_path, monkeypatch):
    """Só a pulseira envia dados: o ESP32 está silencioso, o que gera AVISO."""
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")
    salvar_leitura(conn, _fc(datetime(2026, 9, 16, 13, 55)), idoso_id="idosa-1")
    _Relogio.atual = datetime(2026, 9, 16, 14, 0)
    monkeypatch.setattr("zela.api.scheduler.datetime", _Relogio)
    return caminho_db, conn


def test_aviso_envia_info_ao_primeiro_familiar_sem_escalonar(tmp_path, monkeypatch):
    caminho_db, conn = _cenario_com_pulseira_viva(tmp_path, monkeypatch)

    def _nao_deve_escalonar(*args, **kwargs):
        raise AssertionError("AVISO não pode entrar na escada de escalonamento")

    monkeypatch.setattr("zela.api.scheduler.aplicar_escalonamento", _nao_deve_escalonar)

    waha_falso = _WahaFalso()
    alertas = verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)

    assert len(alertas) == 1
    assert alertas[0].nivel == NivelAlerta.INFO
    assert waha_falso.enviados == [("+5511987654321", alertas[0].mensagem)]
    assert len(listar_alertas(conn, "idosa-1")) == 1
    assert obter_estado(conn, "idosa-1").estagio == EstagioEscalonamento.OCIOSO


def test_aviso_nao_repete_no_mesmo_episodio(tmp_path, monkeypatch):
    caminho_db, _ = _cenario_com_pulseira_viva(tmp_path, monkeypatch)
    waha_falso = _WahaFalso()

    verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)
    segunda = verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)

    assert segunda == []
    assert len(waha_falso.enviados) == 1


def test_aviso_volta_a_avisar_apos_normalizar(tmp_path, monkeypatch):
    caminho_db, conn = _cenario_com_pulseira_viva(tmp_path, monkeypatch)
    waha_falso = _WahaFalso()

    verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)

    # O ESP32 volta a enviar sinal: status NORMAL
    salvar_leitura(conn, _sinal(datetime(2026, 9, 16, 13, 59)), idoso_id="idosa-1")
    assert verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso) == []

    # 20 min depois o ESP32 para de novo, com a pulseira ainda viva
    salvar_leitura(conn, _fc(datetime(2026, 9, 16, 14, 19)), idoso_id="idosa-1")
    _Relogio.atual = datetime(2026, 9, 16, 14, 20)
    verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)

    assert len(waha_falso.enviados) == 2


def test_aviso_encerra_escada_aberta_e_novo_risco_recomeca_do_idoso(tmp_path, monkeypatch):
    caminho_db, conn = _cenario_com_pulseira_viva(tmp_path, monkeypatch)
    salvar_estado(
        conn, "idosa-1",
        EstadoEscalonamento(
            estagio=EstagioEscalonamento.NOTIFICAR_FAMILIA,
            iniciado_em=datetime(2026, 9, 16, 13, 0),
        ),
    )

    verificar_e_escalonar_riscos(caminho_db, "idosa-1", _WahaFalso())

    assert obter_estado(conn, "idosa-1").estagio == EstagioEscalonamento.RESOLVIDO


def _salvar_sono(conn, dias_atras, horas, agora):
    fim = (agora - timedelta(days=dias_atras)).replace(hour=7)
    salvar_leitura(
        conn,
        LeituraSensor(
            fonte=FonteSensor.SMARTWATCH, tipo=TipoLeitura.SONO, valor=horas,
            unidade="horas", timestamp=fim,
        ),
        idoso_id="idosa-1",
    )


def test_verificar_sono_envia_aviso_uma_vez_por_dia(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")
    agora = datetime(2026, 9, 16, 9, 0)
    for dias in range(1, 15):
        _salvar_sono(conn, dias, 7, agora)
    _salvar_sono(conn, 0, 4, agora)
    _Relogio.atual = agora
    monkeypatch.setattr("zela.api.scheduler.datetime", _Relogio)

    waha_falso = _WahaFalso()
    primeira = verificar_sono_e_avisar(caminho_db, "idosa-1", waha_falso)
    segunda = verificar_sono_e_avisar(caminho_db, "idosa-1", waha_falso)

    assert len(primeira) == 1 and primeira[0].nivel == NivelAlerta.INFO
    assert segunda == []
    assert waha_falso.enviados == [("+5511987654321", primeira[0].mensagem)]


def test_normalizar_nao_faz_sono_ser_reenviado_no_mesmo_dia(tmp_path, monkeypatch):
    caminho_db = str(tmp_path / "teste.db")
    conn = conectar(caminho_db)
    salvar_perfil(conn, _perfil(), idoso_id="idosa-1")
    agora = datetime(2026, 9, 16, 9, 0)
    for dias in range(1, 15):
        _salvar_sono(conn, dias, 7, agora)
    _salvar_sono(conn, 0, 4, agora)
    salvar_leitura(conn, _fc(agora), idoso_id="idosa-1")
    salvar_leitura(conn, _sinal(agora), idoso_id="idosa-1")
    _Relogio.atual = agora
    monkeypatch.setattr("zela.api.scheduler.datetime", _Relogio)

    waha_falso = _WahaFalso()
    verificar_sono_e_avisar(caminho_db, "idosa-1", waha_falso)
    verificar_e_escalonar_riscos(caminho_db, "idosa-1", waha_falso)
    verificar_sono_e_avisar(caminho_db, "idosa-1", waha_falso)

    assert len(waha_falso.enviados) == 1


def test_iniciar_scheduler_registra_job_de_sono(tmp_path):
    agendador = iniciar_scheduler(str(tmp_path / "teste.db"), "idosa-1", _WahaFalso())
    try:
        assert agendador.get_job("verificar_sono") is not None
    finally:
        agendador.shutdown(wait=False)


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


def test_despachar_alertas_salva_e_envia_alertas_nao_simulados():
    conn = conectar(":memory:")
    perfil = _perfil()
    waha_falso = _WahaFalso()
    alerta_familia = Alerta(
        nivel=NivelAlerta.CRITICO, destinatario="João", canal=CanalAlerta.WHATSAPP,
        mensagem="Atenção, sem resposta.", timestamp=datetime(2026, 9, 17, 10, 0),
    )

    despachar_alertas(conn, [alerta_familia], perfil, "idosa-1", waha_falso)

    assert waha_falso.enviados == [("+5511987654321", "Atenção, sem resposta.")]
    assert len(listar_alertas(conn, "idosa-1")) == 1


def test_despachar_alertas_usa_lid_da_idosa_quando_disponivel():
    conn = conectar(":memory:")
    perfil = _perfil()
    perfil.lid_whatsapp = "109281332445239@lid"
    waha_falso = _WahaFalso()
    alerta_idosa = Alerta(
        nivel=NivelAlerta.ATENCAO, destinatario=perfil.nome, canal=CanalAlerta.WHATSAPP,
        mensagem="Está tudo bem?", timestamp=datetime(2026, 9, 17, 10, 0),
    )

    despachar_alertas(conn, [alerta_idosa], perfil, "idosa-1", waha_falso)

    assert waha_falso.enviados == [("109281332445239@lid", "Está tudo bem?")]


def test_despachar_alertas_nao_envia_alerta_simulado():
    conn = conectar(":memory:")
    perfil = _perfil()
    waha_falso = _WahaFalso()
    alerta_simulado = Alerta(
        nivel=NivelAlerta.CRITICO, destinatario="servico_emergencia_simulado",
        canal=CanalAlerta.WHATSAPP, mensagem="[SIMULAÇÃO] ...",
        timestamp=datetime(2026, 9, 17, 10, 0), simulado=True,
    )

    despachar_alertas(conn, [alerta_simulado], perfil, "idosa-1", waha_falso)

    assert waha_falso.enviados == []
    assert len(listar_alertas(conn, "idosa-1")) == 1


class _WahaQuebrado(_WahaFalso):
    def __init__(self, telefones_quebrados):
        super().__init__()
        self.telefones_quebrados = telefones_quebrados

    def enviar_texto(self, telefone, texto):
        if telefone in self.telefones_quebrados:
            raise RuntimeError("No LID for user")
        super().enviar_texto(telefone, texto)


def _perfil_dois_contatos():
    return PerfilIdoso(
        nome="Maria",
        telefone="+5511900000000",
        data_nascimento=date(1945, 1, 1),
        contatos_familiares=[
            ContatoFamiliar(nome="Ana", telefone="+5511911111111"),
            ContatoFamiliar(nome="Beto", telefone="+5511922222222"),
        ],
    )


def _alerta_para(nome):
    return Alerta(
        nivel=NivelAlerta.CRITICO, destinatario=nome, canal=CanalAlerta.WHATSAPP,
        mensagem="x", timestamp=datetime(2026, 11, 2, 10, 0),
    )


def test_despachar_alertas_registra_status_real_e_nao_interrompe_outros(tmp_path):
    conn = conectar(str(tmp_path / "t.db"))
    waha = _WahaQuebrado({"+5511911111111"})

    despachar_alertas(conn, [_alerta_para("Ana"), _alerta_para("Beto")], _perfil_dois_contatos(), "idosa-1", waha)

    por_nome = {a.destinatario: a.status.value for a in listar_alertas(conn, "idosa-1")}
    assert por_nome == {"Ana": "falhou", "Beto": "enviado"}
    assert waha.enviados == [("+5511922222222", "x")]
