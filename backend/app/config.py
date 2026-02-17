"""Tribultz – application settings (reads from .env / environment)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Postgres ──────────────────────────────────────────────
    POSTGRES_DB: str = "tribultz"
    POSTGRES_USER: str = "tribultz"
    POSTGRES_PASSWORD: str = "tribultz_pw"
    DATABASE_URL: str = "postgresql+psycopg2://tribultz:tribultz_pw@db:5432/tribultz"

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"

    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET: str = "CHANGE_ME_NOW"
    JWT_ALG: str = "HS256"
    JWT_EXPIRES_MIN: int = 480

    # ── MinIO / S3 ────────────────────────────────────────────
    MINIO_ROOT_USER: str = "tribultz_minio"
    MINIO_ROOT_PASSWORD: str = "tribultz_minio_pw"
    S3_ENDPOINT: str = "http://minio:9000"
    S3_BUCKET: str = "tribultz"
    S3_ACCESS_KEY: str = "tribultz_minio"
    S3_SECRET_KEY: str = "tribultz_minio_pw"

    # ── HubSpot ───────────────────────────────────────────────
    HUBSPOT_ENABLED: bool = False
    HUBSPOT_PRIVATE_APP_TOKEN: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
