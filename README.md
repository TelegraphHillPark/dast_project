# DAST Analyzer

![CI](https://github.com/TelegraphHillPark/dast_project/actions/workflows/ci.yml/badge.svg)
![Version](https://img.shields.io/badge/version-0.4.0-blue)

Инструмент динамического анализа защищённости веб-приложений (DAST).  
Обходит сайт как браузер, находит формы и параметры, прогоняет нагрузки (SQLi, XSS, SSRF, Open Redirect, Header Injection) и показывает что нашёл.

## Что умеет

- Асинхронный краулер — ссылки, формы, JS-маршруты, API-эндпоинты
- Поддержка аутентификации на целевом сайте: cookie, HTTP Basic, Bearer-токен, form login
- Сигнатурный анализатор (ищет ошибки БД, отражённые нагрузки) + эвристический (время ответа, размер тела, статус)
- Управление сканом в реальном времени: пауза, возобновление, остановка, live-лог
- JSON-отчёт с подробностями по каждой уязвимости (payload, evidence, рекомендация)
- Аутентификация: логин/пароль, двухфакторная (TOTP), OAuth через GitHub
- Разграничение ролей admin / user, панель администратора
- REST API с поддержкой API-ключей

## Стек

| Слой | Технология |
|------|-----------|
| Бэкенд | Python 3.11 + FastAPI + SQLAlchemy 2.0 (asyncpg) |
| База данных | PostgreSQL 16 |
| Очередь | Redis 7 |
| Фронтенд | React 18 + Vite + TypeScript |
| Прокси | Nginx 1.27 + TLS |
| CI/CD | GitHub Actions |

---

## Быстрый старт

Нужны: Docker + Docker Compose v2, Node.js 20+.

```bash
git clone https://github.com/TelegraphHillPark/dast_project.git
cd dast_project

# Настроить окружение
cp .env.example .env
# Открыть .env и задать POSTGRES_PASSWORD, REDIS_PASSWORD, SECRET_KEY

# Собрать фронтенд (nginx копирует его при сборке образа)
cd frontend && npm install && npm run build && cd ..

# Поднять всё
docker compose up --build -d

# Применить миграции БД
docker compose exec backend alembic upgrade head
```

Приложение доступно по адресу **https://localhost** (самоподписанный сертификат — браузер покажет предупреждение, это нормально для локального запуска).

Swagger UI (только в dev-режиме): `https://localhost/api/docs`

### Назначить первого администратора

```bash
docker compose exec db psql -U dast dast \
  -c "UPDATE users SET role='admin' WHERE email='ваш@email.com';"
```

---

## Разработка

```bash
# Backend
cd backend
pip install -r requirements.txt
cp ../.env.example .env   # задать ENVIRONMENT=development, DATABASE_URL, REDIS_URL
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev   # http://localhost:5173, проксирует /api на :8000
```

---

## Полезные команды

```bash
# Логи конкретного сервиса
docker compose logs -f backend
docker compose logs -f worker

# Остановить
docker compose down

# Остановить и удалить все данные (осторожно)
docker compose down -v
```

---

## Документация

- [Системные спецификации](docs/SYSTEM_SPECS.md)
- [Руководство пользователя](docs/USER_SPECS.md)
- [Развёртывание](docs/DEPLOY.md)
- [Безопасность](docs/SECURITY.md)

---

## Лицензия

MIT
