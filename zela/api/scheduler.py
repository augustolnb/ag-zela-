from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from zela.domain.comunicacao import formatar_lembrete
from zela.domain.rotina import JANELA_LEMBRETE
from zela.models.alertas import Alerta, CanalAlerta, NivelAlerta
from zela.models.monitoramento import EventoMonitoramento, StatusMonitoramento
from zela.models.perfil import PerfilIdoso
from zela.storage.alertas import salvar_alerta
from zela.storage.db import conectar
from zela.storage.escalonamento import aplicar_escalonamento
from zela.storage.monitoramento import MOTIVO_SEM_DADOS_PREFIXO, aplicar_classificacao
from zela.storage.perfil import obter_perfil
from zela.storage.rotina import aplicar_lembretes_pendentes

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
        waha_client.enviar_texto(perfil.telefone, texto)
        _lembretes_ja_enviados.add(chave)
        enviadas.append(texto)
    return enviadas


def _telefone_por_nome(perfil: PerfilIdoso, nome: str) -> str | None:
    if nome == perfil.nome:
        return perfil.telefone
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


def iniciar_scheduler(caminho_db: str, id_idoso: str, waha_client) -> BackgroundScheduler:
    agendador = BackgroundScheduler()
    agendador.add_job(
        verificar_e_enviar_lembretes,
        "interval",
        minutes=INTERVALO_MINUTOS,
        args=[caminho_db, id_idoso, waha_client],
        id="verificar_lembretes",
    )
    agendador.add_job(
        verificar_e_escalonar_riscos,
        "interval",
        minutes=INTERVALO_MONITORAMENTO_MINUTOS,
        args=[caminho_db, id_idoso, waha_client],
        id="verificar_riscos",
    )
    agendador.start()
    return agendador
