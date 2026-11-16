"""Histórico do painel: avisos, compromissos e doses de remédio numa lista só."""

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

from zela.models.alertas import Alerta
from zela.models.rotina import Compromisso, ConfirmacaoMedicacao, Medicamento, StatusConfirmacao

TIPO_AVISO = "Aviso"
TIPO_COMPROMISSO = "Compromisso"
TIPO_MEDICACAO = "Medicação"
TIPOS = [TIPO_AVISO, TIPO_COMPROMISSO, TIPO_MEDICACAO]

_ROTULOS_NIVEL = {"info": "INFO", "atencao": "ATENÇÃO", "critico": "CRÍTICO"}
_ROTULOS_DOSE = {
    StatusConfirmacao.CONFIRMADO: "Tomado",
    StatusConfirmacao.ATRASADO: "Tomado com atraso",
    StatusConfirmacao.NAO_CONFIRMADO: "Não confirmado",
}


@dataclass(frozen=True)
class ItemHistorico:
    data_hora: datetime
    tipo: str
    descricao: str
    situacao: str


def _item_alerta(alerta: Alerta) -> ItemHistorico:
    situacao = f"{_ROTULOS_NIVEL.get(alerta.nivel.value, alerta.nivel.value)} · para {alerta.destinatario} · {alerta.status.value}"
    if alerta.simulado:
        situacao += " · simulado"
    return ItemHistorico(alerta.timestamp, TIPO_AVISO, alerta.mensagem, situacao)


def _item_compromisso(compromisso: Compromisso, removido: bool, agora: datetime) -> ItemHistorico:
    if removido:
        situacao = "Removido"
    elif compromisso.data_hora < agora:
        situacao = "Realizado"
    else:
        situacao = "Agendado"
    descricao = f"{compromisso.titulo} ({compromisso.tipo.value}, {compromisso.local})"
    return ItemHistorico(compromisso.data_hora, TIPO_COMPROMISSO, descricao, situacao)


def _item_dose(confirmacao: ConfirmacaoMedicacao, medicamentos: dict[str, Medicamento]) -> ItemHistorico:
    medicamento = medicamentos.get(confirmacao.medicamento_id)
    if medicamento is not None:
        nome = f"{medicamento.nome} ({medicamento.dosagem.quantidade} {medicamento.dosagem.unidade})"
    else:
        # Remédio já removido do cadastro: o registro continua, pelo id.
        nome = confirmacao.medicamento_id
    descricao = f"{nome}, previsto às {confirmacao.horario_previsto.strftime('%H:%M')}"
    quando = confirmacao.horario_confirmado or confirmacao.horario_previsto
    return ItemHistorico(quando, TIPO_MEDICACAO, descricao, _ROTULOS_DOSE[confirmacao.status])


def montar_historico(
    alertas: list[Alerta],
    compromissos: list[tuple[Compromisso, bool]],
    confirmacoes: list[ConfirmacaoMedicacao],
    medicamentos: list[Medicamento],
    agora: datetime,
) -> list[ItemHistorico]:
    """Todos os itens, do mais recente ao mais antigo. `compromissos` traz (compromisso, removido)."""
    por_id = {m.id: m for m in medicamentos}
    itens = (
        [_item_alerta(a) for a in alertas]
        + [_item_compromisso(c, removido, agora) for c, removido in compromissos]
        + [_item_dose(c, por_id) for c in confirmacoes]
    )
    return sorted(itens, key=lambda item: item.data_hora, reverse=True)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold().strip()


def filtrar_historico(
    itens: list[ItemHistorico],
    dia: date | None = None,
    busca: str = "",
    tipos: set[str] | None = None,
) -> list[ItemHistorico]:
    """Filtros combinados: dia exato, texto na descrição (sem acento/maiúscula) e tipos."""
    termo = _normalizar(busca or "")
    return [
        item
        for item in itens
        if (dia is None or item.data_hora.date() == dia)
        and (not termo or termo in _normalizar(item.descricao))
        and (tipos is None or item.tipo in tipos)
    ]
