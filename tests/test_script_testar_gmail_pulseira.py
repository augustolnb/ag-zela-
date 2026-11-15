import importlib.util
from pathlib import Path

_CAMINHO = Path(__file__).parent.parent / "scripts" / "testar_gmail_pulseira.py"
_spec = importlib.util.spec_from_file_location("testar_gmail_pulseira", _CAMINHO)
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def test_pede_sem_eco_so_o_que_falta_no_ambiente():
    perguntas = []

    def perguntar(nome):
        perguntas.append(nome)
        return f"valor-{nome}"

    valores = script.ler_variaveis({"ZELA_GMAIL_PULSEIRA_EMAIL": "teste@gmail.com"}, perguntar)

    assert "ZELA_GMAIL_PULSEIRA_EMAIL" not in perguntas
    assert valores["ZELA_GMAIL_PULSEIRA_EMAIL"] == "teste@gmail.com"
    assert valores["ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN"] == "valor-ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN"
