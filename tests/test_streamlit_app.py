from streamlit.testing.v1 import AppTest
from zela.streamlit_app.estilo import ALTURA_CARD_GRADE


def test_app_bloqueia_sem_senha_configurada(monkeypatch, tmp_path):
    monkeypatch.setenv("ZELA_DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.delenv("STREAMLIT_SENHA", raising=False)

    # default_timeout maior que o padrão (3s): o painel agora renderiza mais
    # elementos por execução (cards com borda, grid de colunas, ícones,
    # abas) e o timeout padrão do AppTest fica justo em máquinas sob carga.
    at = AppTest.from_file("../zela/streamlit_app/app.py", default_timeout=10)
    at.run()

    assert at.exception == []
    assert any("STREAMLIT_SENHA" in erro.value for erro in at.error)
    assert at.metric == []


def test_app_renderiza_secoes_apos_autenticacao(monkeypatch, tmp_path):
    monkeypatch.setenv("ZELA_DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("STREAMLIT_SENHA", "segredo123")

    at = AppTest.from_file("../zela/streamlit_app/app.py", default_timeout=10)
    at.run()
    at.text_input[0].set_value("segredo123").run()

    assert at.exception == []
    assert len(at.metric) == 1  # seção de status atual
    assert len(at.subheader) == 7  # status, medicação, alertas, gráfico, form. medicamento, form. compromisso, histórico
    assert len(at.columns) == 5  # grid (medicação, alertas, atividade) + filtros do histórico (dia, busca)
    assert [t.label for t in at.tabs] == ["Medicamento", "Compromisso", "Histórico"]


def test_cards_da_grade_tem_altura_fixa_com_rolagem(monkeypatch, tmp_path):
    # Altura fixa faz o Streamlit rolar o conteúdo dentro do card, em vez de
    # o card crescer junto com a lista de medicações, alertas ou leituras.
    monkeypatch.setenv("ZELA_DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("STREAMLIT_SENHA", "segredo123")

    at = AppTest.from_file("../zela/streamlit_app/app.py", default_timeout=10)
    at.run()
    at.text_input[0].set_value("segredo123").run()

    alturas = []
    for coluna in at.columns[:3]:  # as 3 primeiras são a grade; as seguintes, os filtros do histórico
        cards = list(coluna.children.values())
        assert len(cards) == 1
        alturas.append(cards[0].proto.height_config.pixel_height)
    assert alturas == [ALTURA_CARD_GRADE] * 3


def test_card_de_status_nao_tem_altura_fixa(monkeypatch, tmp_path):
    monkeypatch.setenv("ZELA_DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("STREAMLIT_SENHA", "segredo123")

    at = AppTest.from_file("../zela/streamlit_app/app.py", default_timeout=10)
    at.run()
    at.text_input[0].set_value("segredo123").run()

    # O status é uma linha só: com altura fixa, sobraria espaço vazio.
    cards = [
        bloco
        for bloco in at.main.children.values()
        if getattr(bloco.proto, "flex_container", None) is not None and bloco.proto.flex_container.border
    ]
    card_status = cards[0]
    assert len(card_status.get("metric")) == 1
    assert card_status.proto.height_config.pixel_height == 0


def test_abas_lembram_a_aba_escolhida(monkeypatch, tmp_path):
    # Sem estado nas abas, qualquer interação (ex.: a busca do histórico)
    # recarrega a página e volta para "Medicamento".
    monkeypatch.setenv("ZELA_DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("STREAMLIT_SENHA", "segredo123")

    at = AppTest.from_file("../zela/streamlit_app/app.py", default_timeout=10)
    at.run()
    at.text_input[0].set_value("segredo123").run()

    assert at.session_state["aba_painel"] == "Medicamento"
    at.session_state["aba_painel"] = "Histórico"
    at.text_input(key="historico_busca").set_value("x").run()

    assert at.session_state["aba_painel"] == "Histórico"



def test_botao_de_modo_noturno_aparece_ja_na_tela_de_senha(monkeypatch, tmp_path):
    monkeypatch.setenv("ZELA_DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("STREAMLIT_SENHA", "segredo123")

    at = AppTest.from_file("../zela/streamlit_app/app.py", default_timeout=10)
    at.run()

    botao = at.toggle(key="noturno")
    assert botao.label == "Modo noturno"
    assert botao.value is False
    assert not any("#0B1F3A" in m.value for m in at.markdown)

    botao.set_value(True).run()

    assert any("#0B1F3A" in m.value for m in at.markdown)
