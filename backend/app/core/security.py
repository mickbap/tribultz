from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_email_verification_token(user_id: str) -> str:
    """Create a JWT token for email verification (24h expiry)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=24)
    to_encode = {
        "exp": expire,
        "iat": now,
        "sub": user_id,
        "purpose": "email_verification",
    }
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def verify_email_verification_token(token: str) -> Optional[str]:
    """Verify email verification token. Returns user_id or None."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        if payload.get("purpose") != "email_verification":
            return None
        return payload.get("sub")
    except Exception:
        return None


def create_password_reset_token(user_id: str) -> str:
    """Create a JWT token for password reset (1h expiry)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=1)
    to_encode = {
        "exp": expire,
        "iat": now,
        "sub": user_id,
        "purpose": "password_reset",
    }
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def verify_password_reset_token(token: str) -> Optional[str]:
    """Verify password reset token. Returns user_id or None."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        if payload.get("purpose") != "password_reset":
            return None
        return payload.get("sub")
    except Exception:
        return None


def create_access_token(subject: Union[str, Any], extra_claims: Optional[dict[str, Any]] = None) -> str:
    if extra_claims is None:
        extra_claims = {}
        
    expires_delta = timedelta(minutes=settings.JWT_EXPIRES_MIN)
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    
    to_encode = {
        "exp": expire,
        "iat": now,
        "sub": str(subject),
    }
    to_encode.update(extra_claims)
    
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALG)
    return encoded_jwt
