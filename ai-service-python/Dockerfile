# Build context 必須是 repo 根目錄（taxonomy 讀 ../shared/taxonomy.json）：
#   docker build -f ai-service-python/Dockerfile -t bytebites-ai .
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /usr/local/bin/uv
WORKDIR /repo/ai-service-python
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY ai-service-python/pyproject.toml ai-service-python/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY shared /repo/shared
COPY ai-service-python/app ./app
COPY ai-service-python/evals ./evals
EXPOSE 8000
# 注意：單 worker。session 之外仍有 in-process 快取（LINE media/profile、
# 停車提醒 dict、embedding cache），開多 worker 會出現狀態不一致。
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
