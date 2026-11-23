# Rsafe as one container: the API serves the built frontend on a single port.
# Build:  docker build -t rsafe .
# Run:    docker run --rm -p 8000:8000 rsafe      then open http://localhost:8000

# ---- 1. build the frontend -------------------------------------------------------------
FROM node:20-alpine AS web
WORKDIR /srv/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. the API, serving that build ----------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RSAFE_DEMO_MODE=1 \
    RSAFE_COOKIE_SECURE=1 \
    RSAFE_STATIC_DIR=/srv/frontend/dist \
    PORT=8000
WORKDIR /srv/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./
COPY --from=web /srv/frontend/dist /srv/frontend/dist
COPY deploy/start.sh /srv/start.sh
RUN chmod +x /srv/start.sh && useradd --create-home rsafe && chown -R rsafe /srv
USER rsafe
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health')"
CMD ["/srv/start.sh"]
