from dataclasses import dataclass, field
from datetime import datetime

from zela.domain.comunicacao import formatar_lembrete, interpretar_resposta
from zela.domain.emergencia import EstadoEscalonamento, decidir_proxima_acao
from zela.domain.monitoramento import classificar_por_regra
from zela.domain.rotina import calcular_lembretes_pendentes, registrar_confirmacao
from zela.models.alertas import Alerta
from zela.models.comunicacao import MensagemEntrada
from zela.models.monitoramento import LeituraSensor
from zela.models.perfil import PerfilIdoso
from zela.models.rotina import ConfirmacaoMedicacao, Medicamento


@dataclass
class RelatorioSimulacao:
    lembretes_enviados: list[str] = field(default_factory=list)
    confirmacoes: list[ConfirmacaoMedicacao] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)


def simular_dia(
    perfil: PerfilIdoso,
    medicamentos: list[Medicamento],
    leituras: list[LeituraSensor],
    resposta_idoso: MensagemEntrada | None,
    agora: datetime,
) -> RelatorioSimulacao:
    relatorio = RelatorioSimulacao()

    pendentes = calcular_lembretes_pendentes(medicamentos, [], agora)
    for medicamento in pendentes:
        relatorio.lembretes_enviados.append(formatar_lembrete(medicamento))
        if resposta_idoso is not None and interpretar_resposta(resposta_idoso):
            confirmacao = registrar_confirmacao(medicamento, horario_previsto=agora, agora=agora)
            relatorio.confirmacoes.append(confirmacao)

    evento = classificar_por_regra(leituras, agora)
    estado = EstadoEscalonamento()
    _, alertas = decidir_proxima_acao(evento, perfil, estado, agora)
    relatorio.alertas.extend(alertas)

    return relatorio
