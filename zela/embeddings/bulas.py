"""Catálogo de bulas do paciente usado pelo RAG, independente dos medicamentos
cadastrados: consultar uma bula não pode gerar lembrete de um remédio que a
pessoa não toma."""
import re
from dataclasses import dataclass
from pathlib import Path

DIRETORIO_BULAS = Path(__file__).resolve().parent.parent / "conhecimento" / "bulas"
LIMITE_TRECHO = 1500
_CAMPOS = ("nome", "laboratorio", "registro", "aprovada_em", "fonte")


@dataclass(frozen=True)
class Bula:
    id: str
    nome: str
    laboratorio: str
    registro: str
    aprovada_em: str
    fonte: str
    texto: str


def carregar_bulas(diretorio: Path = DIRETORIO_BULAS) -> list[Bula]:
    bulas = []
    for arquivo in sorted(Path(diretorio).glob("*.md")):
        cabecalho, _, texto = arquivo.read_text().partition("\n\n")
        campos = dict(linha.split(": ", 1) for linha in cabecalho.splitlines() if ": " in linha)
        faltando = [c for c in _CAMPOS if not campos.get(c)]
        if faltando:
            raise ValueError(f"{arquivo.name}: faltam os campos {faltando}")
        bulas.append(Bula(id=arquivo.stem, texto=texto.strip(), **{c: campos[c] for c in _CAMPOS}))
    return bulas


def dividir_em_trechos(texto: str, limite: int = LIMITE_TRECHO) -> list[str]:
    """Agrupa parágrafos até o limite; parágrafo maior que o limite é quebrado entre palavras."""
    pedacos: list[str] = []
    for paragrafo in re.split(r"\n\s*\n", texto.strip()):
        atual = ""
        for palavra in paragrafo.split():
            candidato = f"{atual} {palavra}".strip()
            if len(candidato) > limite:
                pedacos.append(atual)
                atual = palavra
            else:
                atual = candidato
        if atual:
            pedacos.append(atual)

    trechos: list[str] = []
    for pedaco in pedacos:
        if trechos and len(trechos[-1]) + 2 + len(pedaco) <= limite:
            trechos[-1] = f"{trechos[-1]}\n\n{pedaco}"
        else:
            trechos.append(pedaco)
    return trechos


def trechos_de_bula(bula: Bula) -> list[str]:
    identificacao = f"Bula de {bula.nome} ({bula.laboratorio}, aprovada em {bula.aprovada_em})"
    trechos = []
    for secao in re.split(r"^## ", bula.texto, flags=re.MULTILINE):
        if not secao.strip():
            continue
        titulo, _, corpo = secao.partition("\n")
        prefixo = f"{identificacao} - {titulo.strip()}\n"
        trechos += [prefixo + t for t in dividir_em_trechos(corpo, LIMITE_TRECHO)]
    return trechos
