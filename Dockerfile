# lectern: the web app and the API from one uvicorn process. Build from the repository root:
#   docker build -t lectern .
# Base images are pinned to exact versions; pin digests too if your registry policy needs it.

# 1. The web app (static files).
FROM node:22.21.0-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# 2. The Python runtime.
FROM python:3.12.12-slim-bookworm AS app
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY backend/lectern backend/lectern
# EXTRAS=s3 adds boto3 for an S3 or S3-compatible blob store.
ARG EXTRAS=""
RUN uv sync --frozen --no-dev --no-editable ${EXTRAS:+--extra $EXTRAS}
COPY --from=web /web/dist /app/static

RUN useradd --system --uid 10001 --home /data lectern && mkdir -p /data && chown lectern /data
USER lectern
ENV PATH=/app/.venv/bin:$PATH \
    LECTERN_STATIC=/app/static \
    LECTERN_DB=/data/lectern.db \
    LECTERN_BLOBS=/data/blobs \
    PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["lectern", "serve", "--host", "0.0.0.0", "--port", "8000"]
