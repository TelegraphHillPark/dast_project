# DAST Analyzer — Системные спецификации

**Версия:** 0.4.0  
**Стек:** Python 3.11 · FastAPI · PostgreSQL 16 · Redis 7 · React 18 · Nginx 1.27

---

## 1. Общее описание

DAST Analyzer — инструмент динамического анализа защищённости веб-приложений. Работает по принципу «чёрного ящика»: не требует доступа к исходному коду, обходит целевой сайт как браузер, затем прогоняет набор атакующих нагрузок по найденным точкам входа и фиксирует подозрительные ответы.

Приложение разворачивается одной командой через Docker Compose и предоставляет веб-интерфейс на React.

---

## 2. Архитектура

> Схема в формате Draw.io: [docs/diagrams/architecture.drawio](diagrams/architecture.drawio)  
> Открыть онлайн: перетащить файл на [app.diagrams.net](https://app.diagrams.net)

Система состоит из пяти Docker-контейнеров, объединённых внутренней сетью `dast_internal`. Наружу торчат только порты 80 и 443 (Nginx).

| Контейнер | Образ | Назначение |
|---|---|---|
| `dast_nginx` | nginx:1.27-alpine | TLS-терминация, раздача статики, проксирование /api/* |
| `dast_backend` | custom (./backend) | REST API на FastAPI, :8000 |
| `dast_worker` | custom (./backend) | Фоновая обработка сканов |
| `dast_db` | postgres:16-alpine | Постоянное хранилище |
| `dast_redis` | redis:7-alpine | Очередь задач `scan_queue`, хранилище логов сканов |

**Принцип работы:**

1. Пользователь создаёт скан через UI → `POST /api/scans` → задача кладётся в Redis-список `scan_queue` (RPUSH).
2. Воркер ждёт задачи через `BLPOP` (таймаут 1 сек). Как только задача появилась — запускает `ScanOrchestrator` в отдельном `asyncio.Task`.
3. Оркестратор проходит две фазы: обход (Crawler) и атака (PayloadEngine + анализаторы). Результаты пишет в PostgreSQL.
4. Логи каждого шага пишутся в Redis-список `scan_logs:{id}`, фронтенд опрашивает их каждые 2 секунды.
5. Для паузы/отмены API меняет статус в БД, воркер обнаруживает это в следующей итерации `check_pause_signals()` (≤1 сек) и устанавливает `stop_event`.

### 2.1 Компоненты краулера и движка атак

| Компонент | Файл | Описание |
|---|---|---|
| `AsyncCrawler` | `crawler/crawler.py` | BFS-обход по httpx + BeautifulSoup4, извлечение форм и JS-маршрутов |
| `AuthManager` | `crawler/auth_manager.py` | Применение аутентификации к HTTP-клиенту (cookie / Basic / Bearer / form) |
| `PayloadEngine` | `crawler/payload_engine.py` | Генерация GET/POST-целей из посещённых URL и форм |
| `SignatureAnalyzer` | `crawler/analyzers.py` | Поиск сигнатур в теле ответа (SQL-ошибки, XSS-отражение и т.д.) |
| `HeuristicAnalyzer` | `crawler/analyzers.py` | Анализ на основе кода ответа, размера тела, времени отклика |
| `ScanOrchestrator` | `crawler/orchestrator.py` | Управление жизненным циклом одного скана |
| `scan_logger` | `crawler/scan_logger.py` | Запись логов в Redis, чтение через GET /scans/{id}/logs |

---

## 3. Схема базы данных

> Схема в формате Draw.io: [docs/diagrams/database_er.drawio](diagrams/database_er.drawio)

### 3.1 Таблицы

#### `users`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | UUIDv7 |
| email | VARCHAR(255) UNIQUE NOT NULL | |
| username | VARCHAR(64) UNIQUE NOT NULL | |
| hashed_password | TEXT | bcrypt, cost 12 |
| role | ENUM(admin, user) | |
| avatar_url | TEXT | путь к файлу в `/app/uploads/avatars/` |
| totp_secret | TEXT | зашифрован симметрично перед записью |
| is_active | BOOLEAN | по умолчанию true |
| created_at / updated_at | TIMESTAMPTZ | |

#### `user_sessions`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | |
| user_id | FK → users.id CASCADE | |
| token_hash | VARCHAR(64) | SHA-256 от refresh-токена |
| user_agent | TEXT | |
| ip_address | VARCHAR(45) | IPv4/IPv6 |
| is_active | BOOLEAN | |
| created_at / expires_at | TIMESTAMPTZ | expires_at = +30 дней |

#### `api_tokens`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | |
| owner_id | FK → users.id CASCADE | |
| name | VARCHAR(128) | пользовательская метка |
| token_hash | VARCHAR(64) | SHA-256, сам токен показывается один раз при создании |
| is_active | BOOLEAN | |
| last_used_at | TIMESTAMPTZ | обновляется при каждом запросе |
| created_at | TIMESTAMPTZ | |

#### `scans`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | UUIDv7 (монотонно возрастающий) |
| owner_id | FK → users.id CASCADE | |
| target_url | VARCHAR(2048) | |
| status | ENUM(pending, running, paused, finished, failed, cancelled) | |
| max_depth | INTEGER | 1–10, по умолчанию 3 |
| timeout_seconds | INTEGER | 60–86400, по умолчанию 3600 |
| excluded_paths | JSON | массив строк-префиксов |
| config | JSON | конфиг аутентификации + `crawl_stats` после обхода |
| created_at / started_at / finished_at | TIMESTAMPTZ | |

#### `vulnerabilities`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | |
| scan_id | FK → scans.id CASCADE | |
| vuln_type | ENUM(sqli, xss, ssrf, open_redirect, header_injection, ...) | |
| severity | ENUM(critical, high, medium, low, info) | задаётся статической картой в `analyzers.py` |
| url | VARCHAR(2048) | |
| parameter | VARCHAR(255) | имя параметра GET/POST |
| method | VARCHAR(10) | GET / POST |
| payload | TEXT | использованная нагрузка |
| evidence | JSON | `{reflected_payload, signature, location, status, confidence}` |
| recommendation | TEXT | |
| created_at | TIMESTAMPTZ | |

#### `wordlists`
| Столбец | Тип | Примечания |
|---|---|---|
| id | VARCHAR(36) PK | |
| owner_id | FK → users.id CASCADE | |
| name | VARCHAR(128) | |
| file_path | TEXT | путь в файловой системе контейнера |
| size_bytes | BIGINT | |
| is_builtin | BOOLEAN | встроенные словари не привязаны к пользователю |
| created_at | TIMESTAMPTZ | |

---

## 4. Жизненный цикл скана

> Схема в формате Draw.io: [docs/diagrams/scan_lifecycle.drawio](diagrams/scan_lifecycle.drawio)

```
pending ──→ running ──→ finished
               │
               ├──→ paused ──→ pending (resume)
               │                    
               ├──→ failed (исключение / timeout)
               └──→ cancelled
```

Переходы `pending → cancelled` и `paused → cancelled` возможны через `POST /api/scans/{id}/cancel`.  
Переход `paused → pending` происходит при `POST /api/scans/{id}/resume` — скан снова ставится в Redis-очередь.

---

## 5. REST API

Базовый URL: `/api`  
Аутентификация: `Authorization: Bearer <JWT>` или `X-API-Key: <токен>`

### 5.1 Аутентификация (`/api/auth`)

| Метод | Эндпоинт | Лимит | Описание |
|---|---|---|---|
| POST | `/auth/register` | 5/мин | Регистрация |
| POST | `/auth/login` | 10/мин | Вход; при включённой 2FA возвращает `pre_auth_token` |
| POST | `/auth/2fa/verify` | 10/мин | Проверка TOTP-кода |
| POST | `/auth/2fa/setup` | — | Генерация секрета (QR URI) |
| POST | `/auth/2fa/enable` | — | Активация 2FA |
| POST | `/auth/2fa/disable` | — | Деактивация 2FA |
| POST | `/auth/refresh` | — | Обновление access-токена |
| POST | `/auth/logout` | — | Отзыв сессии |
| GET | `/auth/oauth/github` | — | Редирект на OAuth GitHub |
| GET | `/auth/oauth/github/callback` | — | Callback OAuth GitHub |

### 5.2 Пользователи (`/api/users`)

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/users/me` | Профиль текущего пользователя |
| PATCH | `/users/me` | Обновление имени / email |
| POST | `/users/me/change-password` | Смена пароля |
| POST | `/users/me/avatar` | Загрузка аватара (JPEG/PNG/WebP/GIF, до 5 МБ) |
| GET | `/users/me/sessions` | Список активных сессий |
| DELETE | `/users/me/sessions/{id}` | Отзыв сессии |
| GET | `/users/me/tokens` | Список API-токенов |
| POST | `/users/me/tokens` | Создание API-токена (10/мин) |
| DELETE | `/users/me/tokens/{id}` | Отзыв API-токена |

### 5.3 Сканирования (`/api/scans`)

| Метод | Эндпоинт | Лимит | Описание |
|---|---|---|---|
| POST | `/scans` | 10/мин | Создание скана и постановка в очередь |
| GET | `/scans` | — | Список сканов пользователя |
| GET | `/scans/{id}` | — | Детали: уязвимости, статистика краулера |
| POST | `/scans/{id}/pause` | — | Пауза работающего скана |
| POST | `/scans/{id}/resume` | — | Возобновление |
| POST | `/scans/{id}/cancel` | — | Остановка (необратимо) |
| GET | `/scans/{id}/logs` | — | Лог-строки из Redis; поддерживает `?offset=N` |
| GET | `/scans/{id}/report` | — | JSON-отчёт об уязвимостях |

Тело запроса `POST /scans`:
```json
{
  "target_url": "https://example.com",
  "max_depth": 3,
  "timeout_seconds": 3600,
  "excluded_paths": ["/logout", "/admin"],
  "auth_config": {
    "type": "none|cookie|basic|bearer|form",
    "cookie": "session=abc123",
    "username": "admin",
    "password": "secret",
    "bearer_token": "eyJ...",
    "login_url": "https://example.com/login",
    "username_field": "username",
    "password_field": "password"
  }
}
```

### 5.4 Администрирование (`/api/admin`) — требуется роль admin

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/admin/users` | Список всех пользователей |
| PATCH | `/admin/users/{id}` | Изменение роли / статуса |
| GET | `/admin/sessions/{user_id}` | Сессии пользователя |
| DELETE | `/admin/sessions/{id}` | Деактивация сессии |
| GET | `/admin/tokens` | Все API-токены в системе |
| DELETE | `/admin/tokens/{id}` | Отзыв любого токена |

### 5.5 Словари (`/api/wordlists`)

| Метод | Эндпоинт | Описание |
|---|---|---|
| POST | `/wordlists` | Загрузка .txt/.json (до 1 ГБ) |
| GET | `/wordlists` | Список доступных словарей |

---

## 6. Безопасность

### 6.1 Аутентификация

- **JWT:** access-токен живёт 60 минут, подписывается `HS256`. Refresh-токен — 30 дней, хранится в `user_sessions` как SHA-256-хеш. При обновлении токена старый refresh немедленно инвалидируется (rotation).
- **API-ключи:** передаются в заголовке `X-API-Key`, хранятся только как SHA-256-хеш. Сам ключ показывается пользователю один раз при создании.
- **2FA:** TOTP по RFC 6238 (PyOTP), окно ±30 сек, QR через URI `otpauth://`.
- **OAuth:** GitHub через Authlib. Google OAuth не используется.
- **Пароли:** bcrypt, cost factor определяется библиотекой.

### 6.2 HTTP-заголовки (Nginx)

| Заголовок | Значение |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'unsafe-inline'` |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

### 6.3 Rate limiting (SlowAPI)

| Эндпоинт | Лимит |
|---|---|
| `POST /auth/register` | 5 / минута |
| `POST /auth/login` | 10 / минута |
| `POST /auth/2fa/verify` | 10 / минута |
| `POST /scans` | 10 / минута |

Остальные эндпоинты — без глобального лимита (опрос статуса и логов не должен блокировать управляющие запросы).

### 6.4 Трассировка запросов

Каждый запрос получает `X-Request-ID` на основе UUIDv7. Middleware логирует метод, путь, статус, время выполнения.

---

## 7. CI/CD

Файл: `.github/workflows/ci.yml`

| Этап | Триггер | Описание |
|---|---|---|
| Линтинг | push / PR | flake8 + mypy (backend), ESLint (frontend) |
| Тесты | push / PR | pytest, поднимает postgres и redis как services |
| Сборка | push `v*` тег | docker build → push на ghcr.io |
| Trivy | после сборки | сканирование образа, HIGH/CRITICAL = провал |
| Деплой | после Trivy | SSH → docker compose pull && up && alembic upgrade |

Секреты GitHub Actions: `SSH_PRIVATE_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`.

---

## 8. Требования к окружению

### 8.1 Сервисы Docker Compose

| Сервис | Образ | Открытые порты |
|---|---|---|
| `db` | postgres:16-alpine | только внутренняя сеть |
| `redis` | redis:7-alpine | только внутренняя сеть |
| `backend` | custom | 8000 (внутренний), 8000 (проброшен для отладки) |
| `worker` | custom | — |
| `nginx` | custom (nginx:1.27-alpine) | 80, 443 |

### 8.2 Переменные окружения

| Переменная | Обязательна | Описание |
|---|---|---|
| `SECRET_KEY` | Да | Ключ подписи JWT, минимум 32 символа |
| `DATABASE_URL` | Да | `postgresql+asyncpg://user:pass@db:5432/dast` |
| `REDIS_URL` | Да | `redis://:pass@redis:6379/0` |
| `POSTGRES_PASSWORD` | Да | |
| `REDIS_PASSWORD` | Да | |
| `ALLOWED_ORIGINS` | Нет | CORS (по умолчанию localhost) |
| `ENVIRONMENT` | Нет | `development` включает Swagger и auto-create таблиц |
| `GITHUB_CLIENT_ID/SECRET` | Нет | OAuth GitHub |

### 8.3 Требования к серверу

| Параметр | Минимум | Рекомендуется |
|---|---|---|
| ОС | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 ГБ | 8 ГБ |
| Диск | 20 ГБ SSD | 50 ГБ SSD |
| Docker | 24.x + Compose v2 | последняя стабильная |
