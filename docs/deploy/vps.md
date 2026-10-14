# Deploy em VPS — Zela+

Guia para colocar o sistema completo online durante a apresentação do MVP
para os avaliadores. Pressupõe uma VPS Ubuntu/Debian já provisionada, com
Docker e Docker Compose instalados, e um domínio que você controla (os
exemplos abaixo usam `augustoautomacoes.com`).

## Visão geral da topologia

4 containers, todos na mesma rede do `docker-compose.yml`:

```
Internet (80/443) → Caddy (HTTPS automático via Let's Encrypt)
                       ├── api.augustoautomacoes.com      → backend:8000
                       ├── painel.augustoautomacoes.com   → streamlit:8501
                       └── whatsapp.augustoautomacoes.com → waha:3000
```

- **backend**: FastAPI + scheduler embutido (webhook, ingestão, classificação).
- **streamlit**: painel da família (já tem senha própria, `STREAMLIT_SENHA`).
- **waha**: WhatsApp — o dashboard em `whatsapp.*` é só para você escanear
  o QR code; não precisa ficar protegido por senha adicional além da que
  já existe (`WAHA_DASHBOARD_PASSWORD`).
- **caddy**: proxy reverso, único serviço com portas 80/443 expostas.

`n8n` **não** faz parte desta topologia — durante a demonstração, rode-o
localmente no seu notebook e aponte o webhook de teste para
`https://api.augustoautomacoes.com/api/classificar-mensagem`.

## 1. DNS

Crie 3 registros tipo `A` apontando para o IP público da VPS:

| Nome | Tipo | Valor |
|---|---|---|
| `api.augustoautomacoes.com` | A | `<IP da VPS>` |
| `painel.augustoautomacoes.com` | A | `<IP da VPS>` |
| `whatsapp.augustoautomacoes.com` | A | `<IP da VPS>` |

Espere a propagação (`dig api.augustoautomacoes.com` deve retornar o IP)
antes de seguir — o Caddy só emite certificado HTTPS com o DNS já
resolvendo.

## 2. Firewall

Só 22 (SSH), 80 e 443 ficam públicas. As portas internas dos serviços
(3000, 8000, 8501 — usadas pelo `docker-compose.yml` em dev local) **não**
devem ser alcançáveis de fora:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

## 3. Clonar e configurar

```bash
git clone https://github.com/augustolnb/ag-zela-.git
cd ag-zela-
cp .env.example .env
```

Edite `.env` e preencha (ver comentários no próprio arquivo):

- `WAHA_API_KEY`, `WAHA_DASHBOARD_USERNAME`, `WAHA_DASHBOARD_PASSWORD` —
  valores novos e fortes (não reusar os de desenvolvimento local).
- `GOOGLE_API_KEY` — chave do Gemini.
- `ZELA_INGESTAO_TOKEN` — **obrigatório aqui** (o backend fica público).
  Gere um valor aleatório forte, por exemplo: `openssl rand -hex 32`.
- `STREAMLIT_SENHA` — senha do painel da família.

Se o domínio real for diferente de `augustoautomacoes.com`, ajuste os 3
nomes de host no `Caddyfile` antes de subir.

## 4. Subir os containers

```bash
docker compose up -d --build
docker compose ps
```

Acompanhe os logs do Caddy até ver a emissão do certificado:

```bash
docker compose logs -f caddy
```

## 5. Conectar o WhatsApp

Abra `https://whatsapp.augustoautomacoes.com/` (login com
`WAHA_DASHBOARD_USERNAME`/`WAHA_DASHBOARD_PASSWORD`), escaneie o QR code
com o número do Zela+. Isso é necessário mesmo que você já tivesse uma
sessão conectada em outro host — a sessão vive no volume `waha_data`
desta VPS, é uma conexão nova.

Configure o webhook do WAHA para
`https://api.augustoautomacoes.com/webhook/whatsapp`.

## 6. Testar

```bash
# Backend respondendo:
curl -i https://api.augustoautomacoes.com/openapi.json

# Endpoint protegido por token (deve dar 401 sem o header):
curl -i https://api.augustoautomacoes.com/api/classificar-mensagem \
  -X POST -H "Content-Type: application/json" -d '{"texto":"teste"}'

# Com o token correto (deve dar 200):
curl -i https://api.augustoautomacoes.com/api/classificar-mensagem \
  -X POST -H "Content-Type: application/json" \
  -H "X-Api-Key: $ZELA_INGESTAO_TOKEN" -d '{"texto":"teste"}'
```

Abra `https://painel.augustoautomacoes.com/` e confirme que pede a senha
do Streamlit e carrega o painel.

## Checklist antes da apresentação

- [ ] DNS dos 3 subdomínios resolvendo para o IP da VPS
- [ ] `ufw status` mostrando só 22/80/443 abertas
- [ ] `docker compose ps` com os 4 containers `Up`
- [ ] Certificado HTTPS emitido (sem aviso de "não seguro" no navegador)
- [ ] WhatsApp reconectado via QR no dashboard do WAHA
- [ ] `ZELA_INGESTAO_TOKEN` configurado e testado (401 sem header, 200 com)
- [ ] Painel Streamlit pedindo senha e exibindo dados
- [ ] n8n local (notebook) apontando o webhook de teste para
      `https://api.augustoautomacoes.com/api/classificar-mensagem`

## Atualizando depois de um `git pull`

```bash
git pull
docker compose up -d --build
```

Os volumes (`zela_data`, `chroma_data`, `waha_data`, `caddy_data`) não são
afetados — dados e a sessão do WhatsApp persistem entre atualizações.
