import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.core.limiter import limiter
from app.database import engine, Base
from app.middleware.logging import RequestLoggingMiddleware
from app.routers import auth, scans, admin, wordlists, users
import app.models  # noqa: F401 — registers all ORM mappers before create_all / first query

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)-8s %(name)s %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "dast": {"level": "DEBUG" if settings.DEBUG else "INFO", "propagate": True},
        "uvicorn.access": {"level": "WARNING", "propagate": True},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("dast.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s [%s]", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    # Создаём таблицы только в dev (в prod используем Alembic)
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Middleware (порядок важен: внешний → внутренний) ─────────────────────────

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key"],
    expose_headers=["X-Request-ID"],
)

# ── Security headers через Nginx; здесь только TrustedHost ──────────────────
if settings.ENVIRONMENT == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# ── Роутеры ──────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(scans.router)
app.include_router(admin.router)
app.include_router(wordlists.router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


# Раздача загруженных файлов (аватары и т.д.)
import os as _os
_uploads_dir = "/app/uploads"
_os.makedirs(_uploads_dir, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=_uploads_dir), name="uploads")
