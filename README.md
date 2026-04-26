# DAST Analyzer

![CI](https://gitlab.com/your-group/dast/badges/main/pipeline.svg)
![Coverage](https://gitlab.com/your-group/dast/badges/main/coverage.svg)
![Version](https://img.shields.io/badge/version-0.1.0-blue)

Dynamic Application Security Testing tool for web applications.
Detects OWASP Top 10 vulnerabilities via automated crawling and payload injection.

## Quick Start

```bash
cp .env.example .env
# Edit .env — set strong passwords and SECRET_KEY
docker compose up -d
```

API docs available at `https://localhost/api/docs` (development mode only).

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI + SQLAlchemy |
| Database | PostgreSQL 16 |
| Queue | Redis 7 |
| Frontend | React + Vite (TypeScript) |
| Proxy | Nginx + TLS |
| CI/CD | GitLab CI |

## Documentation

- [System Specs](docs/SYSTEM_SPECS.md)
- [User Guide](docs/USER_SPECS.md)
- [Deployment](docs/DEPLOY.md)
- [Security](docs/SECURITY.md)

## Development

```bash
cd backend
pip install -r requirements.txt
# Run with local .env
uvicorn app.main:app --reload
```

```bash
# Apply DB migrations
alembic upgrade head

# Create new migration after model changes
alembic revision --autogenerate -m "description"
```

## License

MIT
