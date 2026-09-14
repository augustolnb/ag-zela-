from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from zela.domain.comunicacao import formatar_lembrete
from zela.storage.db import conectar
from zela.storage.perfil import obter_perfil
from zela.storage.rotina import aplicar_lembretes_pendentes

INTERVALO_MINUTOS = 5


def verificar_e_enviar_lembretes(caminho_db: str, id_idoso: str, waha_client) -> list[str]:
    conn = conectar(caminho_db)
    perfil = obter_perfil(conn, id_idoso)
    if perfil is None:
        return []

    agora = datetime.now()
    pendentes = aplicar_lembretes_pendentes(conn, id_idoso, agora)

    enviadas = []
    for medicamento in pendentes:
        texto = formatar_lembrete(medicamento)
        waha_client.enviar_texto(perfil.telefone, texto)
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
