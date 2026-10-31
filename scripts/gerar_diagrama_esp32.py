"""Gera o diagrama elétrico ESP32 + 2x PIR SR602 (sala e quarto)
usado em docs/hardware/automacao_esp32.md.

Uso:
    python scripts/gerar_diagrama_esp32.py

Desenhado à mão com Pillow, no mesmo estilo de
scripts/gerar_diagramas_relatorio.py (sem depender de graphviz/schemdraw,
que não estão disponíveis no ambiente) — regenere sempre que a ligação
física mudar.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).parent.parent
DIR_FONTES = Path(__file__).parent / "fontes"
CAMINHO_SAIDA = RAIZ / "docs" / "hardware" / "imagens" / "zela_presenca_diagrama_eletrico.png"

LARGURA, ALTURA = 1500, 700

FONTE_TITULO = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans-Bold.ttf"), 26)
FONTE_SUBTITULO = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans.ttf"), 15)
FONTE_CAIXA = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans-Bold.ttf"), 17)
FONTE_GRUPO = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans-Bold.ttf"), 16)
FONTE_PINO = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans.ttf"), 13)
FONTE_LEGENDA = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans.ttf"), 13)

BRANCO = "white"
PRETO = "#222222"
CINZA_BORDA = "#555555"

COR_ESP32 = "#DCE9F9"
COR_SR602 = "#FDEBD0"

COR_FIO_3V3 = "#C0392B"
COR_FIO_GND = "#222222"
COR_FIO_OUT_SALA = "#2980B9"
COR_FIO_OUT_QUARTO = "#27AE60"

ESP32_XY = (80, 130, 330, 540)
X_BUS_3V3 = 500
X_BUS_GND = 560

X_SENSOR = 820
LARGURA_SENSOR = 320
ALTURA_SENSOR = 110
META_PINO = 30  # distância vertical entre VCC/OUT e OUT/GND

Y_3V3 = 190
Y_GPIO13 = 280
Y_GPIO14 = 430
Y_GND_ESP = 510


def _texto_centrado(desenho, cx, cy, texto, fonte, cor=PRETO):
    bbox = desenho.textbbox((0, 0), texto, font=fonte)
    largura, altura = bbox[2] - bbox[0], bbox[3] - bbox[1]
    desenho.text((cx - largura / 2, cy - altura / 2 - bbox[1]), texto, font=fonte, fill=cor)


def _caixa_componente(desenho, xy, titulo, cor_fundo, fonte=FONTE_CAIXA, y_titulo_offset=20):
    x0, y0, x1, y1 = xy
    desenho.rounded_rectangle(xy, radius=10, fill=cor_fundo, outline=CINZA_BORDA, width=2)
    _texto_centrado(desenho, (x0 + x1) / 2, y0 + y_titulo_offset, titulo, fonte)


def _pino_direita(desenho, x_borda, y, rotulo):
    desenho.ellipse([x_borda - 4, y - 4, x_borda + 4, y + 4], fill=PRETO)
    desenho.text((x_borda + 10, y - 24), rotulo, font=FONTE_PINO, fill=PRETO)


def _pino_esquerda(desenho, x_borda, y, rotulo):
    desenho.ellipse([x_borda - 4, y - 4, x_borda + 4, y + 4], fill=PRETO)
    bbox = desenho.textbbox((0, 0), rotulo, font=FONTE_PINO)
    largura = bbox[2] - bbox[0]
    desenho.text((x_borda - 10 - largura, y - 24), rotulo, font=FONTE_PINO, fill=PRETO)


def _sensor(desenho, titulo, cor_fundo, y_out_alvo, rotulo_vcc):
    """Caixa do sensor posicionada para que o pino OUT fique exatamente em
    y_out_alvo (mesma altura do GPIO correspondente -> fio reto)."""
    y0 = y_out_alvo - ALTURA_SENSOR / 2
    y1 = y_out_alvo + ALTURA_SENSOR / 2
    xy = (X_SENSOR, y0, X_SENSOR + LARGURA_SENSOR, y1)
    _caixa_componente(desenho, xy, titulo, cor_fundo, fonte=FONTE_GRUPO, y_titulo_offset=18)
    y_vcc = y_out_alvo - META_PINO
    y_gnd = y_out_alvo + META_PINO
    _pino_esquerda(desenho, X_SENSOR, y_vcc, rotulo_vcc)
    _pino_esquerda(desenho, X_SENSOR, y_out_alvo, "OUT")
    _pino_esquerda(desenho, X_SENSOR, y_gnd, "GND")
    return xy, y_vcc, y_gnd


def _bus_vertical(desenho, x, ys, cor):
    desenho.line([(x, min(ys)), (x, max(ys))], fill=cor, width=3)


def gerar_diagrama() -> None:
    imagem = Image.new("RGB", (LARGURA, ALTURA), BRANCO)
    desenho = ImageDraw.Draw(imagem)

    _texto_centrado(desenho, LARGURA / 2, 34, "Zela+ — Diagrama Elétrico: ESP32 + 2x PIR SR602 (Sala e Quarto)", FONTE_TITULO)
    _texto_centrado(
        desenho, LARGURA / 2, 64,
        "Firmware: firmware/zela_presenca/zela_presenca.ino  |  Endpoint: POST /ingest/esp32",
        FONTE_SUBTITULO,
    )

    _caixa_componente(desenho, ESP32_XY, "ESP32 Dev Module", COR_ESP32)
    x_esp32 = ESP32_XY[2]

    _pino_direita(desenho, x_esp32, Y_3V3, "3,3V")
    _pino_direita(desenho, x_esp32, Y_GPIO13, "GPIO 13")
    _pino_direita(desenho, x_esp32, Y_GPIO14, "GPIO 14")
    _pino_direita(desenho, x_esp32, Y_GND_ESP, "GND")

    # --- Fios de sinal OUT: retos, desenhados ANTES das caixas dos sensores
    # (para as caixas e seus pinos ficarem por cima, nunca atrás do fio) ---
    desenho.line([(x_esp32, Y_GPIO13), (X_SENSOR, Y_GPIO13)], fill=COR_FIO_OUT_SALA, width=3)
    desenho.line([(x_esp32, Y_GPIO14), (X_SENSOR, Y_GPIO14)], fill=COR_FIO_OUT_QUARTO, width=3)

    # --- Sensores (coluna única, cada um alinhado ao seu GPIO) ---
    _, vcc_sala, gnd_sala = _sensor(desenho, "SR602 — Sala", COR_SR602, Y_GPIO13, "VCC (3,3V)")
    _, vcc_quarto, gnd_quarto = _sensor(desenho, "SR602 — Quarto", COR_SR602, Y_GPIO14, "VCC (3,3V)")

    # --- Barramento 3,3V: ESP32 -> os 2 SR602 ---
    ys_3v3 = [Y_3V3, vcc_sala, vcc_quarto]
    desenho.line([(x_esp32, Y_3V3), (X_BUS_3V3, Y_3V3)], fill=COR_FIO_3V3, width=3)
    _bus_vertical(desenho, X_BUS_3V3, ys_3v3, COR_FIO_3V3)
    desenho.line([(X_BUS_3V3, vcc_sala), (X_SENSOR, vcc_sala)], fill=COR_FIO_3V3, width=3)
    desenho.line([(X_BUS_3V3, vcc_quarto), (X_SENSOR, vcc_quarto)], fill=COR_FIO_3V3, width=3)

    # --- GND comum: ESP32 + os 2 sensores, todos tocando o mesmo barramento vertical ---
    ys_gnd = [Y_GND_ESP, gnd_sala, gnd_quarto]
    desenho.line([(x_esp32, Y_GND_ESP), (X_BUS_GND, Y_GND_ESP)], fill=COR_FIO_GND, width=3)
    _bus_vertical(desenho, X_BUS_GND, ys_gnd, COR_FIO_GND)
    for y_gnd in [gnd_sala, gnd_quarto]:
        desenho.line([(X_BUS_GND, y_gnd), (X_SENSOR, y_gnd)], fill=COR_FIO_GND, width=3)

    # --- Legenda ---
    legenda_x0, legenda_y0 = 70, 590
    itens_legenda = [
        (COR_FIO_3V3, "Alimentação 3,3V"),
        (COR_FIO_GND, "Terra (GND, comum)"),
        (COR_FIO_OUT_SALA, "Sinal OUT — Sala"),
        (COR_FIO_OUT_QUARTO, "Sinal OUT — Quarto"),
    ]
    x = legenda_x0
    for cor, texto in itens_legenda:
        desenho.line([(x, legenda_y0), (x + 30, legenda_y0)], fill=cor, width=4)
        bbox = desenho.textbbox((0, 0), texto, font=FONTE_LEGENDA)
        desenho.text((x + 38, legenda_y0 - 9), texto, font=FONTE_LEGENDA, fill=PRETO)
        x += 38 + (bbox[2] - bbox[0]) + 26

    nota = (
        "Sem divisor de tensão: o SR602 tem saída OUT fixa em 3,3V, independente da alimentação (VCC) — "
        "diferente do HC-SR04, o OUT conecta direto ao GPIO do ESP32."
    )
    desenho.text((legenda_x0, legenda_y0 + 30), nota, font=FONTE_LEGENDA, fill="#1E8449")

    nota2 = "Presença = OR entre os 2 sensores. Após ligar, aguardar ~60s de aquecimento do PIR antes de confiar nas leituras."
    desenho.text((legenda_x0, legenda_y0 + 52), nota2, font=FONTE_LEGENDA, fill=PRETO)

    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(CAMINHO_SAIDA)
    print(f"Diagrama gerado em: {CAMINHO_SAIDA}")


if __name__ == "__main__":
    gerar_diagrama()
