"""Converte o texto de uma bula do paciente (pdftotext -layout) no formato de
zela/conhecimento/bulas, sem reescrever o conteúdo: só limpa quebras e rodapés."""
import argparse
import re
from pathlib import Path

_SECAO = re.compile(r"^\s*([1-9])\.\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ].*)$")
_FIM = re.compile(r"^\s*(III|IV)\s*[-.)]\s*DIZERES LEGAIS|^\s*DIZERES LEGAIS", re.IGNORECASE)
_ATENCAO_RODAPE = re.compile(r"^\s*(\d+\s*$|Página\s+\d+|.*_bula_paciente|.*\bVP\d*\b.*$)", re.IGNORECASE)


def extrair_secoes(texto: str) -> list[tuple[str, list[str]]]:
    linhas = texto.replace("\f", "\n").splitlines()
    secoes: list[tuple[str, list[str]]] = []
    proximo = 1
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        if secoes and _FIM.match(linha):
            break
        achado = _SECAO.match(linha)
        if achado and int(achado.group(1)) == proximo and linha.strip().upper() == linha.strip():
            titulo = achado.group(2).strip()
            # Título da seção 9 ocupa duas linhas nas bulas.
            if not titulo.endswith("?") and i + 1 < len(linhas):
                i += 1
                titulo = f"{titulo} {linhas[i].strip()}"
            secoes.append((titulo, []))
            proximo += 1
        elif secoes and not _ATENCAO_RODAPE.match(linha):
            secoes[-1][1].append(re.sub(r"\s+", " ", linha).strip())
        i += 1
    return secoes


def _em_paragrafos(linhas: list[str]) -> str:
    paragrafos, atual = [], []
    for linha in linhas:
        if not linha:
            if atual:
                paragrafos.append(" ".join(atual))
                atual = []
        else:
            atual.append(linha)
    if atual:
        paragrafos.append(" ".join(atual))
    return "\n\n".join(paragrafos)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("entrada", type=Path)
    p.add_argument("saida", type=Path)
    p.add_argument("--nome", required=True)
    p.add_argument("--laboratorio", required=True)
    p.add_argument("--registro", required=True)
    p.add_argument("--aprovada-em", required=True)
    p.add_argument("--fonte", required=True)
    a = p.parse_args()
    secoes = extrair_secoes(a.entrada.read_text())
    if len(secoes) != 9:
        raise SystemExit(f"esperava 9 seções, encontrei {len(secoes)}")
    cabecalho = (
        f"nome: {a.nome}\nlaboratorio: {a.laboratorio}\nregistro: {a.registro}\n"
        f"aprovada_em: {a.aprovada_em}\nfonte: {a.fonte}\n"
    )
    corpo = "\n\n".join(f"## {titulo}\n\n{_em_paragrafos(linhas)}" for titulo, linhas in secoes)
    a.saida.write_text(f"{cabecalho}\n{corpo}\n")


if __name__ == "__main__":
    main()
