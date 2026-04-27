# DAST Analyzer

![CI](https://gitlab.com/your-group/dast/badges/main/pipeline.svg)
![Coverage](https://gitlab.com/your-group/dast/badges/main/coverage.svg)
![Version](https://img.shields.io/badge/version-0.1.0-blue)

Dynamic Application Security Testing tool for web applications.  
Detects OWASP Top 10 vulnerabilities via automated crawling and payload injection.

## Features

- Automated web crawler — links, forms, JS routes, API endpoints
- Payload engine — built-in wordlists for SQLi, XSS, SSRF, Open Redirect, Header Injection
- Signature & heuristic analyzers
- Scan management — pause, resume, configurable depth and timeouts
- PDF and JSON reports with OWASP Top 10 classification
- Authentication — login/password, 2FA (TOTP), OAuth via GitHub and Google
- Role-based access — admin / user
- Admin panel — user management, role assignment, session deactivation, API token management
- REST API protected by API keys with rate limiting
- Request tracing via UUIDv7 Request ID

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI + SQLAlchemy 2.0 |
| Database | PostgreSQL 16 |
| Queue | Redis 7 |
| Frontend | React 18 + Vite (TypeScript) |
| Proxy | Nginx + TLS |
| CI/CD | GitLab CI (lint → SAST → test → build → Trivy → deploy) |

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2
- [Node.js 20+](https://nodejs.org/) (LTS) with npm — for building the frontend

---

## Quick Start

### 1. Clone the repository

```bash
git clone <repo-url>
cd dast_project
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in the required values:

```env
POSTGRES_PASSWORD=your_strong_password
REDIS_PASSWORD=your_redis_password
SECRET_KEY=at_least_32_random_characters_here
ALLOWED_ORIGINS=https://your-domain.com
ENVIRONMENT=production
```

OAuth (optional — leave empty to disable):

```env
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

### 3. Build the frontend

The Nginx image copies the compiled frontend at build time, so build it first:

```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Start all services

```bash
docker compose up --build -d
```

This starts: PostgreSQL, Redis, FastAPI backend, background worker, and Nginx.

### 5. Apply database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 6. Verify

```bash
curl -k https://localhost/health
# {"status":"ok","version":"0.1.0"}
```

The application is available at **https://localhost**.  
API docs (development mode only): `https://localhost/api/docs`

---

## Development Setup

### Backend

```bash
cd backend
pip install -r requirements.txt

# Copy and configure .env
cp ../.env.example .env
# Set ENVIRONMENT=development, DATABASE_URL and REDIS_URL pointing to local services

# Run migrations
alembic upgrade head

# Start with auto-reload
uvicorn app.main:app --reload
```

In development mode (`ENVIRONMENT=development`) tables are also created automatically via SQLAlchemy on startup.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite dev server starts at `http://localhost:5173` and proxies `/api` requests to the backend.

### Useful Alembic commands

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "description"

# Roll back last migration
alembic downgrade -1
```

---

## Useful Docker Commands

```bash
# View backend logs
docker compose logs -f backend

# Stop all services
docker compose down

# Stop and remove all data (caution!)
docker compose down -v
```

---

## TLS Certificate

By default Nginx generates a **self-signed certificate** — browsers will show a warning.  
For production, replace it with a real certificate:

1. Place your `server.crt` and `server.key` into `docker/nginx/certs/`
2. Rebuild the Nginx image: `docker compose build nginx && docker compose up -d nginx`

---

## Documentation

- [System Specs](docs/SYSTEM_SPECS.md)
- [User Guide](docs/USER_SPECS.md)
- [Deployment Guide](docs/DEPLOY.md)
- [Security](docs/SECURITY.md)

---

## License

MIT
