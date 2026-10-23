FROM python:3.11-slim

WORKDIR /app

# tzdata: a imagem slim não vem com o banco de fusos horários do sistema.
# Sem isso, a variável de ambiente TZ (ver docker-compose.yml) é ignorada
# silenciosamente e o relógio do container cai em UTC — o que faria todo
# lembrete (inclusive o "manha" fixo às 08:00 local) disparar ~3h adiantado
# em relação ao horário de São Paulo digitado no painel.
RUN apt-get update \
    && apt-get install --no-install-recommends -y tzdata \
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências num passo isolado da cópia do código: enquanto
# pyproject.toml não mudar, o Docker reaproveita este layer e não baixa de
# novo os ~1.3GB de deps (google-adk, chromadb, streamlit, ...) a cada
# alteração de código — importante para redeploys rápidos na VPS.
COPY pyproject.toml ./
# ".[deepseek]" (não só ".") para o litellm já vir na imagem — permite
# trocar entre Gemini e DeepSeek só com ZELA_LLM_PROVEDOR no .env, sem
# rebuild (ver zela/agents/orchestrator.py).
RUN mkdir zela && touch zela/__init__.py \
    && pip install --no-cache-dir --default-timeout=100 ".[deepseek]" \
    && rm -rf zela

COPY zela ./zela
# Tema claro do painel (ver zela/streamlit_app/estilo.py) depende deste
# arquivo existir em /app/.streamlit/config.toml dentro da imagem — sem
# isso o Streamlit cai no tema padrão (segue dark/light do navegador).
COPY .streamlit ./.streamlit
RUN pip install --no-cache-dir --no-deps .

# Backend e Streamlit compartilham a mesma imagem — o docker-compose.yml
# sobrescreve CMD para o serviço "streamlit" (evita manter dois
# Dockerfiles quase idênticos para um projeto deste tamanho).
EXPOSE 8000
CMD ["uvicorn", "zela.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
