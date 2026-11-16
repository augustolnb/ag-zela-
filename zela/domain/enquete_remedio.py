"""Lembrete de remédio como enquete do WhatsApp ("✅ Tomei" / "⏰ Ainda não").

O WAHA (WhatsApp Web) não envia botões que funcionem; a enquete é o mais
perto de um botão que o idoso só precisa tocar.
"""

from datetime import timedelta

from zela.models.rotina import Medicamento

OPCAO_TOMEI = "✅ Tomei"
OPCAO_AINDA_NAO = "⏰ Ainda não"
OPCOES = [OPCAO_TOMEI, OPCAO_AINDA_NAO]

INTERVALO_RELEMBRAR = timedelta(minutes=30)
RESPOSTA_AINDA_NAO = "Tudo bem! Te lembro de novo em 30 minutos."
RESPOSTA_AINDA_NAO_SEM_REENVIO = "Tudo bem! Quando tomar, é só tocar em ✅ Tomei ou me escrever 'tomei'."


def pergunta_lembrete(medicamento: Medicamento) -> str:
    dose = f"{medicamento.dosagem.quantidade} {medicamento.dosagem.unidade}"
    return f"Hora de tomar {medicamento.nome} ({dose}). Já tomou?"


def resposta_tomei(medicamento: Medicamento) -> str:
    return f"Anotado! ✅ Dose de {medicamento.nome} registrada."


def chave_da_mensagem(identificador: str | dict) -> str:
    """Identificador da mensagem da enquete, sem prefixos.

    A resposta do sendPoll e o `poll.id` do voto podem trazer prefixos
    diferentes ("true_<chat>_<id>"); a parte depois do último "_" é a mesma
    nos dois (verificado em produção em 15/11/2026).
    """
    if isinstance(identificador, dict):
        identificador = identificador.get("_serialized", "")
    return str(identificador).rsplit("_", 1)[-1]


def interpretar_voto(selecionadas: list[str]) -> str | None:
    if OPCAO_TOMEI in selecionadas:
        return "tomei"
    if OPCAO_AINDA_NAO in selecionadas:
        return "ainda_nao"
    return None
