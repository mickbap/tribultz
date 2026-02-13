from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth import User
from app.schemas.auth import TokenPayload

# OAuth2PasswordBearer is used for extracting the token from the header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)]
) -> User:
    # Helper to create fresh exception to avoid traceback reuse issues (Ruff complaint)
    def credentials_exception():
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        user_id_claim = payload.get("sub")
        if not isinstance(user_id_claim, str):
            raise credentials_exception()
        
        # Validate structure with Pydantic
        token_data = TokenPayload(**payload)
        
    except JWTError:
        raise credentials_exception()
    except Exception:
        # Pydantic validation error or other issuer
        raise credentials_exception()
        
    # Check simple UUID validity implicitly by querying
    try:
        user_uuid = UUID(token_data.sub)
    except ValueError:
        raise credentials_exception()

    user = db.get(User, user_uuid)
    if user is None:
        raise credentials_exception()
        
    if not cast(bool, user.is_active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return user
