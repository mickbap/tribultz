"""Tribultz – FastAPI application entry-point."""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.routers import auth, audit, chat, feedback, health, jobs, tasks, validate, validation


app = FastAPI(
    title="Tribultz API",
    version="0.2.0",
    description="Plataforma de conformidade tributária – Reforma Tributária BR",
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
origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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


@app.get("/", tags=["root"])
def root():
    return {"status": "TRIBULTZ API Running", "version": "0.2.0"}
