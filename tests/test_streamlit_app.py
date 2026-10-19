from streamlit.testing.v1 import AppTest


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
    assert len(at.subheader) == 6  # status, medicação, alertas, gráfico, form. medicamento, form. compromisso
    assert len(at.columns) == 3  # grid: medicação, alertas, atividade
    assert [t.label for t in at.tabs] == ["Medicamento", "Compromisso"]
