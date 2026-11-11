from datetime import time

import pytest

from zela.domain.pulseira import (
    notificacao_checagem,
    notificacao_confirmacao_sintoma,
    notificacao_lembrete_remedio,
)
from zela.models.rotina import Dosagem, Medicamento


def _dipirona():
    return Medicamento(
        id="med-1",
        nome="dipirona",
        dosagem=Dosagem(quantidade=1, unidade="comp de 500mg"),
        horarios=[time(8, 30)],
    )


def test_lembrete_traz_nome_e_dose():
    n = notificacao_lembrete_remedio(_dipirona())
    assert n.assunto == "Zela+: hora do remédio"
    assert "dipirona" in n.corpo and "500mg" in n.corpo and "WhatsApp" in n.corpo


def test_confirmacao_de_sintoma_pede_resposta_e_cita_192():
    n = notificacao_confirmacao_sintoma(["tontura"])
    assert n.assunto == "Zela+: você está bem?"
    assert "ESTOU BEM" in n.corpo and "60" in n.corpo and "192" in n.corpo and "tontura" in n.corpo


def test_confirmacao_sem_sintoma_nomeado_continua_legivel():
    n = notificacao_confirmacao_sintoma([])
    assert "ESTOU BEM" in n.corpo and "  " not in n.corpo


def test_checagem_repete_a_mensagem_do_alerta():
    n = notificacao_checagem("Tudo bem? Detectamos: ESP32 parado.")
    assert n.assunto == "Zela+: está tudo bem?"
    assert n.corpo.startswith("Tudo bem? Detectamos: ESP32 parado.")


@pytest.mark.parametrize(
    "notificacao",
    [
        notificacao_lembrete_remedio(_dipirona()),
        notificacao_confirmacao_sintoma(["tontura", "dor no peito"]),
        notificacao_checagem("x"),
    ],
)
def test_assunto_cabe_na_pulseira(notificacao):
    assert len(notificacao.assunto) <= 40
