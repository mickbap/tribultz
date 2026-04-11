"""LGPD data rights — Art. 18-19 compliance.

Endpoints for data subject rights:
- GET  /api/v1/lgpd/my-data    — view all personal data
- GET  /api/v1/lgpd/export     — download all data as JSON (portability)
- POST /api/v1/lgpd/delete-account — soft-delete + PII anonymization
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import cast
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/lgpd", tags=["lgpd"])


def _user_data_dict(user: User) -> dict:
    """Extract user data as a plain dict for export."""
    return {
        "id": str(user.id),
        "email": cast(str, user.email),
        "full_name": cast(str, user.full_name),
        "cnpj": cast(str, user.cnpj) if cast(str, user.cnpj) else None,
        "role": cast(str, user.role),
        "is_active": cast(bool, user.is_active),
        "lgpd_consent_at": str(user.lgpd_consent_at) if cast(str, user.lgpd_consent_at) else None,
        "email_verified": cast(bool, user.email_verified),
        "created_at": str(user.created_at),
        "updated_at": str(user.updated_at),
        "tenant_id": str(user.tenant_id),
    }


@router.get("/my-data")
def get_my_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all personal data for the current user (LGPD Art. 18, I)."""
    user_id = current_user.id
    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": _user_data_dict(user),
        "lgpd_notice": (
            "Seus dados sao tratados conforme a LGPD (Lei 13.709/2018). "
            "Para exercer seus direitos, utilize os endpoints desta API ou "
            "entre em contato com dpo@tribultz.com.br."
        ),
    }


@router.get("/export")
def export_my_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all user data as downloadable JSON (LGPD Art. 18, V — portability)."""
    user_id = current_user.id
    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    export_data = {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "data_controller": "Tribultz Tecnologia Ltda.",
        "contact_dpo": "dpo@tribultz.com.br",
        "user_data": _user_data_dict(user),
    }

    json_bytes = json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8")

    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="tribultz_lgpd_export_{user_id}.json"',
        },
    )


@router.post("/delete-account")
def delete_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete user account with PII anonymization (LGPD Art. 18, VI).

    Tax audit records are retained per Brazilian fiscal law.
    Personal data is replaced with anonymized hashes.
    """
    user_id = current_user.id
    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Account already deactivated")

    # Anonymize PII: replace with hashed values
    email_hash = hashlib.sha256(
        cast(str, user.email).encode()
    ).hexdigest()[:16]
    name_hash = hashlib.sha256(
        cast(str, user.full_name).encode()
    ).hexdigest()[:16]

    now = datetime.now(timezone.utc)

    db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            email=f"deleted_{email_hash}@anonymized.local",
            full_name=f"Deleted User {name_hash}",
            cnpj=None,
            password_hash="DELETED",
            is_active=False,
            deleted_at=now,
        )
    )
    db.commit()

    logger.info(
        "lgpd_account_deleted",
        extra={"user_id": str(user_id), "anonymized_at": now.isoformat()},
    )

    return {
        "status": "deleted",
        "message": (
            "Conta desativada e dados pessoais anonimizados. "
            "Registros fiscais sao retidos conforme obrigacao legal. "
            "Para duvidas, contate dpo@tribultz.com.br."
        ),
    }
