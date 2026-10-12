"""Gera o diagrama elétrico ESP32 + HC-SR04 (sensor de presença) usado em
docs/hardware/automacao_esp32.md.

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

LARGURA, ALTURA = 1400, 980

FONTE_TITULO = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans-Bold.ttf"), 26)
FONTE_SUBTITULO = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans.ttf"), 15)
FONTE_CAIXA = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans-Bold.ttf"), 18)
FONTE_PINO = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans.ttf"), 14)
FONTE_LEGENDA = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans.ttf"), 13)
FONTE_COMPONENTE = ImageFont.truetype(str(DIR_FONTES / "DejaVuSans-Bold.ttf"), 14)

BRANCO = "white"
PRETO = "#222222"
CINZA_BORDA = "#555555"

COR_ESP32 = "#DCE9F9"
COR_SENSOR = "#FDEBD0"
COR_RESISTOR = "#E2F0D9"

COR_FIO_5V = "#C0392B"        # vermelho: alimentação 5V
COR_FIO_GND = "#222222"       # preto: terra
COR_FIO_TRIG = "#E67E22"      # laranja: sinal TRIG (3.3V, ESP32 -> sensor)
COR_FIO_ECHO_5V = "#2980B9"   # azul: sinal ECHO antes do divisor (5V, sensor -> divisor)
COR_FIO_ECHO_3V3 = "#27AE60"  # verde: sinal ECHO depois do divisor (3.3V, divisor -> ESP32)

ESP32_XY = (110, 160, 360, 640)
SENSOR_XY = (1020, 160, 1270, 640)

Y_5V = 260
Y_TRIG = 380
Y_ECHO = 500
Y_GND_STUB = 600
Y_GND_RAIL = 820


def _texto_centrado(desenho, cx, cy, texto, fonte, cor=PRETO):
    bbox = desenho.textbbox((0, 0), texto, font=fonte)
    largura, altura = bbox[2] - bbox[0], bbox[3] - bbox[1]
    desenho.text((cx - largura / 2, cy - altura / 2 - bbox[1]), texto, font=fonte, fill=cor)


def _caixa_componente(desenho, xy, titulo, cor_fundo):
    x0, y0, x1, y1 = xy
    desenho.rounded_rectangle(xy, radius=10, fill=cor_fundo, outline=CINZA_BORDA, width=2)
    _texto_centrado(desenho, (x0 + x1) / 2, y0 + 24, titulo, FONTE_CAIXA)


def _pino_direita(desenho, x_borda, y, rotulo):
    """Pino saindo pra direita da caixa (ESP32). Rótulo fica ACIMA do fio,
    nunca em cima dele, pra não colidir com o traçado que continua reto."""
    desenho.ellipse([x_borda - 4, y - 4, x_borda + 4, y + 4], fill=PRETO)
    desenho.text((x_borda + 10, y - 26), rotulo, font=FONTE_PINO, fill=PRETO)


def _pino_esquerda(desenho, x_borda, y, rotulo):
    """Pino saindo pra esquerda da caixa (HC-SR04). Rótulo acima do fio."""
    desenho.ellipse([x_borda - 4, y - 4, x_borda + 4, y + 4], fill=PRETO)
    bbox = desenho.textbbox((0, 0), rotulo, font=FONTE_PINO)
    largura = bbox[2] - bbox[0]
    desenho.text((x_borda - 10 - largura, y - 26), rotulo, font=FONTE_PINO, fill=PRETO)


def _pino_baixo(desenho, x, y_borda, rotulo, y_final):
    """Pino saindo por baixo da caixa até o trilho de GND."""
    desenho.ellipse([x - 4, y_borda - 4, x + 4, y_borda + 4], fill=PRETO)
    desenho.line([(x, y_borda), (x, y_final)], fill=COR_FIO_GND, width=3)
    desenho.text((x + 10, (y_borda + y_final) / 2 - 8), rotulo, font=FONTE_PINO, fill=PRETO)


def _resistor(desenho, xy, rotulo):
    x0, y0, x1, y1 = xy
    desenho.rounded_rectangle(xy, radius=6, fill=COR_RESISTOR, outline=CINZA_BORDA, width=2)
    _texto_centrado(desenho, (x0 + x1) / 2, (y0 + y1) / 2, rotulo, FONTE_COMPONENTE)


def gerar_diagrama() -> None:
    imagem = Image.new("RGB", (LARGURA, ALTURA), BRANCO)
    desenho = ImageDraw.Draw(imagem)

    _texto_centrado(desenho, LARGURA / 2, 36, "Zela+ — Diagrama Elétrico: ESP32 + HC-SR04 (Sensor de Presença)", FONTE_TITULO)
    _texto_centrado(
        desenho, LARGURA / 2, 66,
        "Firmware: firmware/zela_presenca/zela_presenca.ino  |  Endpoint: POST /ingest/esp32",
        FONTE_SUBTITULO,
    )

    _caixa_componente(desenho, ESP32_XY, "ESP32 Dev Module", COR_ESP32)
    _caixa_componente(desenho, SENSOR_XY, "HC-SR04", COR_SENSOR)

    x_esp32 = ESP32_XY[2]
    x_sensor = SENSOR_XY[0]

    # --- Pinos ---
    _pino_direita(desenho, x_esp32, Y_5V, "5V (VIN)")
    _pino_direita(desenho, x_esp32, Y_TRIG, "GPIO 5 (TRIG)")
    _pino_direita(desenho, x_esp32, Y_ECHO, "GPIO 18 (ECHO)")
    _pino_baixo(desenho, 235, ESP32_XY[3], "GND", Y_GND_RAIL)

    _pino_esquerda(desenho, x_sensor, Y_5V, "VCC (5V)")
    _pino_esquerda(desenho, x_sensor, Y_TRIG, "TRIG")
    _pino_esquerda(desenho, x_sensor, Y_ECHO, "ECHO")
    _pino_baixo(desenho, 1145, SENSOR_XY[3], "GND", Y_GND_RAIL)

    # --- Fio de alimentação: reto, ESP32 5V -> HC-SR04 VCC ---
    desenho.line([(x_esp32, Y_5V), (x_sensor, Y_5V)], fill=COR_FIO_5V, width=3)

    # --- Fio TRIG: reto, ESP32 GPIO5 -> HC-SR04 TRIG ---
    desenho.line([(x_esp32, Y_TRIG), (x_sensor, Y_TRIG)], fill=COR_FIO_TRIG, width=3)

    # --- Divisor de tensão no caminho do ECHO (5V -> 3.3V) ---
    # HC-SR04 ECHO (5V, azul) -> R1 -> nó -> ESP32 GPIO18 (3.3V, verde)
    #                                   |
    #                                  R2 (verde) -> trilho de GND
    r1_xy = (760, Y_ECHO - 20, 860, Y_ECHO + 20)
    _resistor(desenho, r1_xy, "R1\n1kΩ")
    x_no = 920
    desenho.line([(x_sensor, Y_ECHO), (r1_xy[2], Y_ECHO)], fill=COR_FIO_ECHO_5V, width=3)  # sensor -> R1
    desenho.line([(r1_xy[0], Y_ECHO), (x_no, Y_ECHO)], fill=COR_FIO_ECHO_3V3, width=3)       # R1 -> nó
    desenho.line([(x_no, Y_ECHO), (x_esp32, Y_ECHO)], fill=COR_FIO_ECHO_3V3, width=3)        # nó -> GPIO18
    desenho.ellipse([x_no - 5, Y_ECHO - 5, x_no + 5, Y_ECHO + 5], fill=PRETO)

    r2_xy = (x_no - 50, Y_ECHO + 70, x_no + 50, Y_ECHO + 110)
    _resistor(desenho, r2_xy, "R2\n2kΩ")
    desenho.line([(x_no, Y_ECHO), (x_no, r2_xy[1])], fill=COR_FIO_ECHO_3V3, width=3)
    desenho.line([(x_no, r2_xy[3]), (x_no, Y_GND_RAIL)], fill=COR_FIO_GND, width=3)
    desenho.ellipse([x_no - 5, Y_GND_RAIL - 5, x_no + 5, Y_GND_RAIL + 5], fill=PRETO)

    desenho.text((r1_xy[0] - 40, Y_ECHO - 70), "Divisor de tensão (obrigatório na linha ECHO)", font=FONTE_LEGENDA, fill=PRETO)

    # --- Trilho comum de GND ligando ESP32, HC-SR04 e o divisor ---
    desenho.line([(235, Y_GND_RAIL), (1145, Y_GND_RAIL)], fill=COR_FIO_GND, width=3)

    # --- Legenda ---
    legenda_x0, legenda_y0 = 70, 850
    itens_legenda = [
        (COR_FIO_5V, "Alimentação 5V (VIN)"),
        (COR_FIO_GND, "Terra (GND)"),
        (COR_FIO_TRIG, "Sinal TRIG — 3,3V, ESP32 → sensor"),
        (COR_FIO_ECHO_5V, "Sinal ECHO — 5V, sensor → divisor"),
        (COR_FIO_ECHO_3V3, "Sinal ECHO — 3,3V, divisor → ESP32"),
    ]
    x = legenda_x0
    for cor, texto in itens_legenda:
        desenho.line([(x, legenda_y0), (x + 30, legenda_y0)], fill=cor, width=4)
        bbox = desenho.textbbox((0, 0), texto, font=FONTE_LEGENDA)
        desenho.text((x + 38, legenda_y0 - 9), texto, font=FONTE_LEGENDA, fill=PRETO)
        x += 40 + (bbox[2] - bbox[0]) + 30

    nota = (
        "Atenção: o HC-SR04 opera o ECHO em 5V, mas os GPIOs do ESP32 toleram no máximo 3,3V — ligar o ECHO "
        "direto ao GPIO18 sem o divisor de tensão pode danificar permanentemente o ESP32."
    )
    desenho.text((legenda_x0, legenda_y0 + 30), nota, font=FONTE_LEGENDA, fill="#A93226")

    CAMINHO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(CAMINHO_SAIDA)
    print(f"Diagrama gerado em: {CAMINHO_SAIDA}")


if __name__ == "__main__":
    gerar_diagrama()
