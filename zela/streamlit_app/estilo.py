import streamlit as st

# Altura, em pixels, dos 3 cards da grade (medicação, alertas e atividade).
# Com altura fixa, o Streamlit rola o conteúdo dentro do card, em vez de o
# card crescer com a lista e empurrar o resto da página. Os 3 cards ficam
# com a mesma altura, lado a lado.
ALTURA_CARD_GRADE = 420

# Paleta "saúde": fundo claro, azul como cor primária, âmbar reservado para
# chamar atenção (alertas) e vermelho só para o nível crítico (desvio
# deliberado da paleta de 2 cores do design system — um alerta crítico de
# saúde precisa do sinal universal de "risco", âmbar sozinho não comunica
# isso com força suficiente).
_CSS = """
<style>
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 1rem;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    animation: zela-fade-in 0.4s ease-in-out;
}

@keyframes zela-fade-in {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
}

.zela-icone {
    display: inline-flex;
    vertical-align: middle;
    margin-right: 0.375rem;
}

.zela-badge {
    display: inline-block;
    padding: 0.125rem 0.625rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 0.5rem;
}
.zela-badge-info { background: #F1F5F9; color: #475569; }
.zela-badge-atencao { background: #FEF3C7; color: #92400E; }
.zela-badge-critico { background: #FEE2E2; color: #B91C1C; }
</style>
"""

_ROTULOS_NIVEL = {"info": "INFO", "atencao": "ATENÇÃO", "critico": "CRÍTICO"}

# SVGs do Lucide (lucide-static, licença ISC), com stroke-width reduzido de
# 2 para 1.5 (traço fino) e tamanho 20x20 conforme diretriz visual do painel.
_ICONES = {
    "heart-pulse": (
        '<svg class="zela-icone" xmlns="http://www.w3.org/2000/svg" width="20" '
        'height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M2 9.5a5.5 5.5 0 0 1 9.591-3.676.56.56 0 0 0 .818 0A5.49 '
        '5.49 0 0 1 22 9.5c0 2.29-1.5 4-3 5.5l-5.492 5.313a2 2 0 0 1-3 '
        '.019L5 15c-1.5-1.5-3-3.2-3-5.5" />'
        '<path d="M3.22 13H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27" /></svg>'
    ),
    "pill": (
        '<svg class="zela-icone" xmlns="http://www.w3.org/2000/svg" width="20" '
        'height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 '
        '0 7 7Z" /><path d="m8.5 8.5 7 7" /></svg>'
    ),
    "bell": (
        '<svg class="zela-icone" xmlns="http://www.w3.org/2000/svg" width="20" '
        'height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M10.268 21a2 2 0 0 0 3.464 0" />'
        '<path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 '
        '13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 '
        '7.326" /></svg>'
    ),
    "activity": (
        '<svg class="zela-icone" xmlns="http://www.w3.org/2000/svg" width="20" '
        'height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 '
        '0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2" />'
        "</svg>"
    ),
}


# Modo noturno: fundo azul escuro, letras brancas e detalhes em amarelo.
# O tema do Streamlit (.streamlit/config.toml) é fixo por servidor; a troca
# por sessão é feita sobrescrevendo as cores com CSS.
AZUL_NOTURNO = "#0B1F3A"
AZUL_CARTAO = "#13294B"
BRANCO = "#FFFFFF"
AMARELO_DESTAQUE = "#FFD60A"
_CINZA_CLARO = "#CBD5E1"

# Cartões e a caixa de abas recebem key="cartao-..." (classe st-key-cartao-...)
# para o CSS achá-los: o contêiner com borda não tem um data-testid próprio.
_CSS_NOTURNO = f"""
<style>
[data-testid="stApp"], [data-testid="stHeader"] {{ background-color: {AZUL_NOTURNO}; }}
[data-testid="stApp"], [data-testid="stApp"] p, [data-testid="stApp"] span,
[data-testid="stApp"] label, [data-testid="stApp"] li,
[data-testid="stApp"] h1, [data-testid="stApp"] h2, [data-testid="stApp"] h3,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] p {{ color: {BRANCO}; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color: {_CINZA_CLARO}; }}
[data-testid="stApp"] a {{ color: {AMARELO_DESTAQUE}; }}
hr {{ border-color: {AMARELO_DESTAQUE} !important; opacity: 0.5; }}

[class*="st-key-cartao"], [data-testid="stForm"] {{
    background-color: {AZUL_CARTAO};
    border: 1px solid {AMARELO_DESTAQUE} !important;
}}
.zela-icone {{ color: {AMARELO_DESTAQUE}; }}

/* Campos: o fundo de todas as camadas internas fica escuro, borda amarela */
[data-testid="stTextInputRootElement"], [data-testid="stTextInputRootElement"] *,
[data-testid="stNumberInputContainer"], [data-testid="stNumberInputContainer"] *,
[data-testid="stDateInputField"], [data-testid="stDateInputField"] *,
[data-testid="stTimeInput"] [data-baseweb="select"] *,
[data-testid="stSelectbox"] [data-baseweb="select"] *,
[data-testid="stMultiSelect"] [data-baseweb="select"] *,
[data-testid="stTextAreaRootElement"], [data-testid="stTextAreaRootElement"] * {{
    background-color: {AZUL_NOTURNO} !important;
    color: {BRANCO} !important;
    -webkit-text-fill-color: {BRANCO};
}}
[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"],
[data-testid="stDateInputField"], [data-testid="stTextAreaRootElement"],
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stTimeInput"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {{
    border: 1px solid {AMARELO_DESTAQUE} !important;
}}
[data-testid="stApp"] input::placeholder, [data-testid="stApp"] textarea::placeholder {{
    color: {_CINZA_CLARO} !important;
    -webkit-text-fill-color: {_CINZA_CLARO};
}}
/* Etiquetas da seleção múltipla */
[data-testid="stMultiSelectTagsContainer"] [role="group"] > *,
[data-testid="stMultiSelectTagsContainer"] [role="group"] > * * {{
    background-color: {AMARELO_DESTAQUE} !important;
    color: {AZUL_NOTURNO} !important;
    -webkit-text-fill-color: {AZUL_NOTURNO};
}}
[data-baseweb="popover"] ul, [data-baseweb="popover"] li, [data-baseweb="calendar"],
[data-baseweb="calendar"] * {{
    background-color: {AZUL_CARTAO} !important;
    color: {BRANCO} !important;
}}

/* Interruptor ligado */
[data-testid="stCheckbox"] label:has(input:checked) > div:not([data-testid="stWidgetLabel"]),
[data-testid="stCheckbox"] label:has([aria-checked="true"]) > div:not([data-testid="stWidgetLabel"]) {{
    background-color: {AMARELO_DESTAQUE} !important;
}}
[data-testid="stMultiSelect"] svg, [data-testid="stSelectbox"] svg, [data-testid="stDateInput"] svg {{
    color: {BRANCO} !important;
}}

/* Caixas de seleção (simples, múltipla e horário) */
[data-testid="stSelectbox"] div[role="group"], [data-testid="stMultiSelect"] div[role="group"],
[data-testid="stTimeInput"] div[role="group"] {{
    background-color: {AZUL_NOTURNO} !important;
    border: 1px solid {AMARELO_DESTAQUE} !important;
    color: {BRANCO} !important;
}}
[data-testid="stSelectbox"] div[role="group"] *, [data-testid="stTimeInput"] div[role="group"] * {{
    color: {BRANCO} !important;
    -webkit-text-fill-color: {BRANCO};
}}

/* Botões e abas */
[data-testid="stApp"] button[kind], [data-testid="stFormSubmitButton"] button {{
    background-color: {AMARELO_DESTAQUE} !important;
    border-color: {AMARELO_DESTAQUE} !important;
}}
[data-testid="stApp"] button[kind] p, [data-testid="stApp"] button[kind] span,
[data-testid="stFormSubmitButton"] button p {{
    color: {AZUL_NOTURNO} !important;
    font-weight: 700;
}}
[data-testid="stTab"] p {{ color: {BRANCO} !important; }}
[data-testid="stTab"][aria-selected="true"] p {{ color: {AMARELO_DESTAQUE} !important; }}
[data-testid="stTab"] .react-aria-SelectionIndicator {{ background-color: {AMARELO_DESTAQUE} !important; }}

/* Selos de nível: o crítico se destaca mais */
.zela-badge-info {{ background: transparent; color: {BRANCO}; border: 1px solid {BRANCO}; }}
.zela-badge-atencao {{ background: transparent; color: {AMARELO_DESTAQUE}; border: 1px solid {AMARELO_DESTAQUE}; }}
.zela-badge-critico {{ background: {AMARELO_DESTAQUE}; color: {AZUL_NOTURNO} !important; }}

/* A tabela desenha em canvas com fundo claro: inverte as cores e mescla
   sobre o azul do cartão, para o preto invertido virar azul escuro. A faixa
   de presença fica de fora: ela já desenha com as cores noturnas. */
[data-testid="stDataFrame"] {{
    filter: invert(1) hue-rotate(180deg);
    mix-blend-mode: lighten;
}}
</style>
"""


def aplicar_estilo(noturno: bool = False) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    if noturno:
        st.markdown(_CSS_NOTURNO, unsafe_allow_html=True)


def icone(nome: str) -> str:
    return _ICONES.get(nome, "")


def badge_nivel(nivel: str) -> str:
    rotulo = _ROTULOS_NIVEL.get(nivel, nivel.upper())
    return f'<span class="zela-badge zela-badge-{nivel}">{rotulo}</span>'
