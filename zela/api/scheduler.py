import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from zela.domain.compromisso_lembretes import (
    calcular_overrides_minutos_google,
    lembretes_compromisso_pendentes,
)
from zela.domain.comunicacao import formatar_lembrete, formatar_lembrete_compromisso
from zela.domain.rotina import JANELA_LEMBRETE
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.models.monitoramento import EventoMonitoramento, StatusMonitoramento
from zela.models.perfil import PerfilIdoso
from zela.storage.alertas import salvar_alerta
from zela.storage.db import conectar
from zela.storage.escalonamento import aplicar_escalonamento
from zela.storage.monitoramento import MOTIVO_SEM_DADOS_PREFIXO, aplicar_classificacao
from zela.storage.perfil import obter_perfil
from zela.storage.rotina import (
    aplicar_lembretes_pendentes,
    listar_compromissos,
    listar_compromissos_pendentes_sync_google,
    listar_compromissos_removidos_pendentes_cancelamento,
    listar_tipos_lembrete_enviados,
    marcar_google_sync_feito,
    registrar_lembrete_compromisso_enviado,
)

logger = logging.getLogger(__name__)

INTERVALO_MINUTOS = 5
INTERVALO_MONITORAMENTO_MINUTOS = 15

# Dedupe em memória de processo: evita reenviar o mesmo lembrete a cada
# execução do scheduler enquanto a dose continuar dentro da janela de
# lembrete. Chave: (medicamento_id, "YYYY-MM-DD:HH:MM:SS" do horário previsto).
# Perder este estado num restart do processo é aceitável (não é pior que o
# comportamento anterior).
_lembretes_ja_enviados: set[tuple[str, str]] = set()


def _horario_atual_pendente(medicamento, agora: datetime):
    """Retorna o horário (time) do medicamento que está dentro da janela de
    lembrete agora, ou None se nenhum horário do medicamento estiver pendente
    neste instante."""
    for horario in medicamento.horarios:
        horario_previsto = agora.replace(
            hour=horario.hour, minute=horario.minute, second=horario.second, microsecond=0
        )
        if horario_previsto <= agora <= horario_previsto + JANELA_LEMBRETE:
            return horario
    return None


def verificar_e_enviar_lembretes(caminho_db: str, id_idoso: str, waha_client) -> list[str]:
    conn = conectar(caminho_db)
    perfil = obter_perfil(conn, id_idoso)
    if perfil is None:
        return []

    agora = datetime.now()
    pendentes = aplicar_lembretes_pendentes(conn, id_idoso, agora)

    enviadas = []
    for medicamento in pendentes:
        horario = _horario_atual_pendente(medicamento, agora)
        if horario is None:
            continue
        chave = (medicamento.id, f"{agora.date()}:{horario.isoformat()}")
        if chave in _lembretes_ja_enviados:
            continue
        texto = formatar_lembrete(medicamento)
        waha_client.enviar_texto(perfil.lid_whatsapp or perfil.telefone, texto)
        _lembretes_ja_enviados.add(chave)
        enviadas.append(texto)
    return enviadas


def _enviar_para_idoso_e_familia(waha_client, perfil: PerfilIdoso, texto: str) -> None:
    # Cada envio é isolado: se o envio para um destinatário falhar (número
    # inválido, timeout do WAHA etc.), os demais ainda devem receber a
    # mensagem. Sem este try/except por destinatário, uma falha num familiar
    # propagava e abortava o registro do lembrete (ver
    # `registrar_lembrete_compromisso_enviado` no chamador) — o que fazia o
    # mesmo lembrete (inclusive o já entregue com sucesso ao idoso) ser
    # reenviado para todo mundo, a cada tick do scheduler, para sempre.
    try:
        waha_client.enviar_texto(perfil.lid_whatsapp or perfil.telefone, texto)
    except Exception:
        logger.exception("Falha ao enviar lembrete de compromisso para o idoso %s", perfil.nome)
    for contato in perfil.contatos_familiares:
        try:
            waha_client.enviar_texto(contato.telefone, texto)
        except Exception:
            logger.exception(
                "Falha ao enviar lembrete de compromisso para o familiar %s", contato.nome
            )


def verificar_e_enviar_lembretes_compromisso(
    caminho_db: str, id_idoso: str, waha_client
) -> list[str]:
    conn = conectar(caminho_db)
    perfil = obter_perfil(conn, id_idoso)
    if perfil is None:
        return []

    agora = datetime.now()
    enviadas: list[str] = []

    for compromisso in listar_compromissos(conn, id_idoso):
        try:
            tipos_ja_enviados = listar_tipos_lembrete_enviados(conn, compromisso.id)
            for tipo in lembretes_compromisso_pendentes(compromisso, agora, tipos_ja_enviados):
                texto = formatar_lembrete_compromisso(compromisso, tipo)
                _enviar_para_idoso_e_familia(waha_client, perfil, texto)
                registrar_lembrete_compromisso_enviado(conn, compromisso.id, tipo, agora)
                enviadas.append(texto)
        except Exception:
            # Um compromisso com problema (dado inesperado, erro de storage
            # etc.) não pode abortar o processamento dos demais compromissos
            # nem do loop de cancelamento abaixo — mesmo racional do
            # try/except por item já usado em
            # `sincronizar_compromissos_google_agenda`.
            logger.exception(
                "Falha ao processar lembretes do compromisso %s", compromisso.id
            )

    for compromisso in listar_compromissos_removidos_pendentes_cancelamento(conn, id_idoso):
        try:
            texto = formatar_lembrete_compromisso(compromisso, "cancelamento")
            _enviar_para_idoso_e_familia(waha_client, perfil, texto)
            registrar_lembrete_compromisso_enviado(conn, compromisso.id, "cancelamento", agora)
            enviadas.append(texto)
        except Exception:
            logger.exception(
                "Falha ao processar cancelamento do compromisso %s", compromisso.id
            )

    return enviadas


def _telefone_por_nome(perfil: PerfilIdoso, nome: str) -> str | None:
    if nome == perfil.nome:
        return perfil.lid_whatsapp or perfil.telefone
    for contato in perfil.contatos_familiares:
        if contato.nome == nome:
            return contato.telefone
    return None


def despachar_alertas(
    conn, alertas: list[Alerta], perfil: PerfilIdoso, idoso_id: str, waha_client
) -> None:
    for alerta in alertas:
        salvar_alerta(conn, alerta, idoso_id)
        if alerta.simulado:
            continue
        telefone = _telefone_por_nome(perfil, alerta.destinatario)
        if telefone is not None:
            waha_client.enviar_texto(telefone, alerta.mensagem)


def verificar_e_escalonar_riscos(caminho_db: str, id_idoso: str, waha_client) -> list[Alerta]:
    conn = conectar(caminho_db)
    perfil = obter_perfil(conn, id_idoso)
    if perfil is None:
        return []

    agora = datetime.now()
    evento: EventoMonitoramento = aplicar_classificacao(conn, id_idoso, agora)

    # Caso técnico "sem dados" (nenhuma leitura de presença na janela de
    # lookback — instalação nova, sensor/WiFi fora do ar etc.): isso NÃO é
    # uma classificação de risco real, então não pode entrar na escada de
    # escalonamento (`aplicar_escalonamento`/`decidir_proxima_acao` tratam
    # qualquer status != NORMAL como início/continuação da escalada). Em vez
    # disso, avisamos a família uma vez, com nível INFO, e paramos aqui.
    if evento.status == StatusMonitoramento.ATENCAO and evento.motivo.startswith(
        MOTIVO_SEM_DADOS_PREFIXO
    ):
        contato = perfil.contatos_familiares[0]
        alerta = Alerta(
            nivel=NivelAlerta.INFO,
            destinatario=contato.nome,
            canal=CanalAlerta.WHATSAPP,
            mensagem=f"Aviso: {evento.motivo}.",
            timestamp=agora,
        )
        salvar_alerta(conn, alerta, id_idoso)
        waha_client.enviar_texto(contato.telefone, alerta.mensagem)
        return [alerta]

    alertas = aplicar_escalonamento(conn, id_idoso, evento, perfil, agora)
    despachar_alertas(conn, alertas, perfil, id_idoso, waha_client)
    return alertas


def sincronizar_compromissos_google_agenda(
    caminho_db: str, id_idoso: str, google_calendar_client
) -> list[str]:
    conn = conectar(caminho_db)
    agora = datetime.now()
    sincronizados = []
    for pendente in listar_compromissos_pendentes_sync_google(conn, id_idoso):
        try:
            if pendente.removido:
                if pendente.google_event_id:
                    google_calendar_client.remover_evento(pendente.google_event_id)
                marcar_google_sync_feito(conn, pendente.compromisso.id)
            else:
                minutos = calcular_overrides_minutos_google(pendente.compromisso, agora)
                if pendente.google_event_id is None:
                    event_id = google_calendar_client.criar_evento(
                        pendente.compromisso.titulo,
                        pendente.compromisso.local,
                        pendente.compromisso.data_hora,
                        minutos,
                    )
                    marcar_google_sync_feito(conn, pendente.compromisso.id, google_event_id=event_id)
                else:
                    google_calendar_client.atualizar_evento(
                        pendente.google_event_id,
                        pendente.compromisso.titulo,
                        pendente.compromisso.local,
                        pendente.compromisso.data_hora,
                        minutos,
                    )
                    marcar_google_sync_feito(conn, pendente.compromisso.id)
            sincronizados.append(pendente.compromisso.id)
        except Exception:
            logger.exception(
                "Falha ao sincronizar compromisso %s com o Google Agenda", pendente.compromisso.id
            )
    return sincronizados


def iniciar_scheduler(
    caminho_db: str, id_idoso: str, waha_client, google_calendar_client=None
) -> BackgroundScheduler:
    agendador = BackgroundScheduler()
    agendador.add_job(
        verificar_e_enviar_lembretes,
        "interval",
        minutes=INTERVALO_MINUTOS,
        args=[caminho_db, id_idoso, waha_client],
        id="verificar_lembretes",
    )
    agendador.add_job(
        verificar_e_enviar_lembretes_compromisso,
        "interval",
        minutes=INTERVALO_MINUTOS,
        args=[caminho_db, id_idoso, waha_client],
        id="verificar_lembretes_compromisso",
    )
    agendador.add_job(
        verificar_e_escalonar_riscos,
        "interval",
        minutes=INTERVALO_MONITORAMENTO_MINUTOS,
        args=[caminho_db, id_idoso, waha_client],
        id="verificar_riscos",
    )
    if google_calendar_client is not None:
        agendador.add_job(
            sincronizar_compromissos_google_agenda,
            "interval",
            minutes=INTERVALO_MINUTOS,
            args=[caminho_db, id_idoso, google_calendar_client],
            id="sincronizar_compromissos_google_agenda",
        )
    agendador.start()
    return agendador
