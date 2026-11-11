"""Testa qual modo do Gmail faz a notificação aparecer na pulseira.

Envia duas mensagens para a conta de teste, uma por modo, com 20 s de
intervalo:
- "Zela+ teste (insert)": users.messages.insert, direto na caixa de entrada;
- "Zela+ teste (send)": users.messages.send, da conta para ela mesma.

Observe a pulseira e anote qual assunto vibrou. Esse modo vai em
ZELA_GMAIL_MODO no .env da VPS.

Uso (com as variáveis no ambiente, nunca na linha de comando):
    export ZELA_GOOGLE_CALENDAR_CLIENT_ID=... ZELA_GOOGLE_CALENDAR_CLIENT_SECRET=...
    export ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN=... ZELA_GMAIL_PULSEIRA_EMAIL=...
    python scripts/testar_gmail_pulseira.py
"""

import os
import sys
import time

import httpx

from zela.integrations.gmail_client import MODOS, GmailClient

VARIAVEIS = (
    "ZELA_GOOGLE_CALENDAR_CLIENT_ID",
    "ZELA_GOOGLE_CALENDAR_CLIENT_SECRET",
    "ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN",
    "ZELA_GMAIL_PULSEIRA_EMAIL",
)
INTERVALO_SEGUNDOS = 20


def main() -> int:
    faltando = [nome for nome in VARIAVEIS if not os.environ.get(nome)]
    if faltando:
        print("Faltam variáveis de ambiente: " + ", ".join(faltando), file=sys.stderr)
        return 1

    algum_ok = False
    for indice, modo in enumerate(MODOS):
        if indice:
            time.sleep(INTERVALO_SEGUNDOS)
        cliente = GmailClient(
            client_id=os.environ["ZELA_GOOGLE_CALENDAR_CLIENT_ID"],
            client_secret=os.environ["ZELA_GOOGLE_CALENDAR_CLIENT_SECRET"],
            refresh_token=os.environ["ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN"],
            email=os.environ["ZELA_GMAIL_PULSEIRA_EMAIL"],
            modo=modo,
        )
        try:
            cliente.notificar(
                f"Zela+ teste ({modo})",
                f"Teste do modo {modo}. Se esta notificação apareceu na pulseira, use ZELA_GMAIL_MODO={modo}.",
            )
        except httpx.HTTPStatusError as erro:
            # Só o código: o corpo da resposta pode ecoar dados da conta.
            print(f"{modo}: FALHOU: HTTP {erro.response.status_code}")
            continue
        except httpx.HTTPError as erro:
            print(f"{modo}: FALHOU: {type(erro).__name__}")
            continue
        print(f"{modo}: OK")
        algum_ok = True
    return 0 if algum_ok else 1


if __name__ == "__main__":
    sys.exit(main())
