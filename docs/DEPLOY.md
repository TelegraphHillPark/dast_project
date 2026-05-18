# Руководство по развёртыванию — DAST Analyzer

## Содержание

1. [Требования](#1-требования)
2. [Локальный запуск](#2-локальный-запуск)
3. [Развёртывание на сервере](#3-развёртывание-на-сервере)
4. [TLS-сертификат (Certbot)](#4-tls-сертификат-certbot)
5. [Первоначальная настройка](#5-первоначальная-настройка)
6. [Обслуживание](#6-обслуживание)
7. [Резервное копирование](#7-резервное-копирование)
8. [CI/CD автодеплой](#8-cicd-автодеплой)

---

## 1. Требования

### Обязательное ПО

- **Docker** 24.x или новее
- **Docker Compose** v2 (`docker compose`, не `docker-compose`)
- **Node.js** 20 LTS + npm — нужен только один раз для сборки фронтенда

Проверить:
```bash
docker --version          # Docker version 24.x
docker compose version    # Docker Compose version v2.x
node --version            # v20.x
```

### Сервер (для продакшена)

| Параметр | Минимум | Рекомендуется |
|---|---|---|
| ОС | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 ГБ | 8 ГБ |
| Диск | 20 ГБ SSD | 50 ГБ SSD |
| Порты | 80, 443 | 80, 443 |

---

## 2. Локальный запуск

```bash
# 1. Клонировать
git clone https://github.com/TelegraphHillPark/dast_project.git
cd dast_project

# 2. Настроить .env
cp .env.example .env
```

Открыть `.env` и задать:

```env
POSTGRES_PASSWORD=местный_пароль_для_разработки
REDIS_PASSWORD=местный_redis_пароль
SECRET_KEY=минимум_32_случайных_символа_здесь_1234
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost,https://localhost
```

```bash
# 3. Собрать фронтенд
cd frontend
npm install
npm run build
cd ..

# 4. Поднять всё
docker compose up --build -d

# 5. Миграции
docker compose exec backend alembic upgrade head
```

Приложение: **https://localhost** (самоподписанный сертификат — нажмите «Перейти всё равно»).  
Swagger: **https://localhost/api/docs** (только при `ENVIRONMENT=development`).

---

## 3. Развёртывание на сервере

### 3.1 Подготовка сервера

```bash
# Установить Docker (Ubuntu)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Перелогиниться

# Проверить
docker compose version
```

### 3.2 Получить код

```bash
git clone https://github.com/TelegraphHillPark/dast_project.git
cd dast_project
```

### 3.3 Настроить .env

```bash
cp .env.example .env
nano .env
```

Минимальный набор для продакшена:

```env
POSTGRES_DB=dast
POSTGRES_USER=dast
POSTGRES_PASSWORD=сгенерируйте_надёжный_пароль_минимум_20_символов
REDIS_PASSWORD=ещё_один_надёжный_пароль

SECRET_KEY=случайная_строка_минимум_32_символа_openssl_rand_hex_32
ENVIRONMENT=production
ALLOWED_ORIGINS=https://ваш-домен.com
FRONTEND_URL=https://ваш-домен.com

# OAuth GitHub (опционально)
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
```

Для генерации `SECRET_KEY`:
```bash
openssl rand -hex 32
```

### 3.4 Собрать фронтенд

```bash
cd frontend
npm install
npm run build
cd ..
```

### 3.5 Запустить

```bash
docker compose up --build -d
docker compose exec backend alembic upgrade head
```

Проверить что всё поднялось:

```bash
docker compose ps
# Все сервисы должны быть в состоянии "running" или "healthy"

curl -k https://localhost/health
# {"status":"ok","version":"0.4.0"}
```

---

## 4. TLS-сертификат (Certbot)

По умолчанию Nginx использует самоподписанный сертификат из `docker/nginx/certs/`. Для продакшена нужен нормальный — Certbot получит его бесплатно от Let's Encrypt.

### 4.1 Установить Certbot

```bash
sudo apt install certbot
```

### 4.2 Получить сертификат

Перед этим убедитесь, что порт 80 открыт и ваш домен указывает на сервер. Временно остановить Nginx:

```bash
docker compose stop nginx
```

Получить сертификат (standalone-режим):

```bash
sudo certbot certonly --standalone -d ваш-домен.com
```

Файлы окажутся в `/etc/letsencrypt/live/ваш-домен.com/`.

### 4.3 Скопировать сертификат в проект

```bash
sudo cp /etc/letsencrypt/live/ваш-домен.com/fullchain.pem docker/nginx/certs/server.crt
sudo cp /etc/letsencrypt/live/ваш-домен.com/privkey.pem docker/nginx/certs/server.key
sudo chown $USER:$USER docker/nginx/certs/server.*
```

### 4.4 Обновить конфиг Nginx

Откройте `docker/nginx/nginx.conf` и замените `server_name localhost;` на ваш домен:

```nginx
server_name ваш-домен.com;
```

### 4.5 Пересобрать и запустить Nginx

```bash
docker compose build nginx
docker compose up -d nginx
```

### 4.6 Автообновление сертификата

Let's Encrypt сертификаты действуют 90 дней. Добавьте cron для обновления:

```bash
sudo crontab -e
```

Добавить строку (обновляет ежемесячно):

```
0 3 1 * * docker compose -f /путь/к/проекту/docker-compose.yml stop nginx && certbot renew --standalone && cp /etc/letsencrypt/live/ваш-домен.com/fullchain.pem /путь/к/проекту/docker/nginx/certs/server.crt && cp /etc/letsencrypt/live/ваш-домен.com/privkey.pem /путь/к/проекту/docker/nginx/certs/server.key && docker compose -f /путь/к/проекту/docker-compose.yml build nginx && docker compose -f /путь/к/проекту/docker-compose.yml up -d nginx
```

---

## 5. Первоначальная настройка

### Создать первого администратора

После первого запуска и регистрации первого пользователя — назначьте ему роль администратора:

```bash
docker compose exec db psql -U dast dast \
  -c "UPDATE users SET role='admin' WHERE email='ваш@email.com';"
```

После этого через панель `/admin` можно повышать роли других пользователей без прямого доступа к БД.

### Настроить OAuth GitHub (опционально)

1. На GitHub: Settings → Developer settings → OAuth Apps → New OAuth App
2. Authorization callback URL: `https://ваш-домен.com/api/auth/oauth/github/callback`
3. Скопировать Client ID и Client Secret в `.env`
4. Перезапустить backend: `docker compose restart backend`

---

## 6. Обслуживание

### Просмотр логов

```bash
# Все сервисы
docker compose logs -f

# Конкретный сервис
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f nginx

# Последние 100 строк
docker compose logs --tail=100 backend
```

### Перезапуск сервиса

```bash
docker compose restart backend
docker compose restart worker
```

### Обновление приложения

```bash
git pull
cd frontend && npm install && npm run build && cd ..
docker compose up --build -d
docker compose exec backend alembic upgrade head
```

### Применить миграции вручную

```bash
# Посмотреть текущую версию
docker compose exec backend alembic current

# Применить все миграции
docker compose exec backend alembic upgrade head

# Откатить последнюю
docker compose exec backend alembic downgrade -1
```

### Очистить Docker-артефакты

```bash
# Удалить неиспользуемые образы
docker image prune -f

# Удалить всё неиспользуемое (осторожно)
docker system prune -f
```

---

## 7. Резервное копирование

### Бэкап базы данных

```bash
docker compose exec db pg_dump -U dast dast | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Восстановление

```bash
gunzip -c backup_20260101_120000.sql.gz | docker compose exec -T db psql -U dast dast
```

### Бэкап загруженных файлов (аватары, словари)

```bash
docker run --rm -v dast_project_uploads_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/uploads_$(date +%Y%m%d).tar.gz /data
```

> Данные PostgreSQL и Redis хранятся в Docker volumes `postgres_data` и `redis_data`. При `docker compose down -v` они **удаляются** — делайте бэкап перед этой командой.

---

## 8. CI/CD автодеплой

Конфигурация в `.github/workflows/ci.yml`. При пуше тега `v*.*.*` запускается автоматический деплой.

### Необходимые секреты в GitHub

| Секрет | Описание |
|---|---|
| `SSH_PRIVATE_KEY` | Приватный SSH-ключ для подключения к серверу |
| `DEPLOY_HOST` | IP или домен сервера |
| `DEPLOY_USER` | Пользователь SSH |
| `DEPLOY_PATH` | Путь к папке проекта на сервере |

### Настройка SSH-доступа

На сервере:
```bash
# Создать ключ для деплоя (если нет)
ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N ""

# Добавить публичный ключ в authorized_keys
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys
```

Содержимое `~/.ssh/deploy_key` (приватный ключ) добавить в GitHub Secrets как `SSH_PRIVATE_KEY`.

### Деплой вручную

```bash
git tag v0.4.1
git push origin v0.4.1
```

После этого CI автоматически: запустит тесты → соберёт Docker образ → просканирует Trivy → задеплоит на сервер.
