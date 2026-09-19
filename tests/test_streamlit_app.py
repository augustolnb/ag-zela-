from streamlit.testing.v1 import AppTest


def test_app_bloqueia_sem_senha_configurada(monkeypatch, tmp_path):
    monkeypatch.setenv("ZELA_DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.delenv("STREAMLIT_SENHA", raising=False)

    at = AppTest.from_file("../zela/streamlit_app/app.py")
    at.run()

    assert at.exception == []
    assert any("STREAMLIT_SENHA" in erro.value for erro in at.error)
    assert at.metric == []


def test_app_renderiza_secoes_apos_autenticacao(monkeypatch, tmp_path):
    monkeypatch.setenv("ZELA_DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("STREAMLIT_SENHA", "segredo123")

    at = AppTest.from_file("../zela/streamlit_app/app.py")
    at.run()
    at.text_input[0].set_value("segredo123").run()

    assert at.exception == []
    assert len(at.metric) == 1  # seção de status atual
    assert len(at.subheader) >= 4  # status, medicação, alertas, gráfico (+ formulários)
