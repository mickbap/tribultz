#!/usr/bin/env python3
"""
Promove um usuário já existente para role="superadmin" — não cria conta nova.

Contexto: provision_admins.py só provisiona contas que ainda não existem.
Quando a conta já foi criada via /register (fluxo normal de cadastro de
empresa), role fica em "admin"/"contador" e nunca vira superadmin sozinha.
Este script cobre esse caso: promove o User.role e todos os UserTenant.role
do usuário para "superadmin", mantendo e-mail e tenant atuais.

Usage (na VM, dentro do container da API):
    docker compose -f infra/docker-compose.prod.yml exec api \
        python backend/scripts/promote_superadmin.py --email mickel@tribultz.com.br

    # Pré-visualizar sem gravar:
    docker compose -f infra/docker-compose.prod.yml exec api \
        python backend/scripts/promote_superadmin.py --email mickel@tribultz.com.br --dry-run
"""

import argparse
import os
import sys
from typing import cast

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.auth import User, UserTenant


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="E-mail da conta já existente a promover")
    parser.add_argument("--dry-run", action="store_true", help="Mostra o que mudaria, sem gravar")
    args = parser.parse_args()

    engine = create_engine(settings.DATABASE_URL)

    with Session(engine) as db:
        user = db.execute(select(User).where(User.email == args.email)).scalar_one_or_none()
        if not user:
            print(f"ERRO: nenhum usuário com e-mail '{args.email}'. Este script não cria contas — use provision_admins.py para isso.")
            sys.exit(1)

        print(f"Usuário encontrado: {user.email} (id={user.id})")
        print(f"  role atual:         {user.role}")

        user_tenants = db.execute(select(UserTenant).where(UserTenant.user_id == user.id)).scalars().all()
        for ut in user_tenants:
            print(f"  user_tenant {ut.tenant_id}: role atual = {ut.role}")

        if cast(str, user.role) == "superadmin" and all(cast(str, ut.role) == "superadmin" for ut in user_tenants):
            print("Já é superadmin em todos os vínculos. Nada a fazer.")
            return

        if args.dry_run:
            print("\n[dry-run] Nenhuma alteração gravada. Rode sem --dry-run para aplicar.")
            return

        user.role = "superadmin"  # type: ignore[assignment]
        for ut in user_tenants:
            ut.role = "superadmin"  # type: ignore[assignment]
        db.commit()

        print(f"\nOK: {user.email} agora é role='superadmin' (User + {len(user_tenants)} vínculo(s) de tenant).")
        print("Efeito colateral esperado: o link 'Admin' só aparece após um novo login (o JWT antigo continua com o role antigo até expirar).")


if __name__ == "__main__":
    main()
