"""Tribultz – FastAPI application entry-point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, audit, chat, health, jobs, tasks, validate, validation

app = FastAPI(
    title="Tribultz API",
    version="0.1.0",
    description="Plataforma de conformidade tributária – Reforma Tributária BR",
)

# ── CORS (allow front-end dev server) ─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/", tags=["root"])
def root():
    return {"status": "TRIBULTZ API Running"}
