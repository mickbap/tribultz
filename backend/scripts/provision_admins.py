#!/usr/bin/env python3
"""
Provision admin accounts directly in the database — bypasses CAPTCHA,
email verification and billing. Run once on the prod VM after migration.

Usage (from repo root on the VM, with .env.prod sourced):
    python backend/scripts/provision_admins.py

Or inside the Docker api container:
    docker compose -f infra/docker-compose.prod.yml exec api \
        python backend/scripts/provision_admins.py
"""

import os
import sys
import getpass
import argparse
from datetime import datetime, timezone, timedelta

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import get_password_hash
from app.models.auth import Tenant, User, UserTenant
from app.models.billing import Plan, Subscription, UsageTracking

ADMINS = [
    {
        "email": "mickel@tribultz.com.br",
        "full_name": "Mickel",
        "account_type": "empresa",
        "role": "superadmin",
    },
    {
        "email": "roberta@tribultz.com.br",
        "full_name": "Roberta",
        "account_type": "empresa",
        "role": "superadmin",
    },
]

ADMIN_TENANT_SLUG = "tribultz-internal"
PLAN_SLUG = "contador"  # Full access plan


def get_or_create_admin_tenant(db: Session) -> Tenant:
    tenant = db.execute(
        select(Tenant).where(Tenant.slug == ADMIN_TENANT_SLUG)
    ).scalar_one_or_none()
    if not tenant:
        tenant = Tenant(name="Tribultz Internal", slug=ADMIN_TENANT_SLUG)
        db.add(tenant)
        db.flush()
        print(f"  [+] Tenant '{ADMIN_TENANT_SLUG}' criado")
    else:
        print(f"  [=] Tenant '{ADMIN_TENANT_SLUG}' já existe")
    return tenant


def get_plan(db: Session) -> Plan:
    plan = db.execute(
        select(Plan).where(Plan.slug == PLAN_SLUG, Plan.is_active.is_(True))
    ).scalar_one_or_none()
    if not plan:
        raise RuntimeError(
            f"Plano '{PLAN_SLUG}' não encontrado. "
            "Execute as migrations antes de rodar este script."
        )
    return plan


def provision_user(db: Session, admin: dict, password: str, tenant: Tenant, plan: Plan) -> None:
    email = admin["email"]

    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        print(f"  [=] {email} — já existe (id={existing.id}), nada a fazer")
        return

    now = datetime.now(timezone.utc)
    user = User(
        tenant_id=tenant.id,
        email=email,
        full_name=admin["full_name"],
        password_hash=get_password_hash(password),
        account_type=admin["account_type"],
        role=admin["role"],
        is_active=True,
        email_verified=True,
        lgpd_consent_at=now,
    )
    db.add(user)
    db.flush()

    user_tenant = UserTenant(
        user_id=user.id,
        tenant_id=tenant.id,
        role=admin["role"],
        is_default=True,
    )
    db.add(user_tenant)

    subscription = Subscription(
        tenant_id=tenant.id,
        user_id=user.id,
        plan_id=plan.id,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=365 * 10),  # 10 years
    )
    db.add(subscription)

    usage = UsageTracking(
        tenant_id=tenant.id,
        user_id=user.id,
        period=now.strftime("%Y-%m"),
    )
    db.add(usage)

    print(f"  [+] {email} — criado com role='{admin['role']}', plan='{PLAN_SLUG}', email_verified=True")


def main() -> None:
    print("=" * 60)
    print("Tribultz — Admin Provisioning Script")
    print("=" * 60)
    print(f"DB: {settings.DATABASE_URL.split('@')[-1]}")
    print()

    # Accept password from env var (non-interactive) or prompt
    password = os.environ.get("ADMIN_PASSWORD", "")
    if password:
        if len(password) < 8:
            print("ERRO: ADMIN_PASSWORD deve ter no mínimo 8 caracteres.")
            sys.exit(1)
        print("  [i] Senha lida de ADMIN_PASSWORD (modo não-interativo)")
    else:
        password = getpass.getpass("Senha para os 2 admins (min 8 caracteres): ")
        if len(password) < 8:
            print("ERRO: senha deve ter no mínimo 8 caracteres.")
            sys.exit(1)
        confirm = getpass.getpass("Confirmar senha: ")
        if password != confirm:
            print("ERRO: senhas não conferem.")
            sys.exit(1)

    engine = create_engine(settings.DATABASE_URL)

    with Session(engine) as db:
        tenant = get_or_create_admin_tenant(db)
        plan = get_plan(db)

        for admin in ADMINS:
            provision_user(db, admin, password, tenant, plan)

        db.commit()

    print()
    print("Done. Os usuários abaixo estão prontos para login:")
    for admin in ADMINS:
        print(f"  → {admin['email']}")
    print()
    print("IMPORTANTE: guarde a senha em local seguro (não há recuperação automática para admins).")
    print("Use /forgot-password se precisar redefinir via email.")


if __name__ == "__main__":
    main()
