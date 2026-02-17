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
