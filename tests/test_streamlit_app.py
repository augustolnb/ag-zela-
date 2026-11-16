from streamlit.testing.v1 import AppTest

from zela.storage.db import conectar
from zela.storage.usuarios import criar_usuario
from zela.streamlit_app.estilo import ALTURA_CARD_GRADE


def _app(monkeypatch, tmp_path, com_usuario=True):
    caminho = str(tmp_path / "teste.db")
    monkeypatch.setenv("ZELA_DB_PATH", caminho)
    if com_usuario:
        criar_usuario(conectar(caminho), "familia", "senha-forte-1")
    # default_timeout maior que o padrão (3s): o painel renderiza muitos
    # elementos por execução e o timeout padrão fica justo sob carga.
    return AppTest.from_file("../zela/streamlit_app/app.py", default_timeout=10)


def _painel_logado(monkeypatch, tmp_path):
    at = _app(monkeypatch, tmp_path)
    at.run()
    at.text_input(key="login_usuario").set_value("familia")
    at.text_input(key="login_senha").set_value("senha-forte-1")
    at.button(key="login_entrar").click().run()
    return at


def test_app_sem_usuarios_mostra_como_criar_o_primeiro(monkeypatch, tmp_path):
    at = _app(monkeypatch, tmp_path, com_usuario=False)
    at.run()

    assert at.exception == []
    assert any("usuarios criar" in erro.value for erro in at.error)
    assert at.metric == []


def test_app_antes_do_login_mostra_so_o_formulario(monkeypatch, tmp_path):
    at = _app(monkeypatch, tmp_path)
    at.run()

    assert at.exception == []
    assert at.metric == []
    assert at.tabs == []
    assert [b.label for b in at.button] == ["Entrar"]


def test_app_renderiza_secoes_apos_autenticacao(monkeypatch, tmp_path):
    at = _painel_logado(monkeypatch, tmp_path)

    assert at.exception == []
    assert len(at.metric) == 1  # seção de status atual
    assert len(at.subheader) == 7  # status, medicação, alertas, gráfico, form. medicamento, form. compromisso, histórico
    assert len(at.columns) == 7  # usuário/sair (2) + grade (3) + filtros do histórico (2)
    assert [t.label for t in at.tabs] == ["Medicamento", "Compromisso", "Histórico"]


def test_cards_da_grade_tem_altura_fixa_com_rolagem(monkeypatch, tmp_path):
    # Altura fixa faz o Streamlit rolar o conteúdo dentro do card, em vez de
    # o card crescer junto com a lista de medicações, alertas ou leituras.
    at = _painel_logado(monkeypatch, tmp_path)

    alturas = []
    for coluna in at.columns[2:5]:  # depois de usuário/sair vem a grade; por último, os filtros do histórico
        cards = list(coluna.children.values())
        assert len(cards) == 1
        alturas.append(cards[0].proto.height_config.pixel_height)
    assert alturas == [ALTURA_CARD_GRADE] * 3


def test_card_de_status_nao_tem_altura_fixa(monkeypatch, tmp_path):
    at = _painel_logado(monkeypatch, tmp_path)

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
    at = _painel_logado(monkeypatch, tmp_path)

    assert at.session_state["aba_painel"] == "Medicamento"
    at.session_state["aba_painel"] = "Histórico"
    at.text_input(key="historico_busca").set_value("x").run()

    assert at.session_state["aba_painel"] == "Histórico"


def test_botao_de_modo_noturno_aparece_ja_na_tela_de_login(monkeypatch, tmp_path):
    at = _app(monkeypatch, tmp_path)
    at.run()

    botao = at.toggle(key="noturno")
    assert botao.label == "Modo noturno"
    assert botao.value is False
    assert not any("#0B1F3A" in m.value for m in at.markdown)

    botao.set_value(True).run()

    assert any("#0B1F3A" in m.value for m in at.markdown)
