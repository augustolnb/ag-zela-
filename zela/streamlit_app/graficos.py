from datetime import datetime

import altair as alt
import pandas as pd

from zela.models.monitoramento import LeituraSensor, TipoLeitura
from zela.streamlit_app.estilo import AMARELO_DESTAQUE, BRANCO

COM_MOVIMENTO = "Com movimento"
SEM_MOVIMENTO = "Sem movimento"

# Claro: azul primário do tema contra cinza suave. Noturno: amarelo de
# destaque contra um azul um pouco mais claro que o cartão.
_CORES = {
    False: {"com": "#2563EB", "sem": "#E2E8F0", "texto": "#475569"},
    True: {"com": AMARELO_DESTAQUE, "sem": "#24406B", "texto": BRANCO},
}

ALTURA_FAIXA = 44


def montar_faixas_presenca(leituras: list[LeituraSensor], agora: datetime) -> list[dict]:
    """Transforma as leituras de presença em faixas contínuas de estado.

    O ESP32 só envia leitura quando o estado muda, então cada leitura vale
    até a próxima, e a última vale até agora. Leituras seguidas com o mesmo
    estado viram uma faixa só.
    """
    presencas = sorted(
        (l for l in leituras if l.tipo == TipoLeitura.PRESENCA), key=lambda l: l.timestamp
    )
    faixas: list[dict] = []
    for leitura in presencas:
        estado = COM_MOVIMENTO if leitura.valor >= 1 else SEM_MOVIMENTO
        if faixas and faixas[-1]["estado"] == estado:
            continue
        if faixas:
            faixas[-1]["fim"] = leitura.timestamp
        faixas.append({"inicio": leitura.timestamp, "fim": agora, "estado": estado})
    return faixas


def _duracao(inicio: datetime, fim: datetime) -> str:
    minutos = max(0, round((fim - inicio).total_seconds() / 60))
    horas, minutos = divmod(minutos, 60)
    return f"{horas}h{minutos:02d}min" if horas else f"{minutos} min"


def grafico_presenca(faixas: list[dict], noturno: bool = False) -> alt.Chart:
    cores = _CORES[noturno]
    dados = pd.DataFrame(faixas)
    dados["linha"] = "Presença"
    dados["de"] = dados["inicio"].dt.strftime("%H:%M")
    dados["ate"] = dados["fim"].dt.strftime("%H:%M")
    dados["duracao"] = [_duracao(f["inicio"], f["fim"]) for f in faixas]

    return (
        alt.Chart(dados, height=ALTURA_FAIXA)
        .mark_bar(cornerRadius=6, height=ALTURA_FAIXA - 8)
        .encode(
            x=alt.X(
                "inicio:T", title=None,
                axis=alt.Axis(format="%H:%M", grid=False, domain=False, tickCount=6,
                              labelColor=cores["texto"], tickColor=cores["texto"]),
            ),
            x2="fim:T",
            y=alt.Y("linha:N", title=None, axis=None),
            color=alt.Color(
                "estado:N", title=None,
                scale=alt.Scale(domain=[COM_MOVIMENTO, SEM_MOVIMENTO],
                                range=[cores["com"], cores["sem"]]),
                legend=alt.Legend(orient="bottom", labelColor=cores["texto"],
                                  symbolType="circle"),
            ),
            tooltip=[
                alt.Tooltip("estado:N", title="Estado"),
                alt.Tooltip("de:N", title="De"),
                alt.Tooltip("ate:N", title="Até"),
                alt.Tooltip("duracao:N", title="Duração"),
            ],
        )
        .configure(background="transparent", view={"stroke": "transparent"})
    )
