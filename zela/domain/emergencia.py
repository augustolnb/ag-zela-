from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.models.monitoramento import EventoMonitoramento, StatusMonitoramento
from zela.models.perfil import PerfilIdoso


class EstagioEscalonamento(str, Enum):
    OCIOSO = "ocioso"
    CONTATO_IDOSO = "contato_idoso"
    NOTIFICAR_FAMILIA = "notificar_familia"
    SIMULAR_EMERGENCIA = "simular_emergencia"
    RESOLVIDO = "resolvido"


@dataclass
class EstadoEscalonamento:
    estagio: EstagioEscalonamento = EstagioEscalonamento.OCIOSO
    iniciado_em: datetime | None = None


JANELA_CONTATO_IDOSO = timedelta(minutes=10)
JANELA_NOTIFICAR_FAMILIA = timedelta(minutes=15)


def decidir_proxima_acao(
    evento: EventoMonitoramento,
    perfil: PerfilIdoso,
    estado: EstadoEscalonamento,
    agora: datetime,
) -> tuple[EstadoEscalonamento, list[Alerta]]:
    if evento.status == StatusMonitoramento.NORMAL:
        return EstadoEscalonamento(estagio=EstagioEscalonamento.RESOLVIDO), []

    if estado.estagio in (EstagioEscalonamento.OCIOSO, EstagioEscalonamento.RESOLVIDO) or estado.iniciado_em is None:
        novo_estado = EstadoEscalonamento(estagio=EstagioEscalonamento.CONTATO_IDOSO, iniciado_em=agora)
        alerta = Alerta(
            nivel=NivelAlerta.ATENCAO,
            destinatario=perfil.nome,
            canal=CanalAlerta.WHATSAPP,
            mensagem=f"Tudo bem? Detectamos: {evento.motivo}. Pode confirmar que está tudo certo?",
            timestamp=agora,
        )
        return novo_estado, [alerta]

    tempo_decorrido = agora - estado.iniciado_em

    if estado.estagio == EstagioEscalonamento.CONTATO_IDOSO:
        if tempo_decorrido < JANELA_CONTATO_IDOSO:
            return estado, []
        novo_estado = EstadoEscalonamento(estagio=EstagioEscalonamento.NOTIFICAR_FAMILIA, iniciado_em=agora)
        alertas = [
            Alerta(
                nivel=NivelAlerta.CRITICO,
                destinatario=contato.nome,
                canal=CanalAlerta.WHATSAPP,
                mensagem=f"Atenção: {perfil.nome} não respondeu. Motivo do alerta: {evento.motivo}.",
                timestamp=agora,
            )
            for contato in perfil.contatos_familiares
        ]
        return novo_estado, alertas

    if estado.estagio == EstagioEscalonamento.NOTIFICAR_FAMILIA:
        if tempo_decorrido < JANELA_NOTIFICAR_FAMILIA:
            return estado, []
        novo_estado = EstadoEscalonamento(estagio=EstagioEscalonamento.SIMULAR_EMERGENCIA, iniciado_em=agora)
        alerta = Alerta(
            nivel=NivelAlerta.CRITICO,
            destinatario="servico_emergencia_simulado",
            canal=CanalAlerta.WHATSAPP,
            mensagem=(
                f"[SIMULAÇÃO] Acionamento de serviço de emergência para {perfil.nome}. "
                f"Motivo: {evento.motivo}. Nenhuma ligação real foi realizada."
            ),
            timestamp=agora,
            simulado=True,
        )
        return novo_estado, [alerta]

    return estado, []
