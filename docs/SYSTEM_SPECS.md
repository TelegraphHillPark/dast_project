# DAST Analyzer — System Specifications

## 1. Overview

DAST Analyzer is an automated Dynamic Application Security Testing tool that crawls web applications, generates attack payloads, and detects vulnerabilities from the OWASP Top 10.

**Version:** 0.2.0  
**Stack:** Python 3.11 · FastAPI · PostgreSQL 16 · Redis 7 · React 18 · Nginx

---

## 2. Architecture

### 2.1 Component Diagram

```
Browser / CLI
    │
    ▼
Nginx (443 TLS / 80 redirect)
    ├── Static files  → React SPA (frontend/dist)
    └── /api/*        → FastAPI Backend (:8000)
                            │
                ┌───────────┼────────────┐
                ▼           ▼            ▼
          PostgreSQL      Redis       Worker process
          (state store)  (task queue) (Orchestrator + Crawler)
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|---|---|
| **Nginx** | TLS termination, static file serving, reverse proxy to backend |
| **FastAPI Backend** | REST API, authentication, user management, scan management |
| **PostgreSQL** | Persistent state: users, sessions, scans, vulnerabilities, wordlists |
| **Redis** | Scan task queue (`scan_queue` list), future pub/sub |
| **Worker** | Dequeues scan tasks, runs Orchestrator, saves results to DB |
| **Orchestrator** | Manages scan lifecycle (pending → running → finished/paused/failed) |
| **Crawler** | Async HTTP traversal of target application |
| **Auth Manager** | Applies target-app auth (cookie, Basic, Bearer, form login) |
| **Payload Engine** | *(Sprint 4)* Generates attack payloads from wordlists |
| **Analyzers** | *(Sprint 4)* Signature + heuristic vulnerability detection |
| **Report Generator** | *(Sprint 5)* PDF and JSON report export |

---

## 3. Database Schema

### 3.1 Entity-Relationship Summary

```
users ──< user_sessions
users ──< api_tokens
users ──< scans ──< vulnerabilities
users ──< wordlists
```

### 3.2 Tables

#### `users`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) PK | UUIDv7 |
| email | VARCHAR(255) UNIQUE | |
| username | VARCHAR(64) UNIQUE | |
| hashed_password | TEXT | bcrypt |
| role | ENUM(admin, user) | |
| avatar_url | TEXT | |
| totp_secret | TEXT | Encrypted TOTP seed |
| is_active | BOOLEAN | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

#### `user_sessions`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) PK | |
| user_id | FK → users.id CASCADE | |
| token_hash | VARCHAR(64) | SHA-256 of refresh token |
| user_agent | TEXT | |
| ip_address | VARCHAR(45) | IPv4/IPv6 |
| is_active | BOOLEAN | |
| created_at / expires_at | TIMESTAMPTZ | |

#### `api_tokens`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) PK | |
| owner_id | FK → users.id CASCADE | |
| name | VARCHAR(128) | Human label |
| token_hash | VARCHAR(64) | SHA-256 |
| is_active | BOOLEAN | |
| last_used_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |

#### `scans`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) PK | UUIDv7 |
| owner_id | FK → users.id CASCADE | |
| target_url | VARCHAR(2048) | |
| status | ENUM(pending, running, paused, finished, failed) | |
| max_depth | INTEGER | Default 3 |
| timeout_seconds | INTEGER | Default 3600 |
| excluded_paths | JSON | Array of path prefixes |
| config | JSON | Auth config + crawl_stats after run |
| created_at / started_at / finished_at | TIMESTAMPTZ | |

#### `vulnerabilities`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) PK | |
| scan_id | FK → scans.id CASCADE | |
| vuln_type | ENUM(sqli, xss, ssrf, open_redirect, header_injection, broken_auth, sensitive_data, security_misconfiguration, other) | |
| severity | ENUM(critical, high, medium, low, info) | |
| url | VARCHAR(2048) | |
| parameter | VARCHAR(255) | |
| method | VARCHAR(10) | GET / POST / etc. |
| payload | TEXT | Attack payload used |
| evidence | JSON | Request/response snippets |
| recommendation | TEXT | |
| created_at | TIMESTAMPTZ | |

#### `wordlists`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) PK | |
| owner_id | FK → users.id CASCADE | |
| name | VARCHAR(128) | |
| file_path | TEXT | Path on filesystem |
| size_bytes | BIGINT | |
| is_builtin | BOOLEAN | |
| created_at | TIMESTAMPTZ | |

---

## 4. REST API Specification

Base URL: `/api`  
Authentication: `Authorization: Bearer <JWT>` or `X-API-Key: <token>`

### 4.1 Authentication (`/api/auth`)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Register new user (5/min rate limit) |
| POST | `/auth/login` | Login; returns pre_auth_token if 2FA enabled (10/min) |
| POST | `/auth/2fa/setup` | Generate TOTP secret + QR code URI |
| POST | `/auth/2fa/enable` | Activate 2FA with TOTP code |
| POST | `/auth/2fa/disable` | Deactivate 2FA |
| POST | `/auth/2fa/verify` | Verify TOTP code (10/min) |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Revoke session |
| GET | `/auth/oauth/github` | Redirect to GitHub OAuth |
| GET | `/auth/oauth/github/callback` | GitHub OAuth callback |
| GET | `/auth/oauth/google` | Redirect to Google OAuth |
| GET | `/auth/oauth/google/callback` | Google OAuth callback |

### 4.2 Users (`/api/users`)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/users/me` | Current user profile |
| PATCH | `/users/me` | Update username/email |
| POST | `/users/me/change-password` | Change password |
| POST | `/users/me/avatar` | Upload avatar (JPEG/PNG/WebP/GIF) |
| GET | `/users/me/sessions` | List active sessions |
| DELETE | `/users/me/sessions/{id}` | Revoke session |
| GET | `/users/me/tokens` | List API tokens |
| POST | `/users/me/tokens` | Create API token |
| DELETE | `/users/me/tokens/{id}` | Revoke API token |

### 4.3 Scans (`/api/scans`)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/scans` | Create and enqueue scan |
| GET | `/scans` | List user's scans |
| GET | `/scans/{id}` | Scan detail with vulnerabilities and crawl stats |
| POST | `/scans/{id}/pause` | Pause running scan |
| POST | `/scans/{id}/resume` | Resume paused scan (re-enqueues) |
| GET | `/scans/{id}/report` | JSON vulnerability report *(Sprint 5)* |
| GET | `/scans/{id}/report.pdf` | PDF vulnerability report *(Sprint 5)* |

**POST `/scans` request body:**
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

### 4.4 Admin (`/api/admin`) — admin role required

| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin/users` | List all users |
| PATCH | `/admin/users/{id}` | Update user role / active status |
| GET | `/admin/sessions/{user_id}` | List user sessions |
| DELETE | `/admin/sessions/{id}` | Deactivate session |
| GET | `/admin/tokens` | List all API tokens |
| DELETE | `/admin/tokens/{id}` | Revoke any API token |

### 4.5 Wordlists (`/api/wordlists`) — *(Sprint 4)*

| Method | Endpoint | Description |
|---|---|---|
| POST | `/wordlists` | Upload wordlist (.txt / .json, up to 1 GB) |
| GET | `/wordlists` | List available wordlists |

---

## 5. Crawler Architecture

### 5.1 Async Crawler (`app/crawler/crawler.py`)

- **HTTP client:** `httpx.AsyncClient` with configurable timeout
- **HTML parsing:** BeautifulSoup4 + lxml
- **Link extraction:** `<a href>`, `<link href>`, `<form action>`
- **Form extraction:** all `<form>` elements with input field metadata
- **JS route extraction:** regex scan for path literals in `fetch()`, `axios()`, `href:`
- **Scope control:** same-origin only; excluded_paths prefix matching
- **Depth control:** BFS with configurable max_depth (1–10)
- **Stop support:** `asyncio.Event` checked before each URL

### 5.2 Auth Manager (`app/crawler/auth_manager.py`)

| Strategy | Mechanism |
|---|---|
| `none` | No authentication |
| `cookie` | Pre-configured `Cookie` header |
| `basic` | HTTP Basic Auth via httpx |
| `bearer` | `Authorization: Bearer` header |
| `form` | POST to login_url, session cookies auto-captured |

### 5.3 Orchestrator (`app/crawler/orchestrator.py`)

State transitions:
```
pending → running → finished
                 → paused   (stop_event set by worker)
                 → failed   (exception or timeout)
paused  → pending → running (re-enqueued via resume endpoint)
```

After crawl, `scan.config` is updated with:
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

### 5.4 Worker (`app/worker.py`)

- Polls Redis `scan_queue` (BLPOP with 2s timeout)
- Spawns `asyncio.Task` per scan → `ScanOrchestrator.run()`
- `check_pause_signals()` queries DB each cycle; calls `orch.stop()` when status = paused

---

## 6. Security Architecture

### 6.1 Authentication & Authorization

- **JWT:** access token (60 min) + refresh token (30 days), stored in `user_sessions`
- **API Key:** SHA-256 hashed, header `X-API-Key`
- **2FA:** TOTP (RFC 6238), PyOTP, QR via `otpauth://` URI
- **OAuth:** GitHub and Google via Authlib
- **Role-based access:** `user` / `admin`; admin routes guarded by `require_admin` dependency

### 6.2 HTTP Security Headers (Nginx)

| Header | Value |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'unsafe-inline'` |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

### 6.3 Rate Limiting (SlowAPI)

| Endpoint | Limit |
|---|---|
| `POST /auth/register` | 5 / minute |
| `POST /auth/login` | 10 / minute |
| `POST /auth/2fa/verify` | 10 / minute |
| All other endpoints | 60 / minute (default) |

### 6.4 Request Tracing

Every request is assigned a UUIDv7 `X-Request-ID` header and logged with timestamp, method, path, status code, and duration.

---

## 7. CI/CD Pipeline (GitHub Actions)

File: `.github/workflows/ci.yml`

| Stage | Trigger | Jobs |
|---|---|---|
| Lint | Push / PR (path filter) | flake8 + mypy (backend), ESLint (frontend) |
| SAST | Push to main / PR | SonarQube Scanner |
| Test | Push / PR (path filter) | pytest + postgres + redis services |
| Build | `git push --tags v*` | Docker build → push to ghcr.io |
| Trivy | After build | Container vulnerability scan (HIGH/CRITICAL fail) |
| Deploy | After trivy | SSH → docker compose pull + up + alembic upgrade |

Secrets required: `SONAR_TOKEN`, `SONAR_HOST_URL`, `SSH_PRIVATE_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`

---

## 8. Deployment

### 8.1 Docker Compose Services

| Service | Image | Port |
|---|---|---|
| `db` | postgres:16-alpine | internal |
| `redis` | redis:7-alpine | internal |
| `backend` | custom (./backend) | 8000 (exposed) |
| `worker` | custom (./backend) | — |
| `nginx` | custom (nginx:1.27-alpine) | 80, 443 |

### 8.2 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | JWT signing key (32+ chars) |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user:pass@db:5432/dast` |
| `REDIS_URL` | Yes | `redis://:pass@redis:6379/0` |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `REDIS_PASSWORD` | Yes | Redis password |
| `ALLOWED_ORIGINS` | No | CORS origins, comma-separated |
| `ENVIRONMENT` | No | `development` enables Swagger UI |
| `GITHUB_CLIENT_ID/SECRET` | No | GitHub OAuth |
| `GOOGLE_CLIENT_ID/SECRET` | No | Google OAuth |

### 8.3 Minimum Server Requirements

| Parameter | Minimum | Recommended |
|---|---|---|
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB SSD | 50 GB SSD |
| Port | 443 (HTTPS) | 443 + 80 |

---

## 9. Sprint Roadmap

| Sprint | Scope | Status |
|---|---|---|
| 1 | Infrastructure, DB schema, FastAPI skeleton, Nginx, CI/CD | ✅ Done |
| 2 | Auth (login/2FA/OAuth), Admin panel, Rate limiting, Alembic migration | ✅ Done |
| 3 | Async Crawler, Auth Manager, Scan API, Worker, Scan UI | ✅ Done |
| 4 | Payload Engine, wordlists, Signature/Heuristic analyzers, Scan progress UI | ⬜ Pending |
| 5 | PDF/JSON reports, Report API, Report UI, Documentation | ⬜ Pending |
| 6 | Unit/integration tests, DVWA testing, final deployment, comparison analysis | ⬜ Pending |
