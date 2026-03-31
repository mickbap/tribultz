"""Tribultz – FastAPI application entry-point."""

import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.core.logging import configure_logging
from app.routers import auth, audit, billing, calculadora, chat, feedback, health, jobs, lgpd, news, public, reports, tasks, validate, validate_xml, validation
from app.services.news_seed import ensure_default_news_entry

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    ensure_default_news_entry()
    yield


app = FastAPI(
    title="Tribultz API",
    version="0.2.0",
    description="Plataforma de conformidade tributária – Reforma Tributária BR",
    lifespan=lifespan,
)


# ── Security Headers Middleware ─────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)

# ── CORS ────────────────────────────────────────────────────
origin_patterns = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
origins = [origin for origin in origin_patterns if "*" not in origin]
origin_regexes = [
    f"^{re.escape(origin).replace(r'\*', '[^.]+')}$"
    for origin in origin_patterns
    if "*" in origin
]
origin_regex = "|".join(origin_regexes) or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
)

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(validate.router)
app.include_router(validation.router)
app.include_router(audit.router)
app.include_router(jobs.router)
app.include_router(tasks.router)
app.include_router(chat.router)
app.include_router(feedback.router)
app.include_router(lgpd.router)
app.include_router(billing.router)
app.include_router(validate_xml.router)
app.include_router(public.router)
app.include_router(calculadora.router)
app.include_router(reports.router)
app.include_router(news.router)


@app.get("/", tags=["root"])
def root():
    return {"status": "TRIBULTZ API Running", "version": "0.2.0"}
