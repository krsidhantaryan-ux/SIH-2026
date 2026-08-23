# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS web-build
WORKDIR /workspace/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=demo \
    PORT=8000
WORKDIR /app
RUN groupadd --system cyclone && useradd --system --gid cyclone --home /app cyclone
COPY requirements-api.txt ./
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r requirements-api.txt
COPY app/ ./app/
COPY data/processed/index.csv ./data/processed/index.csv
COPY models/ ./models/
COPY --from=web-build /workspace/web/dist ./web/dist
RUN chown -R cyclone:cyclone /app
USER cyclone
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3))['status']=='ok'"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
