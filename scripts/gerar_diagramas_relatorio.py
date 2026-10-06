"""Gera os diagramas PNG usados em docs/relatorio/RELATORIO_SISTEMA.md.

Uso:
    python scripts/gerar_diagramas_relatorio.py

Desenhados à mão com Pillow (sem depender de graphviz/mermaid, que não
estão disponíveis no ambiente) — regenere sempre que o layout mudar.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).parent.parent
DIR_FONTES = Path(__file__).parent / "fontes"
DIR_SAIDA = RAIZ / "docs" / "relatorio" / "imagens"

FONTE_TITULO = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans-Bold.ttf"), 22)
FONTE_CAIXA = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans-Bold.ttf"), 15)
FONTE_SUB = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans.ttf"), 12)
FONTE_LEGENDA = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans.ttf"), 11)

BRANCO = "white"
PRETO = "#222222"
CINZA_BORDA = "#555555"

COR_AGENTE = "#DCE9F9"
COR_CANAL = "#FDEBD0"
COR_DADOS = "#E2F0D9"
COR_DECISAO = "#F9E2E2"
COR_EXTERNO = "#EDEDED"


def _altura_linha(desenho, fonte):
    bbox = desenho.textbbox((0, 0), "Ag", font=fonte)
    return bbox[3] - bbox[1]


def _bloco_texto(desenho, cx, y_topo, linhas, fonte, cor=PRETO):
    """Desenha linhas empilhadas a partir de y_topo; devolve o y logo abaixo."""
    altura = _altura_linha(desenho, fonte)
    y = y_topo
    for linha in linhas:
        largura = desenho.textbbox((0, 0), linha, font=fonte)[2]
        desenho.text((cx - largura / 2, y), linha, font=fonte, fill=cor)
        y += altura + 5
    return y


def caixa(desenho, xy, linhas, cor_fundo, fonte=FONTE_CAIXA, fonte_sub=None, linhas_sub=None):
    x0, y0, x1, y1 = xy
    desenho.rounded_rectangle(xy, radius=10, fill=cor_fundo, outline=CINZA_BORDA, width=2)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    fonte_sub = fonte_sub or FONTE_SUB
    linhas_sub = linhas_sub or []

    altura_titulo = len(linhas) * (_altura_linha(desenho, fonte) + 5) - 5
    altura_sub = (len(linhas_sub) * (_altura_linha(desenho, fonte_sub) + 5) - 5) if linhas_sub else 0
    espaco_entre = 8 if linhas_sub else 0
    altura_total = altura_titulo + espaco_entre + altura_sub

    y = cy - altura_total / 2
    y = _bloco_texto(desenho, cx, y, linhas, fonte)
    if linhas_sub:
        _bloco_texto(desenho, cx, y + espaco_entre - 5, linhas_sub, fonte_sub, cor="#333333")
    return (cx, cy)


def diamante(desenho, centro_xy, largura, altura, linhas):
    cx, cy = centro_xy
    pontos = [
        (cx, cy - altura / 2),
        (cx + largura / 2, cy),
        (cx, cy + altura / 2),
        (cx - largura / 2, cy),
    ]
    desenho.polygon(pontos, fill=COR_DECISAO, outline=CINZA_BORDA, width=2)
    altura_bloco = len(linhas) * (_altura_linha(desenho, FONTE_SUB) + 5) - 5
    _bloco_texto(desenho, cx, cy - altura_bloco / 2, linhas, FONTE_SUB)


def seta(desenho, p1, p2, cor=PRETO, largura=2, rotulo=None, deslocamento_rotulo=(0, -10)):
    desenho.line([p1, p2], fill=cor, width=largura)
    import math

    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    tam = 9
    for delta in (0.5, -0.5):
        p = (
            p2[0] - tam * math.cos(ang - delta),
            p2[1] - tam * math.sin(ang - delta),
        )
        desenho.line([p2, p], fill=cor, width=largura)
    if rotulo:
        mx, my = (p1[0] + p2[0]) / 2 + deslocamento_rotulo[0], (p1[1] + p2[1]) / 2 + deslocamento_rotulo[1]
        desenho.text((mx, my), rotulo, font=FONTE_LEGENDA, fill="#444444")


def legenda(desenho, xy, itens):
    x, y = xy
    for cor, texto in itens:
        desenho.rectangle([x, y, x + 16, y + 16], fill=cor, outline=CINZA_BORDA)
        desenho.text((x + 24, y), texto, font=FONTE_LEGENDA, fill=PRETO)
        y += 24


# ---------------------------------------------------------------------------
# Diagrama 1: arquitetura multiagente
# ---------------------------------------------------------------------------

def gerar_arquitetura_agentes():
    img = Image.new("RGB", (1000, 870), BRANCO)
    d = ImageDraw.Draw(img)
    d.text((30, 20), "Arquitetura multiagente do Zela+", font=FONTE_TITULO, fill=PRETO)

    caixa(d, (30, 90, 230, 150), ["WhatsApp"], COR_CANAL, linhas_sub=["idoso: texto/áudio"])
    caixa(d, (770, 90, 970, 150), ["Streamlit"], COR_CANAL, linhas_sub=["painel da família"])
    caixa(d, (330, 90, 670, 150), ["Agente de Comunicação"], COR_AGENTE, linhas_sub=["STT/TTS, roteamento, RAG"])

    seta(d, (230, 120), (330, 120))
    seta(d, (970, 120), (670, 120))

    caixa(d, (380, 230, 620, 290), ["Agente Orquestrador"], COR_AGENTE, linhas_sub=["ADK root agent"])
    seta(d, (500, 150), (500, 230))

    y0_sub, y1_sub = 380, 500
    caixa(d, (50, y0_sub, 335, y1_sub), ["Agente de Rotina/Medicação"], COR_AGENTE,
          linhas_sub=["agenda, lembretes,", "confirmações"])
    caixa(d, (360, y0_sub, 640, y1_sub), ["Agente de Monitoramento", "de Saúde/Risco"], COR_AGENTE,
          linhas_sub=["classificação de risco", "por embeddings"])
    caixa(d, (665, y0_sub, 950, y1_sub), ["Agente de", "Emergência/Alertas"], COR_AGENTE,
          linhas_sub=["aciona família /", "serviço emerg. (simulado)"])

    seta(d, (430, 290), (192, y0_sub))
    seta(d, (500, 290), (500, y0_sub))
    seta(d, (570, 290), (807, y0_sub))

    caixa(d, (280, 630, 510, 700), ["Mi Band 9"], COR_EXTERNO, linhas_sub=["Health Connect webhook"])
    caixa(d, (535, 630, 765, 700), ["ESP32 (HC-SR04)"], COR_EXTERNO, linhas_sub=["sensor de presença"])
    seta(d, (410, 630), (460, 500))
    seta(d, (635, 630), (545, 500))

    d.text(
        (30, 790),
        "Decisão de escalonar risco é sempre determinística (zela/domain/emergencia.py),\n"
        "nunca tomada diretamente por um LLM — os agentes só alimentam essa máquina de estados.",
        font=FONTE_SUB,
        fill="#444444",
    )

    img.save(DIR_SAIDA / "arquitetura_agentes.png")


# ---------------------------------------------------------------------------
# Diagrama 2: infraestrutura / implantação
# ---------------------------------------------------------------------------

def gerar_infraestrutura():
    img = Image.new("RGB", (1100, 620), BRANCO)
    d = ImageDraw.Draw(img)
    d.text((30, 20), "Infraestrutura e implantação", font=FONTE_TITULO, fill=PRETO)

    caixa(d, (40, 90, 220, 170), ["WhatsApp"], COR_CANAL, linhas_sub=["app do usuário"])

    d.rounded_rectangle((260, 80, 480, 180), radius=10, outline="#999999", width=2)
    d.text((272, 86), "container Docker", font=FONTE_LEGENDA, fill="#666666")
    caixa(d, (275, 100, 465, 170), ["WAHA"], COR_EXTERNO, linhas_sub=["WhatsApp Web API"])
    seta(d, (220, 130), (275, 130))

    caixa(d, (520, 90, 740, 170), ["Backend FastAPI"], COR_AGENTE, linhas_sub=["uvicorn + ADK"])
    seta(d, (465, 115), (520, 115), rotulo="webhook")
    seta(d, (520, 150), (465, 150), rotulo="sendText")

    caixa(d, (780, 90, 980, 170), ["Gemini / DeepSeek"], COR_EXTERNO, linhas_sub=["LLM + embeddings"])
    seta(d, (740, 130), (780, 130))

    caixa(d, (40, 260, 220, 340), ["n8n"], COR_EXTERNO, linhas_sub=["workflows (classificação,", "captura de debug)"])
    seta(d, (220, 270), (560, 170), rotulo="/api/classificar-mensagem", deslocamento_rotulo=(-60, -18))

    caixa(d, (520, 260, 700, 340), ["SQLite"], COR_DADOS, linhas_sub=["zela.db — perfil, alertas,", "medicamentos, leituras"])
    seta(d, (600, 170), (600, 260))

    caixa(d, (730, 260, 910, 340), ["ChromaDB"], COR_DADOS, linhas_sub=["índice vetorial (RAG)"])
    seta(d, (700, 170), (815, 260))

    caixa(d, (40, 410, 220, 490), ["Streamlit"], COR_CANAL, linhas_sub=["painel da família"])
    seta(d, (220, 420), (540, 340), rotulo="lê o SQLite direto", deslocamento_rotulo=(-50, -18))

    d.text(
        (30, 540),
        "ESP32 (HC-SR04) e Health Connect/Mi Band 9 enviam leituras direto ao Backend\n"
        "(/ingest/esp32, /ingest/health-connect) — ver diagrama de arquitetura de agentes.\n"
        "IPs/portas exatos (gateway do bridge Docker, 0.0.0.0:8000 etc.) variam por ambiente,\n"
        "ver README, seção \"Configurando o WAHA (WhatsApp)\".",
        font=FONTE_SUB,
        fill="#444444",
    )

    img.save(DIR_SAIDA / "infraestrutura.png")


# ---------------------------------------------------------------------------
# Diagrama 3: fluxo de uma mensagem de ponta a ponta
# ---------------------------------------------------------------------------

def gerar_fluxo_mensagem():
    img = Image.new("RGB", (1000, 980), BRANCO)
    d = ImageDraw.Draw(img)
    d.text((30, 20), "Fluxo de uma mensagem do WhatsApp (ponta a ponta)", font=FONTE_TITULO, fill=PRETO)

    c1 = caixa(d, (350, 70, 650, 120), ["Idoso envia mensagem no WhatsApp"], COR_CANAL)
    c2 = caixa(d, (350, 160, 650, 210), ["WAHA recebe e dispara o webhook"], COR_EXTERNO)
    seta(d, (500, 120), (500, 160))

    c3 = caixa(d, (350, 250, 650, 300), ["Backend extrai remetente e texto"], COR_AGENTE,
               linhas_sub=["(telefone @c.us ou LID @lid)"])
    seta(d, (500, 210), (500, 250))

    diamante(d, (500, 370), 280, 110, ["Remetente está na", "lista de permitidos?"])
    seta(d, (500, 300), (500, 315))

    fim_ignorado = caixa(d, (40, 340, 260, 400), ["Mensagem ignorada", '{"status": "ignorado"}'], COR_DECISAO)
    seta(d, (360, 370), (260, 370), rotulo="não")

    c4 = caixa(d, (350, 460, 650, 520), ["Agente ADK processa a mensagem"], COR_AGENTE,
               linhas_sub=["orquestrador → sub-agente certo"])
    seta(d, (500, 425), (500, 460), rotulo="sim")

    c5 = caixa(d, (350, 560, 650, 610), ["Resposta enviada de volta via WAHA"], COR_EXTERNO,
               linhas_sub=["(sendText com o mesmo JID)"])
    seta(d, (500, 520), (500, 560))

    c6 = caixa(d, (350, 650, 650, 700), ["Classificação de risco por embeddings"], COR_AGENTE,
               linhas_sub=["(roda em paralelo, sobre o texto)"])
    seta(d, (500, 610), (500, 650))

    diamante(d, (500, 790), 320, 130, ["Qual o status calculado?", "normal / atenção / risco"])
    seta(d, (500, 700), (500, 725))

    r_normal = caixa(d, (40, 850, 260, 910), ["normal", "nenhuma ação"], COR_DADOS)
    r_atencao = caixa(d, (370, 850, 630, 910), ["atenção", "aviso no painel Streamlit"], COR_DADOS)
    r_risco = caixa(d, (740, 850, 960, 910), ["risco", "escalonamento: idoso → família", "→ emergência (simulado)"], COR_DADOS)

    seta(d, (340, 790), (150, 850), rotulo="normal", deslocamento_rotulo=(-50, -4))
    seta(d, (500, 855), (500, 850), rotulo="atenção", deslocamento_rotulo=(14, -14))
    seta(d, (660, 790), (850, 850), rotulo="risco", deslocamento_rotulo=(10, -4))

    img.save(DIR_SAIDA / "fluxo_mensagem.png")


if __name__ == "__main__":
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    gerar_arquitetura_agentes()
    gerar_infraestrutura()
    gerar_fluxo_mensagem()
    print(f"Diagramas gerados em: {DIR_SAIDA}")
