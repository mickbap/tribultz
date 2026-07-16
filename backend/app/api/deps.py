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


async def get_current_actor(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)]
) -> User:
    """Resolve o ator autenticado (qualquer domínio — tenant ou partner).

    Nível mais baixo da autenticação (RFC-0026): decodifica o JWT, valida o
    payload genérico e busca o ``User`` por ``sub``. Não assume nenhum
    domínio — quem precisa de um ator de um domínio específico usa
    ``get_current_user`` (tenant) ou ``get_current_partner`` (partner).
    """
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

    # Block soft-deleted users (LGPD deletion sets deleted_at)
    if user.deleted_at is not None:
        raise credentials_exception()

    if not cast(bool, user.is_active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user(
    actor: Annotated[User, Depends(get_current_actor)],
) -> User:
    """Ator do domínio Tenant — dependência usada por todos os routers
    tenant-scoped existentes. Assinatura e retorno inalterados (RFC-0026):
    só ganha a checagem de domínio abaixo.
    """
    if actor.actor_type != "tenant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recurso disponível apenas para usuários de uma Empresa (Tenant)",
        )
    return actor


async def get_current_partner(
    actor: Annotated[User, Depends(get_current_actor)],
) -> User:
    """Ator do domínio Partner (Programa de Parceiros, RFC-0026) — usada
    exclusivamente pelas rotas da área do parceiro.
    """
    if actor.actor_type != "partner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recurso disponível apenas para parceiros",
        )
    return actor
