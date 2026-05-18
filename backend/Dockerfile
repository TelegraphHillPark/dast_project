FROM python:3.11-slim AS builder

WORKDIR /app

# Системные зависимости для WeasyPrint и psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-xlib-2.0-0 \
    shared-mime-info fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    gosu \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-xlib-2.0-0 \
    shared-mime-info fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

# Непривилегированный пользователь (entrypoint переключится на него после chown volume)
RUN useradd --no-create-home --shell /bin/false appuser && \
    mkdir -p /app/wordlists /app/uploads/avatars && \
    chown -R appuser:appuser /app && \
    chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
