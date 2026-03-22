from typing import cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.auth import Tenant, User
from app.schemas.auth import Token, UserLogin, UserRead, UserRegister
from app.core.security import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    # 1. Resolve Tenant
    stmt_tenant = select(Tenant).where(Tenant.slug == login_data.tenant_slug)
    tenant = db.execute(stmt_tenant).scalar_one_or_none()
    
    # Cast is_active to bool for Pyright
    if not tenant or not cast(bool, tenant.is_active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Resolve User within Tenant
    # Use Tenant.id (class attr) for query, which is correct
    stmt_user = select(User).where(
        User.email == login_data.email,
        User.tenant_id == tenant.id
    )
    user = db.execute(stmt_user).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Cast password_hash to str
    if not verify_password(login_data.password, cast(str, user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Cast is_active to bool
    if not cast(bool, user.is_active):
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Create Token
    # Cast IDs and Role
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "tenant_id": str(tenant.id),
            "role": cast(str, user.role)
        }
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: Session = Depends(get_db)):
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

    # 3. Create user
    user = User(
        tenant_id=tenant.id,
        email=data.email,
        full_name=data.full_name,
        password_hash=get_password_hash(data.password),
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserRead(
        id=user.id,
        email=cast(str, user.email),
        full_name=cast(str, user.full_name),
        role=cast(str, user.role),
        tenant_id=user.tenant_id,
        is_active=cast(bool, user.is_active),
    )
