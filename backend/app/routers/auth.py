import logging
from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Tenant, User
from app.schemas.auth import Token, UserLogin, UserRead, UserRegister
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_email_verification_token,
    verify_email_verification_token,
)
from app.services.captcha_service import verify_captcha
from app.services.cnpj_validator import validate_cnpj
from app.services.email_service import send_verification_email
from app.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Rate limiters: login 5/60s, register 3/60s per IP
_login_limiter = RateLimiter()
_login_limiter.limit = 5

_register_limiter = RateLimiter()
_register_limiter.limit = 3


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/login", response_model=Token)
async def login(login_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    _login_limiter.check_or_raise(f"login:{ip}")

    # CAPTCHA check
    if not await verify_captcha(login_data.captcha_token, ip):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA verification failed",
        )

    # 1. Resolve Tenant
    stmt_tenant = select(Tenant).where(Tenant.slug == login_data.tenant_slug)
    tenant = db.execute(stmt_tenant).scalar_one_or_none()

    if not tenant or not cast(bool, tenant.is_active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Resolve User within Tenant
    stmt_user = select(User).where(
        User.email == login_data.email,
        User.tenant_id == tenant.id,
    )
    user = db.execute(stmt_user).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(login_data.password, cast(str, user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not cast(bool, user.is_active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check email verification
    if not cast(bool, user.email_verified):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email nao verificado. Verifique sua caixa de entrada.",
        )

    # 4. Check soft-delete
    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 5. Create Token
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "tenant_id": str(tenant.id),
            "role": cast(str, user.role),
        },
    )

    logger.info("login_success", extra={"user_id": str(user.id), "ip": ip})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    _register_limiter.check_or_raise(f"register:{ip}")

    # CAPTCHA check
    if not await verify_captcha(data.captcha_token, ip):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA verification failed",
        )

    # CNPJ validation via BrasilAPI
    if data.cnpj:
        cnpj_result = await validate_cnpj(data.cnpj)
        if not cnpj_result.valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=cnpj_result.error,
            )

    # 1. Resolve Tenant
    stmt_tenant = select(Tenant).where(Tenant.slug == data.tenant_slug)
    tenant = db.execute(stmt_tenant).scalar_one_or_none()

    if not tenant or not cast(bool, tenant.is_active):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant not found or inactive",
        )

    # 2. Check duplicate email within tenant
    stmt_existing = select(User).where(
        User.email == data.email,
        User.tenant_id == tenant.id,
    )
    if db.execute(stmt_existing).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered for this tenant",
        )

    # 3. Create user with LGPD consent timestamp
    user = User(
        tenant_id=tenant.id,
        email=data.email,
        full_name=data.full_name,
        password_hash=get_password_hash(data.password),
        cnpj=data.cnpj or None,
        role="user",
        lgpd_consent_at=datetime.now(timezone.utc),
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 4. Send verification email
    verification_token = create_email_verification_token(str(user.id))
    user.email_verification_token = verification_token  # type: ignore[assignment]
    db.commit()

    send_verification_email(
        to_email=data.email,
        user_name=data.full_name,
        token=verification_token,
    )

    logger.info(
        "user_registered",
        extra={"user_id": str(user.id), "tenant": data.tenant_slug, "ip": ip},
    )

    return UserRead(
        id=cast(UUID, user.id),
        email=cast(str, user.email),
        full_name=cast(str, user.full_name),
        role=cast(str, user.role),
        tenant_id=cast(UUID, user.tenant_id),
        is_active=cast(bool, user.is_active),
        cnpj=cast(str, user.cnpj) if user.cnpj else None,
        lgpd_consent_at=user.lgpd_consent_at,  # type: ignore[arg-type]
    )


@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify user email via JWT token link (24h expiry)."""
    user_id = verify_email_verification_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token invalido ou expirado.",
        )

    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario nao encontrado.",
        )

    if cast(bool, user.email_verified):
        return {"status": "already_verified", "message": "Email ja verificado."}

    user.email_verified = True  # type: ignore[assignment]
    user.email_verification_token = None  # type: ignore[assignment]
    db.commit()

    logger.info("email_verified", extra={"user_id": str(user.id)})
    return {"status": "verified", "message": "Email verificado com sucesso!"}


@router.post("/resend-verification")
async def resend_verification(
    data: UserLogin, request: Request, db: Session = Depends(get_db)
):
    """Resend verification email for unverified users."""
    ip = _client_ip(request)
    _register_limiter.check_or_raise(f"resend:{ip}")

    # Resolve tenant + user
    tenant = db.execute(
        select(Tenant).where(Tenant.slug == data.tenant_slug)
    ).scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=400, detail="Tenant nao encontrado.")

    user = db.execute(
        select(User).where(User.email == data.email, User.tenant_id == tenant.id)
    ).scalar_one_or_none()

    if not user:
        # Don't reveal whether email exists
        return {"message": "Se o email estiver cadastrado, um novo link sera enviado."}

    if cast(bool, user.email_verified):
        return {"message": "Email ja verificado. Faca login normalmente."}

    # Generate new token and send
    new_token = create_email_verification_token(str(user.id))
    user.email_verification_token = new_token  # type: ignore[assignment]
    db.commit()

    send_verification_email(
        to_email=cast(str, user.email),
        user_name=cast(str, user.full_name),
        token=new_token,
    )

    return {"message": "Se o email estiver cadastrado, um novo link sera enviado."}
