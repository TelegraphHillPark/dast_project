#!/bin/sh
set -e

DOMAIN="${DOMAIN:-localhost}"
LE_CERT="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
LE_KEY="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
SS_DIR="/etc/nginx/certs"
SS_CERT="${SS_DIR}/fullchain.pem"
SS_KEY="${SS_DIR}/privkey.pem"

# ── Выбираем сертификат ────────────────────────────────────────────────────
if [ -f "${LE_CERT}" ] && [ -f "${LE_KEY}" ]; then
    echo "[nginx] Используем Let's Encrypt сертификат для ${DOMAIN}"
    SSL_CERT_PATH="${LE_CERT}"
    SSL_KEY_PATH="${LE_KEY}"
else
    echo "[nginx] Let's Encrypt сертификат не найден — генерируем self-signed для ${DOMAIN}"
    mkdir -p "${SS_DIR}"
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "${SS_KEY}" \
        -out "${SS_CERT}" \
        -subj "/CN=${DOMAIN}" \
        -addext "subjectAltName=IP:${DOMAIN},DNS:${DOMAIN}" 2>/dev/null || \
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "${SS_KEY}" \
        -out "${SS_CERT}" \
        -subj "/CN=${DOMAIN}" 2>/dev/null
    SSL_CERT_PATH="${SS_CERT}"
    SSL_KEY_PATH="${SS_KEY}"
fi

# ── Подставляем переменные в шаблон конфига ────────────────────────────────
export DOMAIN SSL_CERT_PATH SSL_KEY_PATH
envsubst '${DOMAIN} ${SSL_CERT_PATH} ${SSL_KEY_PATH}' \
    < /etc/nginx/nginx.conf.template \
    > /etc/nginx/nginx.conf

echo "[nginx] Конфиг сгенерирован. Запускаем nginx (domain=${DOMAIN})"
exec "$@"
