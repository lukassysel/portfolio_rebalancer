# One container: FastAPI serves /api/* and the built React SPA (doc 07 §8 item 9). Node is used only at build time.
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npx vite build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 WEB_DIST=/app/web/dist
WORKDIR /app
COPY pyproject.toml README.md ./
COPY rebalancer/ rebalancer/
RUN pip install --no-cache-dir .
COPY --from=web /web/dist web/dist
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/api/health' % __import__('os').environ.get('PORT','8000')).status==200 else 1)"
CMD ["sh", "-c", "uvicorn rebalancer.api.app:app --host 0.0.0.0 --port ${PORT} --workers 1"]
