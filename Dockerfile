FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY 2026_World_Cup_Results.md /app/2026_World_Cup_Results.md
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist
COPY deploy/docker-entrypoint.sh /app/docker-entrypoint.sh

RUN mkdir -p /app/seed-data /app/backend/data \
    && cp -R /app/backend/data/. /app/seed-data/ 2>/dev/null || true

EXPOSE 8000

CMD ["sh", "/app/docker-entrypoint.sh"]
