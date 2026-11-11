from zela.api.main import _montar_gmail_client

CREDENCIAIS = {
    "ZELA_GOOGLE_CALENDAR_CLIENT_ID": "cid",
    "ZELA_GOOGLE_CALENDAR_CLIENT_SECRET": "csecret",
    "ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN": "rtok",
}


def test_montar_gmail_client_desliga_sem_email():
    # docker-compose define variáveis ausentes do .env como string vazia.
    assert _montar_gmail_client({**CREDENCIAIS, "ZELA_GMAIL_PULSEIRA_EMAIL": ""}) is None


def test_montar_gmail_client_desliga_sem_credenciais():
    assert _montar_gmail_client({"ZELA_GMAIL_PULSEIRA_EMAIL": "teste@gmail.com"}) is None


def test_montar_gmail_client_usa_modo_insert_por_padrao():
    cliente = _montar_gmail_client({**CREDENCIAIS, "ZELA_GMAIL_PULSEIRA_EMAIL": "teste@gmail.com", "ZELA_GMAIL_MODO": ""})
    assert cliente.modo == "insert"
    assert cliente.email == "teste@gmail.com"


def test_montar_gmail_client_respeita_modo_send():
    cliente = _montar_gmail_client(
        {**CREDENCIAIS, "ZELA_GMAIL_PULSEIRA_EMAIL": "teste@gmail.com", "ZELA_GMAIL_MODO": "send"}
    )
    assert cliente.modo == "send"


def test_modo_invalido_desliga_gmail_sem_derrubar_o_backend():
    # Um erro de digitação no .env não pode impedir o backend (e os avisos de emergência) de subir.
    assert _montar_gmail_client(
        {**CREDENCIAIS, "ZELA_GMAIL_PULSEIRA_EMAIL": "teste@gmail.com", "ZELA_GMAIL_MODO": "smtp"}
    ) is None


def test_modo_aceita_maiusculas_e_espacos():
    cliente = _montar_gmail_client(
        {**CREDENCIAIS, "ZELA_GMAIL_PULSEIRA_EMAIL": "teste@gmail.com", "ZELA_GMAIL_MODO": "  Send "}
    )
    assert cliente.modo == "send"


def test_notificar_sintoma_nao_espera_o_gmail(monkeypatch):
    import threading
    import time

    from zela.api import main, pulseira

    liberar = threading.Event()
    chamadas = []

    class _GmailTravado:
        def notificar(self, assunto, corpo):
            liberar.wait(timeout=5)
            chamadas.append(assunto)

    monkeypatch.setattr(main, "gmail_client", _GmailTravado())
    inicio = time.monotonic()
    main._notificar_sintoma(["tontura"])
    duracao = time.monotonic() - inicio
    liberar.set()
    pulseira._executor.submit(lambda: None).result(timeout=5)

    assert duracao < 1
    assert chamadas == ["Zela+: você está bem?"]
