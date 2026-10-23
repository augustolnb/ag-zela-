"""Obtém o refresh_token do Google Agenda (OAuth 2.0 "installed app").

ETAPA MANUAL DE COMISSIONAMENTO — rode UMA ÚNICA VEZ, à mão, na sua máquina
local, durante a instalação do Zela+ (ver seção "Comissionamento: Google
Agenda" do README e a seção 5.1 do design doc). Não faz parte do app nem da
suíte de testes, e não importa nada do pacote `zela`.

Uso:
    python scripts/obter_refresh_token_google.py
    python scripts/obter_refresh_token_google.py <client_id> <client_secret>

O script abre o navegador para você autorizar a conta Google dedicada e, ao
final, imprime o `refresh_token`. Esse valor deve ir para a variável de
ambiente ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN do deploy (junto com
ZELA_GOOGLE_CALENDAR_CLIENT_ID, ZELA_GOOGLE_CALENDAR_CLIENT_SECRET e
ZELA_GOOGLE_CALENDAR_CALENDAR_ID). Trate o refresh_token como senha.
"""

import getpass
import http.server
import json
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

URL_AUTORIZACAO = "https://accounts.google.com/o/oauth2/v2/auth"
URL_TOKEN = "https://oauth2.googleapis.com/token"
ESCOPO = "https://www.googleapis.com/auth/calendar"


def _receber_codigo(estado_esperado: str, resultado: dict) -> http.server.HTTPServer:
    """Sobe um servidor local em porta livre que captura o `code` do redirect."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parametros = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

            # Ignora qualquer requisição que não seja o callback real do OAuth
            # (ex.: o navegador pedindo /favicon.ico automaticamente depois do
            # redirect). Só tratamos como callback uma requisição que
            # realmente tenha "code" ou "error" na query string.
            if "code" not in parametros and "error" not in parametros:
                self.send_response(404)
                self.end_headers()
                return

            # Só registra o primeiro callback genuíno. Requisições
            # subsequentes (ex.: uma segunda chamada perdida chegando antes
            # do servidor terminar de desligar) são ignoradas, para não
            # sobrescrever um resultado de sucesso já armazenado com um erro
            # espúrio.
            if not resultado:
                if parametros.get("state", [""])[0] != estado_esperado:
                    resultado["erro"] = "state inválido (possível interceptação); tente de novo"
                elif "error" in parametros:
                    resultado["erro"] = f"autorização negada: {parametros['error'][0]}"
                else:
                    resultado["code"] = parametros.get("code", [""])[0]

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<html><body><h2>Pronto.</h2><p>Pode fechar esta aba e voltar ao terminal.</p></body></html>".encode("utf-8")
            )
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, *args):  # silencia o log padrão do http.server
            pass

    return http.server.HTTPServer(("127.0.0.1", 0), Handler)


def main() -> int:
    if len(sys.argv) == 3:
        client_id, client_secret = sys.argv[1], sys.argv[2]
    else:
        client_id = input("Client ID (OAuth, tipo Desktop app): ").strip()
        client_secret = getpass.getpass("Client secret: ").strip()
    if not client_id or not client_secret:
        print("client_id e client_secret são obrigatórios.", file=sys.stderr)
        return 1

    estado = secrets.token_urlsafe(16)
    resultado: dict = {}
    servidor = _receber_codigo(estado, resultado)
    redirect_uri = f"http://127.0.0.1:{servidor.server_address[1]}/"

    url_autorizacao = URL_AUTORIZACAO + "?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": ESCOPO,
            "access_type": "offline",
            # prompt=consent força o Google a devolver refresh_token mesmo se a
            # conta já tiver autorizado este client antes.
            "prompt": "consent",
            "state": estado,
        }
    )

    print("\nAbra este link e autorize a conta Google dedicada do idoso:\n")
    print(url_autorizacao, "\n")
    webbrowser.open(url_autorizacao)
    print("Aguardando a autorização no navegador...")

    servidor.serve_forever()
    servidor.server_close()

    if "erro" in resultado:
        print(f"Erro: {resultado['erro']}", file=sys.stderr)
        return 1
    if not resultado.get("code"):
        print("Nenhum código de autorização recebido.", file=sys.stderr)
        return 1

    dados = urllib.parse.urlencode(
        {
            "code": resultado["code"],
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    try:
        with urllib.request.urlopen(urllib.request.Request(URL_TOKEN, data=dados), timeout=30) as resposta:
            corpo = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        print(f"Falha ao trocar o código por tokens (HTTP {erro.code}): {erro.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return 1

    refresh_token = corpo.get("refresh_token")
    if not refresh_token:
        print(
            "O Google não devolveu refresh_token. Revogue o acesso deste app em "
            "myaccount.google.com/permissions e rode o script de novo.",
            file=sys.stderr,
        )
        return 1

    print("\nrefresh_token obtido. Configure no deploy:")
    print("ZELA_GOOGLE_CALENDAR_REFRESH_TOKEN=" + refresh_token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
