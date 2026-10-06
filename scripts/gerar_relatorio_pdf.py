"""Gera um PDF a partir de um Markdown (por padrão, RELATORIO.md).

Uso:
    pip install -e ".[relatorio]"
    python scripts/gerar_relatorio_pdf.py
    python scripts/gerar_relatorio_pdf.py <entrada.md> <saida.pdf>

Regenere sempre que editar o Markdown — o PDF não é atualizado
automaticamente.
"""

import sys
from pathlib import Path

import markdown
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import pisa

RAIZ = Path(__file__).parent.parent
CAMINHO_MD = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "RELATORIO.md"
CAMINHO_PDF = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "RELATORIO.pdf"
DIR_FONTES = Path(__file__).parent / "fontes"

# O diagrama de arquitetura usa caracteres Unicode de desenho de caixa
# (┌─┐│▶◀) e setas (→ ↔) que Helvetica/Courier não cobrem — sem embutir
# uma fonte com esses glifos, eles saem em branco no PDF. DejaVu Sans
# cobre esse conjunto (ver scripts/fontes/LICENSE-DejaVu.txt).
pdfmetrics.registerFont(TTFont("DejaVuSans", str(DIR_FONTES / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(DIR_FONTES / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DejaVuSansMono", str(DIR_FONTES / "DejaVuSansMono.ttf")))

FONT_FACES_CSS = "\n".join(
    f'@font-face {{ font-family: "{nome}"; src: url("{DIR_FONTES / arquivo}"); }}'
    for nome, arquivo in [
        ("DejaVuSans", "DejaVuSans.ttf"),
        ("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"),
        ("DejaVuSansMono", "DejaVuSansMono.ttf"),
    ]
)

ESTILO_CSS = FONT_FACES_CSS + """
@page { size: A4; margin: 2cm; }
body { font-family: "DejaVuSans", sans-serif; font-size: 10pt; line-height: 1.4; }
h1, h2, h3 { font-family: "DejaVuSans-Bold", sans-serif; }
h1 { font-size: 18pt; margin-top: 0; }
h2 { font-size: 14pt; margin-top: 18pt; border-bottom: 1px solid #ccc; }
h3 { font-size: 12pt; margin-top: 14pt; }
pre, code {
    font-family: "DejaVuSansMono", monospace;
    font-size: 8pt;
    white-space: pre;
    background-color: #f5f5f5;
}
pre { padding: 6pt; }
table { width: 100%; margin: 8pt 0; }
th, td { border: 1px solid #999; padding: 4pt; text-align: left; font-size: 9pt; }
img { max-width: 100%; }
"""


def gerar_pdf() -> None:
    texto_md = CAMINHO_MD.read_text(encoding="utf-8")
    corpo_html = markdown.markdown(texto_md, extensions=["tables", "fenced_code"])
    html_completo = f"<html><head><style>{ESTILO_CSS}</style></head><body>{corpo_html}</body></html>"

    with open(CAMINHO_PDF, "wb") as arquivo_pdf:
        resultado = pisa.CreatePDF(
            html_completo,
            dest=arquivo_pdf,
            path=str(RAIZ) + "/",
        )

    if resultado.err:
        raise RuntimeError(f"Falha ao gerar PDF: {resultado.err} erro(s)")

    print(f"PDF gerado em: {CAMINHO_PDF}")


if __name__ == "__main__":
    gerar_pdf()
