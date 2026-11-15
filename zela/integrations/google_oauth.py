import httpx

TOKEN_URL = "https://oauth2.googleapis.com/token"


def obter_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Troca o refresh token por um access token de curta duração.

    Compartilhado pelo Google Agenda e pelo Gmail, que usam o mesmo
    consentimento OAuth da conta de teste.
    """
    resposta = httpx.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resposta.raise_for_status()
    return resposta.json()["access_token"]
