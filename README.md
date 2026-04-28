# DAST Analyzer

![CI](https://github.com/TelegraphHillPark/dast_project/actions/workflows/ci.yml/badge.svg)
![Version](https://img.shields.io/badge/version-0.2.0-blue)

Инструмент динамического анализа защищённости веб-приложений (DAST).  
Автоматически обходит приложение, обнаруживает уязвимости из OWASP Top 10 посредством инъекции полезных нагрузок.

## Возможности

- Асинхронный краулер — ссылки, формы, JS-маршруты, API-эндпоинты
- Движок полезных нагрузок — встроенные словари для SQLi, XSS, SSRF, Open Redirect, Header Injection *(Спринт 4)*
- Сигнатурный и эвристический анализаторы *(Спринт 4)*
- Управление сканированием — пауза, возобновление, настройка глубины и таймаутов
- Отчёты в форматах PDF и JSON по классификации OWASP Top 10 *(Спринт 5)*
- Аутентификация — логин/пароль, двухфакторная (TOTP), OAuth через GitHub и Google
- Разграничение ролей — admin / user
- Панель администратора — управление пользователями, назначение ролей, управление сессиями и API-токенами
- REST API с защитой API-ключами и ограничением запросов (rate limiting)
- Трассировка запросов через UUIDv7 Request ID

## Стек технологий

| Слой | Технология |
|------|-----------|
| Бэкенд | Python 3.11 + FastAPI + SQLAlchemy 2.0 |
| База данных | PostgreSQL 16 |
| Очередь | Redis 7 |
| Фронтенд | React 18 + Vite (TypeScript) |
| Прокси | Nginx + TLS |
| CI/CD | GitHub Actions (lint → test → build → deploy) |

---

## Требования

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2
- [Node.js 20+](https://nodejs.org/) (LTS) с npm — для сборки фронтенда

---

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone https://github.com/TelegraphHillPark/dast_project.git
cd dast_project
```

### 2. Настроить окружение

```bash
cp .env.example .env
```

Открыть `.env` и заполнить обязательные переменные:

```env
POSTGRES_PASSWORD=надёжный_пароль
REDIS_PASSWORD=пароль_redis
SECRET_KEY=минимум_32_случайных_символа
ALLOWED_ORIGINS=https://ваш-домен.com
ENVIRONMENT=production
```

OAuth (опционально — оставить пустым для отключения):

```env
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

### 3. Собрать фронтенд

Образ Nginx копирует скомпилированный фронтенд при сборке, поэтому его нужно собрать заранее:

```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Запустить все сервисы

```bash
docker compose up --build -d
```

Запускаются: PostgreSQL, Redis, FastAPI бэкенд, фоновый воркер и Nginx.

### 5. Применить миграции базы данных

```bash
docker compose exec backend alembic upgrade head
```

### 6. Проверить работоспособность

```bash
curl -k https://localhost/health
# {"status":"ok","version":"0.2.0"}
```

Приложение доступно по адресу **https://localhost**.  
Документация API (только в режиме разработки): `https://localhost/api/docs`

---

## Настройка для разработки

### Бэкенд

```bash
cd backend
pip install -r requirements.txt

# Скопировать и настроить .env
cp ../.env.example .env
# Установить ENVIRONMENT=development, DATABASE_URL и REDIS_URL, указывающие на локальные сервисы

# Применить миграции
alembic upgrade head

# Запустить с автоперезагрузкой
uvicorn app.main:app --reload
```

В режиме разработки (`ENVIRONMENT=development`) таблицы также создаются автоматически через SQLAlchemy при старте.

### Фронтенд

```bash
cd frontend
npm install
npm run dev
```

Dev-сервер Vite стартует на `http://localhost:5173` и проксирует запросы `/api` на бэкенд.

### Полезные команды Alembic

```bash
# Применить все миграции
alembic upgrade head

# Создать новую миграцию после изменений моделей
alembic revision --autogenerate -m "описание"

# Откатить последнюю миграцию
alembic downgrade -1
```

---

## Полезные команды Docker

```bash
# Просмотр логов бэкенда
docker compose logs -f backend

# Просмотр логов воркера
docker compose logs -f worker

# Остановить все сервисы
docker compose down

# Остановить и удалить все данные (осторожно!)
docker compose down -v
```

---

## TLS-сертификат

По умолчанию Nginx генерирует **самоподписанный сертификат** — браузеры покажут предупреждение.  
Для продакшена заменить на реальный:

1. Поместить `server.crt` и `server.key` в `docker/nginx/certs/`
2. Пересобрать образ Nginx: `docker compose build nginx && docker compose up -d nginx`

---

## Назначение роли администратора

Первый администратор создаётся напрямую через БД:

```bash
docker compose exec db psql -U dast dast \
  -c "UPDATE users SET role='admin' WHERE email='ваш@email.com';"
```

После этого через панель администратора (`/admin`) или API (`PATCH /api/admin/users/{id}`) можно повышать роли других пользователей.

---

## Документация

- [Системные спецификации](docs/SYSTEM_SPECS.md)
- [Руководство пользователя](docs/USER_SPECS.md)
- [Руководство по развёртыванию](docs/DEPLOY.md)
- [Безопасность](docs/SECURITY.md)

---

## Лицензия

MIT
