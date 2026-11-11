"""Textos das notificações espelhadas na pulseira via Gmail.

A tela da pulseira é pequena: o assunto precisa caber em até 40 caracteres.
"""

from dataclasses import dataclass

from zela.models.rotina import Medicamento

LIMITE_ASSUNTO = 40


@dataclass(frozen=True)
class NotificacaoPulseira:
    assunto: str
    corpo: str


def notificacao_lembrete_remedio(medicamento: Medicamento) -> NotificacaoPulseira:
    dose = f"{medicamento.dosagem.quantidade:g} {medicamento.dosagem.unidade}"
    return NotificacaoPulseira(
        assunto="Zela+: hora do remédio",
        corpo=f"Hora de tomar {medicamento.nome} ({dose}). Responda TOMEI no WhatsApp.",
    )


def notificacao_confirmacao_sintoma(sintomas: list[str]) -> NotificacaoPulseira:
    relato = f"Você relatou {', '.join(sintomas)}. " if sintomas else ""
    return NotificacaoPulseira(
        assunto="Zela+: você está bem?",
        corpo=(
            f"{relato}Responda ESTOU BEM no WhatsApp em 60 segundos ou sua família será avisada. "
            "Em emergência, ligue 192."
        ),
    )


def notificacao_checagem(mensagem: str) -> NotificacaoPulseira:
    return NotificacaoPulseira(
        assunto="Zela+: está tudo bem?",
        corpo=f"{mensagem} Responda no WhatsApp.",
    )
