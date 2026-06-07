# ── Stage 1: build React frontend ────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci --silent

COPY frontend/ ./

# VITE_API_URL defaults to /api so the SPA hits the same origin
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ── Stage 2: nginx ────────────────────────────────────────────────────────────
FROM nginx:1.25-alpine

# openssl для генерации self-signed сертификата при первом запуске
RUN apk add --no-cache openssl

# Собранный фронтенд
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

# Конфиг-шаблон (переменные подставляются через envsubst в entrypoint)
COPY docker/nginx/nginx.conf.template /etc/nginx/nginx.conf.template

# Entrypoint: генерирует self-signed cert если нет LE-сертификата
COPY docker/nginx/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80 443

ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
