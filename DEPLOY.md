# Деплой DAST на VDS

## Требования к серверу
- Ubuntu 22.04, минимум 2 CPU / 4 GB RAM / 20 GB диск
- Открытые порты: 22 (SSH), 80, 443, 8888 (DVWA)
- Белый IP адрес

---

## Шаг 1 — Установка Docker на VDS

```bash
# Подключись к серверу
ssh root@YOUR_SERVER_IP

# Установи Docker
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

# Добавь пользователя deploy
adduser deploy
usermod -aG docker deploy
su - deploy
```

---

## Шаг 2 — SSH-ключ для GitHub Actions

```bash
# На сервере (под пользователем deploy):
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy -N ""

# Добавь публичный ключ в authorized_keys
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Скопируй приватный ключ — он пойдёт в GitHub Secrets
cat ~/.ssh/github_deploy
```

---

## Шаг 3 — Клонирование проекта

```bash
# На сервере:
git clone https://github.com/<user>/<repo>.git /home/deploy/dast
cd /home/deploy/dast
cp .env.example .env.prod
```

Отредактируй `.env.prod`:

```bash
nano .env.prod
```

Минимальные обязательные изменения:

```env
POSTGRES_PASSWORD=<strong_password>
REDIS_PASSWORD=<strong_password>
SECRET_KEY=$(openssl rand -hex 32)   # запусти команду, вставь результат

# Вместо домена используй белый IP или IP.nip.io:
DOMAIN=YOUR_SERVER_IP              # → self-signed сертификат (сразу работает)
# DOMAIN=YOUR_SERVER_IP.nip.io    # → позволит получить Let's Encrypt сертификат

FRONTEND_URL=https://YOUR_SERVER_IP
ALLOWED_ORIGINS=https://YOUR_SERVER_IP
```

> **Про SSL:**
> - `DOMAIN=1.2.3.4` — nginx сам генерирует self-signed сертификат. Браузер покажет предупреждение, но всё работает. Подходит для разработки и тестирования.
> - `DOMAIN=1.2.3.4.nip.io` — бесплатный DNS-сервис, который резолвит `*.nip.io` в IP. Позволяет получить настоящий Let's Encrypt сертификат (см. Шаг 6).

---

## Шаг 4 — GitHub Secrets

В репозитории: **Settings → Secrets and variables → Actions → New repository secret**

| Секрет | Значение |
|---|---|
| `VDS_HOST` | Белый IP сервера |
| `VDS_USER` | `deploy` |
| `VDS_SSH_KEY` | Содержимое `~/.ssh/github_deploy` (приватный ключ) |
| `VDS_PORT` | `22` |
| `VDS_DEPLOY_PATH` | `/home/deploy/dast` |

---

## Шаг 5 — Первый запуск (вручную)

```bash
cd /home/deploy/dast

# Поднять все сервисы
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Дождаться запуска backend (30-60 секунд)
docker compose -f docker-compose.prod.yml logs -f backend

# Применить миграции БД
docker compose -f docker-compose.prod.yml --env-file .env.prod \
    exec backend alembic upgrade head

# Создать администратора
docker compose -f docker-compose.prod.yml --env-file .env.prod \
    exec backend python -m app.cli create-admin \
    --email admin@example.com --password YOUR_ADMIN_PASSWORD
```

Приложение доступно:
- `https://YOUR_SERVER_IP` — основное приложение (self-signed cert)
- `http://YOUR_SERVER_IP:8888` — DVWA

---

## Шаг 6 — Let's Encrypt (только если используешь nip.io или домен)

```bash
# Убедись что nginx запущен и отвечает на порту 80
curl http://YOUR_SERVER_IP.nip.io

# Получить сертификат (замени email и домен)
docker compose -f docker-compose.prod.yml --env-file .env.prod \
    run --rm certbot certbot certonly \
    --webroot -w /var/www/certbot \
    -d YOUR_SERVER_IP.nip.io \
    --email your@email.com \
    --agree-tos --no-eff-email

# Перезапустить nginx — он найдёт LE-сертификат и переключится на него
docker compose -f docker-compose.prod.yml --env-file .env.prod \
    restart nginx
```

После этого `https://YOUR_SERVER_IP.nip.io` будет с настоящим сертификатом. Обнови `.env.prod`:
```env
DOMAIN=YOUR_SERVER_IP.nip.io
FRONTEND_URL=https://YOUR_SERVER_IP.nip.io
ALLOWED_ORIGINS=https://YOUR_SERVER_IP.nip.io
```

---

## Шаг 7 — Автодеплой через GitHub Actions

После настройки секретов каждый `git push main` будет:
1. Запускать CI (тесты)
2. При успехе — деплоить на VDS:
   - `git pull`
   - `docker compose build`
   - `docker compose up -d`
   - `alembic upgrade head`

---

## Шаг 8 — Настройка DVWA

1. Открой `http://YOUR_SERVER_IP:8888/setup.php`
2. Нажми **Create / Reset Database**
3. Войди: `admin` / `password`
4. В DAST-приложении добавь цель: `http://dvwa:80` (внутренняя сеть) или `http://YOUR_SERVER_IP:8888`

---

## Шаг 9 — Полезные команды

```bash
# Логи конкретного сервиса
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f worker
docker compose -f docker-compose.prod.yml logs -f nginx

# Перезапустить сервис
docker compose -f docker-compose.prod.yml restart backend

# Статус всех контейнеров
docker compose -f docker-compose.prod.yml ps

# Войти в контейнер backend
docker compose -f docker-compose.prod.yml exec backend sh

# Бэкап PostgreSQL
docker compose -f docker-compose.prod.yml exec db \
    pg_dump -U dast dast > backup_$(date +%Y%m%d).sql

# Очистить неиспользуемые образы
docker image prune -f
```

---

## Шаг 10 — Файрволл (UFW)

```bash
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 8888/tcp  # DVWA (можно закрыть если не нужен снаружи)
ufw enable
ufw status
```
