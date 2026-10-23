import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from zela.api.aviso_familia import processar_episodios
from zela.domain.compromisso_lembretes import lembretes_compromisso_pendentes
from zela.domain.comunicacao import formatar_lembrete, formatar_lembrete_compromisso
from zela.domain.emergencia import EstadoEscalonamento, EstagioEscalonamento
from zela.domain.rotina import JANELA_LEMBRETE
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta, StatusAlerta
from zela.models.monitoramento import EventoMonitoramento, StatusMonitoramento
from zela.models.perfil import PerfilIdoso
from zela.storage.alertas import salvar_alerta
from zela.storage.db import conectar
from zela.storage.escalonamento import aplicar_escalonamento, obter_estado, salvar_estado
from zela.storage.monitoramento import aplicar_classificacao, avaliar_sono_recente
from zela.storage.perfil import obter_perfil
from zela.storage.rotina import (
    aplicar_lembretes_pendentes,
    listar_compromissos,
    listar_compromissos_removidos_pendentes_cancelamento,
    listar_tipos_lembrete_enviados,
    registrar_lembrete_compromisso_enviado,
)

logger = logging.getLogger(__name__)

INTERVALO_MINUTOS = 5
INTERVALO_MONITORAMENTO_MINUTOS = 15
INTERVALO_EPISODIOS_SEGUNDOS = 10
INTERVALO_REINDEXACAO_SEGUNDOS = 60

# Dedupe em memória de processo: evita reenviar o mesmo lembrete a cada
# execução do scheduler enquanto a dose continuar dentro da janela de
# lembrete. Chave: (medicamento_id, "YYYY-MM-DD:HH:MM:SS" do horário previsto).
# Perder este estado num restart do processo é aceitável (não é pior que o
# comportamento anterior).
_lembretes_ja_enviados: set[tuple[str, str]] = set()

# Dedupe em memória de processo dos AVISOs, como `_lembretes_ja_enviados`: a
# verificação roda a cada 15 min e a família só deve receber a mensagem uma vez
# por episódio. Chave: (id_idoso, motivo) ou (id_idoso, "sono:YYYY-MM-DD").
_avisos_ja_enviados: set[tuple[str, str]] = set()
_PREFIXO_CHAVE_SONO = "sono:"


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
    waha_client.enviar_texto(perfil.lid_whatsapp or perfil.telefone, texto)
    for contato in perfil.contatos_familiares:
        waha_client.enviar_texto(contato.telefone, texto)


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
        tipos_ja_enviados = listar_tipos_lembrete_enviados(conn, compromisso.id)
        for tipo in lembretes_compromisso_pendentes(compromisso, agora, tipos_ja_enviados):
            texto = formatar_lembrete_compromisso(compromisso, tipo)
            _enviar_para_idoso_e_familia(waha_client, perfil, texto)
            registrar_lembrete_compromisso_enviado(conn, compromisso.id, tipo, agora)
            enviadas.append(texto)

    for compromisso in listar_compromissos_removidos_pendentes_cancelamento(conn, id_idoso):
        texto = formatar_lembrete_compromisso(compromisso, "cancelamento")
        _enviar_para_idoso_e_familia(waha_client, perfil, texto)
        registrar_lembrete_compromisso_enviado(conn, compromisso.id, "cancelamento", agora)
        enviadas.append(texto)

    return enviadas


def _telefone_por_nome(perfil: PerfilIdoso, nome: str) -> str | None:
    if nome == perfil.nome:
        return perfil.lid_whatsapp or perfil.telefone
    for contato in perfil.contatos_familiares:
        if contato.nome == nome:
            return contato.telefone
    return None


def _tentar_enviar(waha_client, telefone: str, alerta: Alerta) -> bool:
    try:
        waha_client.enviar_texto(telefone, alerta.mensagem)
    except Exception:
        logger.exception("Falha ao enviar alerta para %s", alerta.destinatario)
        return False
    return True


def despachar_alertas(
    conn, alertas: list[Alerta], perfil: PerfilIdoso, idoso_id: str, waha_client
) -> None:
    for alerta in alertas:
        telefone = None if alerta.simulado else _telefone_por_nome(perfil, alerta.destinatario)
        if telefone is not None and not _tentar_enviar(waha_client, telefone, alerta):
            alerta = alerta.model_copy(update={"status": StatusAlerta.FALHOU})
        salvar_alerta(conn, alerta, idoso_id)


def _enviar_aviso(
    conn, perfil: PerfilIdoso, idoso_id: str, motivo: str, chave: tuple[str, str], agora: datetime, waha_client
) -> list[Alerta]:
    if chave in _avisos_ja_enviados or not perfil.contatos_familiares:
        return []
    contato = perfil.contatos_familiares[0]
    alerta = Alerta(
        nivel=NivelAlerta.INFO,
        destinatario=contato.nome,
        canal=CanalAlerta.WHATSAPP,
        mensagem=f"Aviso: {motivo}.",
        timestamp=agora,
    )
    if not _tentar_enviar(waha_client, contato.telefone, alerta):
        # Sem marcar em `_avisos_ja_enviados`: a próxima verificação tenta de novo.
        alerta = alerta.model_copy(update={"status": StatusAlerta.FALHOU})
        salvar_alerta(conn, alerta, idoso_id)
        return [alerta]
    salvar_alerta(conn, alerta, idoso_id)
    _avisos_ja_enviados.add(chave)
    return [alerta]


def verificar_e_escalonar_riscos(caminho_db: str, id_idoso: str, waha_client) -> list[Alerta]:
    conn = conectar(caminho_db)
    perfil = obter_perfil(conn, id_idoso)
    if perfil is None:
        return []

    agora = datetime.now()
    evento: EventoMonitoramento = aplicar_classificacao(conn, id_idoso, agora)

    # AVISO é falha de uma só fonte, não uma classificação de risco: não pode
    # entrar na escada de escalonamento (`decidir_proxima_acao` trata qualquer
    # status != NORMAL como início/continuação da escalada). Uma das fontes
    # está viva, então uma escada aberta é encerrada; um novo RISCO recomeça
    # perguntando à própria idosa.
    if evento.status == StatusMonitoramento.AVISO:
        estado = obter_estado(conn, id_idoso)
        if estado.estagio not in (EstagioEscalonamento.OCIOSO, EstagioEscalonamento.RESOLVIDO):
            salvar_estado(conn, id_idoso, EstadoEscalonamento(estagio=EstagioEscalonamento.RESOLVIDO))
        return _enviar_aviso(conn, perfil, id_idoso, evento.motivo, (id_idoso, evento.motivo), agora, waha_client)

    if evento.status == StatusMonitoramento.NORMAL:
        for chave in list(_avisos_ja_enviados):
            if chave[0] == id_idoso and not chave[1].startswith(_PREFIXO_CHAVE_SONO):
                _avisos_ja_enviados.discard(chave)

    alertas = aplicar_escalonamento(conn, id_idoso, evento, perfil, agora)
    despachar_alertas(conn, alertas, perfil, id_idoso, waha_client)
    return alertas


def verificar_sono_e_avisar(caminho_db: str, id_idoso: str, waha_client) -> list[Alerta]:
    conn = conectar(caminho_db)
    perfil = obter_perfil(conn, id_idoso)
    if perfil is None:
        return []

    agora = datetime.now()
    evento = avaliar_sono_recente(conn, id_idoso, agora)
    if evento is None:
        return []
    chave = (id_idoso, f"{_PREFIXO_CHAVE_SONO}{agora.date()}")
    return _enviar_aviso(conn, perfil, id_idoso, evento.motivo, chave, agora, waha_client)


def iniciar_scheduler(caminho_db: str, id_idoso: str, waha_client, reindexar=None) -> BackgroundScheduler:
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
    agendador.add_job(
        verificar_sono_e_avisar,
        "cron",
        hour=9,
        minute=0,
        args=[caminho_db, id_idoso, waha_client],
        id="verificar_sono",
        misfire_grace_time=3600,
    )
    agendador.add_job(
        processar_episodios,
        "interval",
        seconds=INTERVALO_EPISODIOS_SEGUNDOS,
        args=[caminho_db, id_idoso, waha_client],
        id="processar_episodios",
    )
    if reindexar is not None:
        # Em segundo plano desde o início: embeddings não podem atrasar o boot da API.
        agendador.add_job(
            reindexar, "interval", seconds=INTERVALO_REINDEXACAO_SEGUNDOS,
            id="reindexar_documentos", next_run_time=datetime.now(),
        )
    agendador.start()
    return agendador
