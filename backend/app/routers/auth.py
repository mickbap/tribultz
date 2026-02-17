from typing import cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.auth import Tenant, User
from app.schemas.auth import Token, UserLogin
from app.core.security import verify_password, create_access_token

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
