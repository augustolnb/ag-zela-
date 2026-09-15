from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from zela.domain.comunicacao import formatar_lembrete
from zela.domain.rotina import JANELA_LEMBRETE
from zela.storage.db import conectar
from zela.storage.perfil import obter_perfil
from zela.storage.rotina import aplicar_lembretes_pendentes

INTERVALO_MINUTOS = 5

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


def iniciar_scheduler(caminho_db: str, id_idoso: str, waha_client) -> BackgroundScheduler:
    agendador = BackgroundScheduler()
    agendador.add_job(
        verificar_e_enviar_lembretes,
        "interval",
        minutes=INTERVALO_MINUTOS,
        args=[caminho_db, id_idoso, waha_client],
        id="verificar_lembretes",
    )
    agendador.start()
    return agendador
