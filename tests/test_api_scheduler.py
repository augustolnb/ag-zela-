from datetime import date, time

from zela.api.scheduler import verificar_e_enviar_lembretes
from zela.models.perfil import ContatoFamiliar, PerfilIdoso
from zela.models.rotina import Dosagem, Medicamento
from zela.storage.db import conectar
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
