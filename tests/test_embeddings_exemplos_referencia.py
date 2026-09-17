from zela.embeddings.exemplos_referencia import EXEMPLOS_REFERENCIA
from zela.models.monitoramento import StatusMonitoramento


def test_ha_pelo_menos_um_exemplo_por_status():
    status_presentes = {exemplo.status for exemplo in EXEMPLOS_REFERENCIA}
    assert status_presentes == {
        StatusMonitoramento.NORMAL,
        StatusMonitoramento.ATENCAO,
        StatusMonitoramento.RISCO,
    }


def test_ha_pelo_menos_cinco_exemplos_por_status():
    from collections import Counter

    contagem = Counter(exemplo.status for exemplo in EXEMPLOS_REFERENCIA)
    assert all(quantidade >= 5 for quantidade in contagem.values())


def test_textos_dos_exemplos_sao_unicos():
    textos = [exemplo.texto for exemplo in EXEMPLOS_REFERENCIA]
    assert len(textos) == len(set(textos))
