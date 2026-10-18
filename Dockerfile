FROM node:24-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS python-deps
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/backend PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=python-deps /app/.venv /app/.venv
COPY backend/ backend/
COPY --from=frontend /build/frontend/dist frontend/dist/
RUN mkdir -p /var/lib/solids && chown 65532:65532 /var/lib/solids && chmod 0700 /var/lib/solids
USER 65532:65532
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
CMD ["uvicorn", "solids.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
