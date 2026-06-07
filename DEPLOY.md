# Деплой DAST на VDS через GitHub Actions

## Что получится в итоге

```
GitHub repo
    │
    ├── push to main ──► CI (тесты) ──► CD (deploy via SSH)
    │
VDS (Ubuntu 22)
    ├── dast_nginx     :80, :443  — фронт + reverse proxy
    ├── dast_backend   internal   — FastAPI
    ├── dast_worker    internal   — сканер
    ├── dast_db        internal   — PostgreSQL
    ├── dast_redis     internal   — Redis
    └── dvwa           :8888      — уязвимое приложение для тестов
```

---

## Шаг 1 — Подготовка VDS

**Минимальные требования:** Ubuntu 22.04, 2 vCPU, 4 GB RAM, 40 GB SSD.

Подключись по SSH как root:

```bash
ssh root@<IP_СЕРВЕРА>
```

### 1.1 Установи Docker

```bash
apt update && apt upgrade -y
apt install -y ca-certificates curl gnupg

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Проверь:

```bash
docker --version
docker compose version
```

### 1.2 Создай deploy-пользователя

```bash
useradd -m -s /bin/bash deploy
usermod -aG docker deploy
```

---

## Шаг 2 — SSH-ключ для GitHub Actions

На **VDS** (от имени `deploy`):

```bash
su - deploy
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions -N ""
cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
cat ~/.ssh/github_actions   # ← приватный ключ — скопируй его целиком
```

---

## Шаг 3 — Клонируй репо на VDS

```bash
su - deploy
git clone https://github.com/<ТВО_USERNAME>/<ИМЯ_РЕПО>.git /home/deploy/dast
cd /home/deploy/dast
```

### 3.1 Создай .env.prod

```bash
cp .env.example .env.prod
nano .env.prod
```

Заполни обязательные поля:

```env
POSTGRES_PASSWORD=<сложный пароль>
REDIS_PASSWORD=<сложный пароль>
SECRET_KEY=$(openssl rand -hex 32)   # сгенерируй прямо тут
FRONTEND_URL=https://<твой-домен>
ALLOWED_ORIGINS=https://<твой-домен>
DVWA_DB_ROOT_PASSWORD=<пароль>
DVWA_DB_PASSWORD=<пароль>
```

---

## Шаг 4 — GitHub: добавь секреты

Открой **GitHub → твой репо → Settings → Secrets and variables → Actions → New repository secret** и добавь:

| Название              | Значение                                          |
|-----------------------|---------------------------------------------------|
| `VDS_HOST`            | IP или домен VDS                                  |
| `VDS_USER`            | `deploy`                                          |
| `VDS_SSH_KEY`         | приватный ключ из шага 2 (весь текст с `-----BEGIN`) |
| `VDS_PORT`            | `22`                                              |
| `VDS_DEPLOY_PATH`     | `/home/deploy/dast`                               |

---

## Шаг 5 — Первый деплой вручную

Первый раз запускаем руками, чтобы убедиться, что всё работает:

```bash
su - deploy
cd /home/deploy/dast
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Подожди 1-2 минуты, затем:

```bash
docker compose -f docker-compose.prod.yml ps
```

Все сервисы должны быть `running (healthy)`.

Применяем миграции:

```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

Создаём первого администратора:

```bash
docker compose -f docker-compose.prod.yml exec backend python -m app.cli create-admin \
  --email admin@example.com \
  --password "ChangeMe123!"
```

---

## Шаг 6 — SSL-сертификат (Let's Encrypt)

> Нужен домен, указывающий на IP VDS.

```bash
# Сначала временно открой порт 80 и подними certbot
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d your-domain.com \
  --email your@email.com \
  --agree-tos --no-eff-email
```

Обнови `docker/nginx/nginx.conf` — замени пути к сертификатам на:

```nginx
ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
```

Перезапусти nginx:

```bash
docker compose -f docker-compose.prod.yml restart nginx
```

Certbot в `docker-compose.prod.yml` уже настроен на автообновление каждые 12 часов.

---

## Шаг 7 — Настройка GitHub Actions (автодеплой)

После шагов 4-5 каждый `git push` в ветку `main` будет:

1. Запускать **CI**: тесты backend + type check frontend  
2. При успехе запускать **CD**: SSH на VDS → `git pull` → `docker compose build` → `docker compose up -d` → `alembic upgrade head`

Посмотреть статус: **GitHub → Actions**.

---

## Шаг 8 — DVWA для тестирования DAST

DVWA поднимается автоматически в `docker-compose.prod.yml` на порту `8888`.

**Первый запуск:** открой `http://<IP>:8888/setup.php` и нажми **Create / Reset Database**.

**Логин:** `admin` / `password`

**Настрой уровень уязвимости:** DVWA Security → `Low`.

**В DAST-сканере** добавь цель:
- URL: `http://localhost:8888` (или `http://<IP>:8888`)
- Auth: Form Login
  - Login URL: `http://localhost:8888/login.php`
  - Username field: `username`
  - Password field: `password`
  - Username: `admin`
  - Password: `password`

---

## Шаг 9 — Полезные команды на VDS

```bash
# Логи конкретного сервиса
docker compose -f docker-compose.prod.yml logs -f backend

# Перезапустить один сервис
docker compose -f docker-compose.prod.yml restart worker

# Обновить вручную (без пуша в git)
cd /home/deploy/dast
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build --no-deps backend worker nginx

# Бэкап БД
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U dast dast > backup_$(date +%Y%m%d).sql

# Очистить старые образы
docker image prune -f
```

---

## Шаг 10 — Firewall (UFW)

```bash
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 8888/tcp  # DVWA (можно закрыть после тестов)
ufw enable
ufw status
```

---

## Схема CI/CD

```
git push main
     │
     ▼
.github/workflows/ci.yml
  ├── backend: pytest (SQLite in-memory)
  └── frontend: tsc --noEmit + npm run build
           │ (если всё зелёно)
           ▼
.github/workflows/deploy.yml
  ├── scp docker-compose.prod.yml → VDS
  └── ssh → VDS:
        git pull origin main
        docker compose build
        docker compose up -d
        alembic upgrade head
        docker image prune -f
```

---

## Структура файлов CI/CD

```
dast_project/
├── .github/
│   └── workflows/
│       ├── ci.yml          ← тесты на каждый push/PR
│       └── deploy.yml      ← деплой при push в main
├── docker-compose.yml      ← локальная разработка
├── docker-compose.prod.yml ← production (VDS)
├── .env.example            ← шаблон переменных окружения
├── backend/
│   ├── pytest.ini
│   ├── requirements.txt    ← aiosqlite добавлен для тестов
│   └── tests/
│       ├── conftest.py     ← фикстуры, SQLite in-memory
│       ├── test_auth.py    ← тесты регистрации/логина
│       └── test_scans.py   ← тесты CRUD сканов
```
