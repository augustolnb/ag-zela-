from datetime import datetime

from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.storage.alertas import listar_alertas, salvar_alerta
from zela.storage.db import conectar


def test_salvar_e_listar_alertas():
    conn = conectar(":memory:")
    alerta = Alerta(
        nivel=NivelAlerta.CRITICO,
        destinatario="João",
        canal=CanalAlerta.WHATSAPP,
        mensagem="Sem resposta.",
        timestamp=datetime(2026, 9, 16, 14, 20),
    )

    salvar_alerta(conn, alerta, idoso_id="idosa-1")
    alertas = listar_alertas(conn, "idosa-1")

    assert len(alertas) == 1
    assert alertas[0].destinatario == "João"
    assert alertas[0].simulado is False


def test_salvar_alerta_simulado_preserva_a_flag():
    conn = conectar(":memory:")
    alerta = Alerta(
        nivel=NivelAlerta.CRITICO,
        destinatario="servico_emergencia_simulado",
        canal=CanalAlerta.WHATSAPP,
        mensagem="[SIMULAÇÃO] ...",
        simulado=True,
        timestamp=datetime(2026, 9, 16, 14, 30),
    )

    salvar_alerta(conn, alerta, idoso_id="idosa-1")
    alertas = listar_alertas(conn, "idosa-1")

    assert alertas[0].simulado is True


def test_listar_alertas_ordena_por_timestamp():
    conn = conectar(":memory:")
    tarde = Alerta(
        nivel=NivelAlerta.INFO, destinatario="A", canal=CanalAlerta.WHATSAPP,
        mensagem="segundo", timestamp=datetime(2026, 9, 16, 12, 0),
    )
    manha = Alerta(
        nivel=NivelAlerta.INFO, destinatario="A", canal=CanalAlerta.WHATSAPP,
        mensagem="primeiro", timestamp=datetime(2026, 9, 16, 8, 0),
    )
    salvar_alerta(conn, tarde, idoso_id="idosa-1")
    salvar_alerta(conn, manha, idoso_id="idosa-1")

    alertas = listar_alertas(conn, "idosa-1")

    assert [a.mensagem for a in alertas] == ["primeiro", "segundo"]
