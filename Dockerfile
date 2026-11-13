# ---- Stage 1: build the React frontend -------------------------------------------------
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime -------------------------------------------------------------
FROM python:3.12-slim AS runtime
WORKDIR /app

# System deps needed by reportlab/Pillow for font/image handling.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-build /app/frontend/dist ./frontend_dist

ENV FRONTEND_DIST=/app/frontend_dist \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data/signatures /data/receipts
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app"]
