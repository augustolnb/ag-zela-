from pathlib import Path

from zela.embeddings.bulas import DIRETORIO_BULAS, Bula, carregar_bulas, dividir_em_trechos, trechos_de_bula


def _bula(texto):
    return Bula(id="teste", nome="Teste", laboratorio="Lab", registro="1", aprovada_em="01/01/2025", fonte="u", texto=texto)


def test_catalogo_tem_as_cinco_bulas_com_as_nove_secoes():
    bulas = {b.id: b for b in carregar_bulas(DIRETORIO_BULAS)}
    assert set(bulas) == {"dipirona", "losartana", "metformina", "sinvastatina", "dapagliflozina"}
    for bula in bulas.values():
        assert bula.texto.count("## ") == 9
        assert bula.laboratorio and bula.aprovada_em and bula.fonte.startswith("https://")
        assert "PARA QUE ESTE MEDICAMENTO É INDICADO?" in bula.texto


def test_arquivo_sem_campo_obrigatorio_falha(tmp_path):
    (tmp_path / "x.md").write_text("nome: X\n\n## A\n\nb\n")
    try:
        carregar_bulas(tmp_path)
    except ValueError as erro:
        assert "x.md" in str(erro)
    else:
        raise AssertionError("deveria falhar")


def test_trecho_respeita_limite_e_nao_perde_palavras():
    paragrafos = [f"palavra{i} " * 60 for i in range(10)]
    trechos = dividir_em_trechos("\n\n".join(paragrafos), limite=800)
    assert len(trechos) > 1
    assert all(len(t) <= 800 for t in trechos)
    assert " ".join(trechos).split() == " ".join(paragrafos).split()


def test_paragrafo_maior_que_o_limite_e_quebrado_entre_palavras():
    texto = "palavra " * 500
    trechos = dividir_em_trechos(texto, limite=300)
    assert all(len(t) <= 300 for t in trechos)
    assert " ".join(trechos).split() == texto.split()


def test_trecho_identifica_medicamento_laboratorio_e_secao():
    trechos = trechos_de_bula(_bula("## PARA QUE SERVE?\n\nTrata dor.\n\n## COMO USAR?\n\nCom água."))
    assert len(trechos) == 2
    assert trechos[0].startswith("Bula de Teste (Lab, aprovada em 01/01/2025)")
    assert "PARA QUE SERVE?" in trechos[0] and "Trata dor." in trechos[0]
    assert "COMO USAR?" in trechos[1] and "Com água." in trechos[1]


def test_bulas_reais_geram_trechos_dentro_do_limite():
    for bula in carregar_bulas(DIRETORIO_BULAS):
        assert all(len(t) <= 2000 for t in trechos_de_bula(bula))


def test_bulas_estao_dentro_do_pacote_copiado_para_a_imagem():
    assert Path("zela") in DIRETORIO_BULAS.resolve().relative_to(Path.cwd().resolve()).parents
