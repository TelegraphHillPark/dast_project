# DAST Analyzer — Системные спецификации

## 1. Обзор

DAST Analyzer — автоматизированный инструмент динамического анализа защищённости (Dynamic Application Security Testing), который обходит веб-приложения, генерирует атакующие полезные нагрузки и обнаруживает уязвимости из OWASP Top 10.

**Версия:** 0.2.0  
**Стек:** Python 3.11 · FastAPI · PostgreSQL 16 · Redis 7 · React 18 · Nginx

---

## 2. Архитектура

### 2.1 Схема компонентов

```
Браузер / CLI
    │
    ▼
Nginx (443 TLS / редирект с 80)
    ├── Статика       → React SPA (frontend/dist)
    └── /api/*        → FastAPI Бэкенд (:8000)
                            │
                ┌───────────┼────────────┐
                ▼           ▼            ▼
          PostgreSQL      Redis       Воркер
          (состояние)  (очередь)  (Оркестратор + Краулер)
```

### 2.2 Обязанности компонентов

| Компонент | Ответственность |
|---|---|
| **Nginx** | Завершение TLS, раздача статики, обратный прокси к бэкенду |
| **FastAPI Бэкенд** | REST API, аутентификация, управление пользователями и сканами |
| **PostgreSQL** | Постоянное хранение: пользователи, сессии, сканы, уязвимости, словари |
| **Redis** | Очередь задач сканирования (`scan_queue` list), будущий pub/sub |
| **Воркер** | Извлекает задачи из Redis, запускает Оркестратор, сохраняет результаты в БД |
| **Оркестратор** | Управляет жизненным циклом скана (pending → running → finished/paused/failed) |
| **Краулер** | Асинхронный HTTP-обход целевого приложения |
| **Auth Manager** | Применяет аутентификацию к целевому приложению (cookie, Basic, Bearer, form) |
| **Движок нагрузок** | *(Спринт 4)* Генерация атакующих нагрузок из словарей |
| **Анализаторы** | *(Спринт 4)* Сигнатурное и эвристическое обнаружение уязвимостей |
| **Генератор отчётов** | *(Спринт 5)* Экспорт отчётов в PDF и JSON |

---

## 3. Схема базы данных

### 3.1 Сводка отношений

```
users ──< user_sessions
users ──< api_tokens
users ──< scans ──< vulnerabilities
users ──< wordlists
```

### 3.2 Таблицы

#### `users`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | UUIDv7 |
| email | VARCHAR(255) UNIQUE | |
| username | VARCHAR(64) UNIQUE | |
| hashed_password | TEXT | bcrypt |
| role | ENUM(admin, user) | |
| avatar_url | TEXT | |
| totp_secret | TEXT | Зашифрованный TOTP-сид |
| is_active | BOOLEAN | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

#### `user_sessions`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | |
| user_id | FK → users.id CASCADE | |
| token_hash | VARCHAR(64) | SHA-256 refresh-токена |
| user_agent | TEXT | |
| ip_address | VARCHAR(45) | IPv4/IPv6 |
| is_active | BOOLEAN | |
| created_at / expires_at | TIMESTAMPTZ | |

#### `api_tokens`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | |
| owner_id | FK → users.id CASCADE | |
| name | VARCHAR(128) | Метка |
| token_hash | VARCHAR(64) | SHA-256 |
| is_active | BOOLEAN | |
| last_used_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |

#### `scans`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | UUIDv7 |
| owner_id | FK → users.id CASCADE | |
| target_url | VARCHAR(2048) | |
| status | ENUM(pending, running, paused, finished, failed) | |
| max_depth | INTEGER | По умолчанию 3 |
| timeout_seconds | INTEGER | По умолчанию 3600 |
| excluded_paths | JSON | Массив префиксов путей |
| config | JSON | Конфиг аутентификации + crawl_stats после выполнения |
| created_at / started_at / finished_at | TIMESTAMPTZ | |

#### `vulnerabilities`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | |
| scan_id | FK → scans.id CASCADE | |
| vuln_type | ENUM(sqli, xss, ssrf, open_redirect, header_injection, broken_auth, sensitive_data, security_misconfiguration, other) | |
| severity | ENUM(critical, high, medium, low, info) | |
| url | VARCHAR(2048) | |
| parameter | VARCHAR(255) | |
| method | VARCHAR(10) | GET / POST / и др. |
| payload | TEXT | Использованная нагрузка |
| evidence | JSON | Фрагменты запроса/ответа |
| recommendation | TEXT | |
| created_at | TIMESTAMPTZ | |

#### `wordlists`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | |
| owner_id | FK → users.id CASCADE | |
| name | VARCHAR(128) | |
| file_path | TEXT | Путь на файловой системе |
| size_bytes | BIGINT | |
| is_builtin | BOOLEAN | |
| created_at | TIMESTAMPTZ | |

---

## 4. Спецификация REST API

Базовый URL: `/api`  
Аутентификация: `Authorization: Bearer <JWT>` или `X-API-Key: <токен>`

### 4.1 Аутентификация (`/api/auth`)

| Метод | Эндпоинт | Описание |
|---|---|---|
| POST | `/auth/register` | Регистрация нового пользователя (лимит 5/мин) |
| POST | `/auth/login` | Вход; возвращает `pre_auth_token`, если включена 2FA (лимит 10/мин) |
| POST | `/auth/2fa/setup` | Генерация TOTP-секрета и URI QR-кода |
| POST | `/auth/2fa/enable` | Активация 2FA по TOTP-коду |
| POST | `/auth/2fa/disable` | Деактивация 2FA |
| POST | `/auth/2fa/verify` | Проверка TOTP-кода (лимит 10/мин) |
| POST | `/auth/refresh` | Обновление access-токена |
| POST | `/auth/logout` | Отзыв сессии |
| GET | `/auth/oauth/github` | Редирект на OAuth GitHub |
| GET | `/auth/oauth/github/callback` | Callback OAuth GitHub |
| GET | `/auth/oauth/google` | Редирект на OAuth Google |
| GET | `/auth/oauth/google/callback` | Callback OAuth Google |

### 4.2 Пользователи (`/api/users`)

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/users/me` | Профиль текущего пользователя |
| PATCH | `/users/me` | Обновление имени пользователя / email |
| POST | `/users/me/change-password` | Смена пароля |
| POST | `/users/me/avatar` | Загрузка аватара (JPEG/PNG/WebP/GIF) |
| GET | `/users/me/sessions` | Список активных сессий |
| DELETE | `/users/me/sessions/{id}` | Отзыв сессии |
| GET | `/users/me/tokens` | Список API-токенов |
| POST | `/users/me/tokens` | Создание API-токена |
| DELETE | `/users/me/tokens/{id}` | Отзыв API-токена |

### 4.3 Сканирования (`/api/scans`)

| Метод | Эндпоинт | Описание |
|---|---|---|
| POST | `/scans` | Создание и постановка скана в очередь |
| GET | `/scans` | Список сканов пользователя |
| GET | `/scans/{id}` | Детали скана: уязвимости и статистика краулера |
| POST | `/scans/{id}/pause` | Пауза выполняющегося скана |
| POST | `/scans/{id}/resume` | Возобновление приостановленного скана (повторная постановка в очередь) |
| GET | `/scans/{id}/report` | JSON-отчёт об уязвимостях *(Спринт 5)* |
| GET | `/scans/{id}/report.pdf` | PDF-отчёт об уязвимостях *(Спринт 5)* |

**Тело запроса POST `/scans`:**
```json
{
  "target_url": "https://example.com",
  "max_depth": 3,
  "timeout_seconds": 3600,
  "excluded_paths": ["/logout", "/admin"],
  "auth_config": {
    "type": "none|cookie|basic|bearer|form",
    "cookie": "session=abc",
    "username": "user",
    "password": "pass",
    "bearer_token": "eyJ...",
    "login_url": "https://example.com/login",
    "username_field": "username",
    "password_field": "password"
  }
}
```

### 4.4 Администрирование (`/api/admin`) — требуется роль admin

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/admin/users` | Список всех пользователей |
| PATCH | `/admin/users/{id}` | Изменение роли / статуса пользователя |
| GET | `/admin/sessions/{user_id}` | Список сессий пользователя |
| DELETE | `/admin/sessions/{id}` | Деактивация сессии |
| GET | `/admin/tokens` | Список всех API-токенов |
| DELETE | `/admin/tokens/{id}` | Отзыв любого API-токена |

### 4.5 Словари (`/api/wordlists`) — *(Спринт 4)*

| Метод | Эндпоинт | Описание |
|---|---|---|
| POST | `/wordlists` | Загрузка словаря (.txt / .json, до 1 ГБ) |
| GET | `/wordlists` | Список доступных словарей |

---

## 5. Архитектура краулера

### 5.1 Асинхронный краулер (`app/crawler/crawler.py`)

- **HTTP-клиент:** `httpx.AsyncClient` с настраиваемым таймаутом
- **Парсинг HTML:** BeautifulSoup4 + lxml
- **Извлечение ссылок:** `<a href>`, `<link href>`, `<form action>`
- **Извлечение форм:** все элементы `<form>` с метаданными полей ввода
- **Извлечение JS-маршрутов:** regex-поиск строковых литералов путей в `fetch()`, `axios()`, `href:`
- **Контроль области:** только тот же origin; сравнение по префиксу excluded_paths
- **Контроль глубины:** BFS с настраиваемым max_depth (1–10)
- **Поддержка остановки:** `asyncio.Event` проверяется перед каждым URL

### 5.2 Auth Manager (`app/crawler/auth_manager.py`)

| Стратегия | Механизм |
|---|---|
| `none` | Без аутентификации |
| `cookie` | Предварительно настроенный заголовок `Cookie` |
| `basic` | HTTP Basic Auth через httpx |
| `bearer` | Заголовок `Authorization: Bearer` |
| `form` | POST на login_url, сессионные cookie захватываются автоматически |

### 5.3 Оркестратор (`app/crawler/orchestrator.py`)

Переходы состояний:
```
pending → running → finished
                 → paused   (stop_event выставлен воркером)
                 → failed   (исключение или таймаут)
paused  → pending → running (повторная постановка в очередь через /resume)
```

После обхода `scan.config` обновляется:
```json
{
  "crawl_stats": {
    "visited_count": 42,
    "forms_count": 7,
    "js_routes_count": 12,
    "visited_urls": ["https://..."],
    "forms": [...],
    "js_routes": [...]
  }
}
```

### 5.4 Воркер (`app/worker.py`)

- Опрашивает Redis `scan_queue` (BLPOP с таймаутом 2 с)
- Создаёт `asyncio.Task` для каждого скана → `ScanOrchestrator.run()`
- `check_pause_signals()` запрашивает БД в каждом цикле; вызывает `orch.stop()`, если `status == paused`

---

## 6. Архитектура безопасности

### 6.1 Аутентификация и авторизация

- **JWT:** access-токен (60 мин) + refresh-токен (30 дней), хранятся в `user_sessions`
- **API-ключ:** хешируется SHA-256, передаётся в заголовке `X-API-Key`
- **2FA:** TOTP (RFC 6238), PyOTP, QR через URI `otpauth://`
- **OAuth:** GitHub и Google через Authlib
- **Ролевой доступ:** `user` / `admin`; admin-маршруты защищены зависимостью `require_admin`

### 6.2 HTTP-заголовки безопасности (Nginx)

| Заголовок | Значение |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'unsafe-inline'` |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

### 6.3 Ограничение запросов (SlowAPI)

| Эндпоинт | Лимит |
|---|---|
| `POST /auth/register` | 5 / минута |
| `POST /auth/login` | 10 / минута |
| `POST /auth/2fa/verify` | 10 / минута |
| Все остальные эндпоинты | 60 / минута (по умолчанию) |

### 6.4 Трассировка запросов

Каждому запросу присваивается UUIDv7 в заголовке `X-Request-ID`; логируется время, метод, путь, код ответа и длительность.

---

## 7. CI/CD (GitHub Actions)

Файл: `.github/workflows/ci.yml`

| Этап | Триггер | Джобы |
|---|---|---|
| Линтинг | Push / PR (фильтр путей) | flake8 + mypy (бэкенд), ESLint (фронтенд) |
| SAST | Push в main / PR | SonarQube Scanner |
| Тесты | Push / PR (фильтр путей) | pytest + сервисы postgres и redis |
| Сборка | `git push --tags v*` | Docker build → push на ghcr.io |
| Trivy | После сборки | Сканирование контейнера (HIGH/CRITICAL = провал) |
| Деплой | После Trivy | SSH → docker compose pull + up + alembic upgrade |

Необходимые секреты: `SONAR_TOKEN`, `SONAR_HOST_URL`, `SSH_PRIVATE_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`

---

## 8. Развёртывание

### 8.1 Сервисы Docker Compose

| Сервис | Образ | Порт |
|---|---|---|
| `db` | postgres:16-alpine | внутренний |
| `redis` | redis:7-alpine | внутренний |
| `backend` | custom (./backend) | 8000 (проброшен) |
| `worker` | custom (./backend) | — |
| `nginx` | custom (nginx:1.27-alpine) | 80, 443 |

### 8.2 Переменные окружения

| Переменная | Обязательна | Описание |
|---|---|---|
| `SECRET_KEY` | Да | Ключ подписи JWT (32+ символа) |
| `DATABASE_URL` | Да | `postgresql+asyncpg://user:pass@db:5432/dast` |
| `REDIS_URL` | Да | `redis://:pass@redis:6379/0` |
| `POSTGRES_PASSWORD` | Да | Пароль PostgreSQL |
| `REDIS_PASSWORD` | Да | Пароль Redis |
| `ALLOWED_ORIGINS` | Нет | CORS-источники через запятую |
| `ENVIRONMENT` | Нет | `development` включает Swagger UI |
| `GITHUB_CLIENT_ID/SECRET` | Нет | OAuth GitHub |
| `GOOGLE_CLIENT_ID/SECRET` | Нет | OAuth Google |

### 8.3 Минимальные требования к серверу

| Параметр | Минимум | Рекомендуется |
|---|---|---|
| ОС | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 ГБ | 8 ГБ |
| Диск | 20 ГБ SSD | 50 ГБ SSD |
| Порты | 443 (HTTPS) | 443 + 80 |

---

## 9. Дорожная карта спринтов

| Спринт | Содержание | Статус |
|---|---|---|
| 1 | Инфраструктура, схема БД, скелет FastAPI, Nginx, CI/CD | ✅ Выполнен |
| 2 | Аутентификация (вход/2FA/OAuth), панель администратора, rate limiting, миграции Alembic | ✅ Выполнен |
| 3 | Асинхронный краулер, Auth Manager, Scan API, воркер, UI сканирований | ✅ Выполнен |
| 4 | Движок нагрузок, словари, сигнатурный/эвристический анализаторы, прогресс-бар скана | ⬜ Планируется |
| 5 | PDF/JSON-отчёты, Report API, UI отчётов, документация | ⬜ Планируется |
| 6 | Юнит/интеграционные тесты, тестирование на DVWA, финальный деплой, сравнительный анализ | ⬜ Планируется |
