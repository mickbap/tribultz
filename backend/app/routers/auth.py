import logging
from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data.trial_policy import TRIAL_DURATION_DAYS
from app.database import get_db
from app.models.auth import Tenant, User, UserTenant
from app.models.founding_partner import resolve_effective_license
from app.models.partner import Partner, normalize_partner_code
from app.models.billing import Plan, Subscription, UsageTracking
from app.schemas.auth import Token, TenantInfo, UserLogin, UserRead, UserRegister
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_email_verification_token,
    verify_email_verification_token,
    create_password_reset_token,
    verify_password_reset_token,
)
from app.api.deps import get_current_user
from app.services.captcha_service import verify_captcha
from app.services.cnpj_validator import is_valid_cnpj_format, normalize_cnpj, validate_cnpj
from app.services.email_service import send_verification_email, send_password_reset_email
from app.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Rate limiters: login 5/60s, register 3/60s per IP
_login_limiter = RateLimiter()
_login_limiter.limit = 5

_register_limiter = RateLimiter()
_register_limiter.limit = 3


def _client_ip(request: Request) -> str:
    # Cloudflare sets CF-Connecting-IP with the real client IP (most reliable)
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    # Fallback: rightmost X-Forwarded-For (last untrusted hop)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",")]
        return parts[-1] if parts else "unknown"
    if request.client:
        return request.client.host
    return "unknown"


def _cnpj_to_slug(cnpj: str) -> str:
    """Convert CNPJ to a tenant slug: 12345678000199 → cnpj-12345678000199.

    Preserva letras (CNPJ alfanumérico, RFB — produção 27/07/2026): descartar
    non-digits colidiria dois CNPJs alfanuméricos diferentes que compartilhem
    os mesmos dígitos.
    """
    return f"cnpj-{normalize_cnpj(cnpj)}"


def _get_or_create_tenant_for_cnpj(
    db: Session, cnpj: str, company_name: str = ""
) -> Tenant:
    """Find existing tenant by CNPJ slug or create a new one."""
    slug = _cnpj_to_slug(cnpj)
    tenant = db.execute(
        select(Tenant).where(Tenant.slug == slug)
    ).scalar_one_or_none()

    if tenant:
        return tenant

    name = company_name or f"Empresa {cnpj}"
    tenant = Tenant(name=name, slug=slug)
    db.add(tenant)
    db.flush()  # get the ID without committing
    return tenant


def _attach_partner_from_code(db: Session, tenant: Tenant, raw_code: str) -> None:
    """Captura a proveniência comercial (RFC-0025) sem nunca bloquear o cadastro.

    Vincula ``tenant.partner_id`` ao Partner ativo cujo código bate com o link
    ``?partner=/?ref=``. Regras (RFC-0025):
    - Código inválido ou inativo → apenas loga; a empresa entra sem vínculo.
    - A origem é permanente: se o tenant já tem Partner, não sobrescreve.
    """
    code = normalize_partner_code(raw_code)
    if not code:
        if raw_code:
            logger.info("partner attribution ignorada: código inválido %r", raw_code)
        return
    if tenant.partner_id is not None:
        return  # origem já registrada — permanente, não sobrescreve
    partner = db.execute(
        select(Partner).where(Partner.code == code)
    ).scalar_one_or_none()
    if partner is None or cast(str, partner.status) != "active":
        logger.info("partner attribution ignorada: código %s inexistente/inativo", code)
        return
    tenant.partner_id = partner.id  # type: ignore[assignment]
    logger.info("partner attribution: tenant %s → partner %s", tenant.slug, code)


def _attach_prospect_diagnostic(db: Session, tenant: Tenant, raw_diag_id: str) -> None:
    """Captura a atribuição de diagnóstico gratuito (Escopo A, plano de
    aquisição comercial) sem nunca bloquear o cadastro.

    Vincula ``tenant.prospect_diagnostic_id`` ao ProspectDiagnostic cujo id
    bate com o link ``?diag=`` no PDF. Id inválido/inexistente → apenas loga.
    A origem é permanente, mesmo padrão do Partner (RFC-0025).
    """
    if not raw_diag_id:
        return
    if tenant.prospect_diagnostic_id is not None:
        return  # origem já registrada — permanente, não sobrescreve
    try:
        diag_id = UUID(raw_diag_id)
    except ValueError:
        logger.info("prospect diagnostic attribution ignorada: id inválido %r", raw_diag_id)
        return
    from app.models.prospect_diagnostic import ProspectDiagnostic
    diagnostic = db.get(ProspectDiagnostic, diag_id)
    if diagnostic is None:
        logger.info("prospect diagnostic attribution ignorada: id %s inexistente", diag_id)
        return
    tenant.prospect_diagnostic_id = diagnostic.id  # type: ignore[assignment]
    logger.info("prospect diagnostic attribution: tenant %s → diagnostic %s", tenant.slug, diag_id)


def _get_user_tenants(db: Session, user_id: UUID) -> list[TenantInfo]:
    """Get all tenants a user has access to."""
    rows = db.execute(
        select(Tenant, UserTenant.is_default, UserTenant.role)
        .join(UserTenant, UserTenant.tenant_id == Tenant.id)
        .where(UserTenant.user_id == user_id)
        .order_by(UserTenant.is_default.desc(), Tenant.name)
    ).all()

    return [
        TenantInfo(
            id=cast(UUID, t.id),
            name=cast(str, t.name),
            slug=cast(str, t.slug),
            is_default=is_def,
        )
        for t, is_def, _role in rows
    ]


# ── Login ────────────────────────────────────────────────────

@router.post("/login", response_model=Token)
async def login(login_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    _login_limiter.check_or_raise(f"login:{ip}")

    if not await verify_captcha(login_data.captcha_token, ip):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA verification failed",
        )

    # Find user by email (across all tenants — email is the primary identity)
    user = db.execute(
        select(User).where(User.email == login_data.email)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(login_data.password, cast(str, user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not cast(bool, user.is_active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inativo",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not cast(bool, user.email_verified):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email não verificado. Verifique sua caixa de entrada.",
        )

    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Conta desativada",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Marca 1º/último login (RFC-0024): alimenta a jornada do cockpit Early
    # Adopters sem tabela adicional — evento genérico de User, não exclusivo de EA.
    _now = datetime.now(timezone.utc)
    if user.first_login_at is None:
        user.first_login_at = _now  # type: ignore[assignment]
    user.last_login_at = _now  # type: ignore[assignment]
    db.commit()

    # Ator partner (Programa de Parceiros, RFC-0026): não tem tenant, billing
    # nem Grant/licença — sai cedo, antes de qualquer resolução tenant-scoped
    # (o restante deste handler assume tenant_id válido).
    if user.actor_type == "partner":
        access_token = create_access_token(
            subject=str(user.id),
            extra_claims={
                "actor_type": "partner",
                "partner_id": str(user.partner_id),
                "role": cast(str, user.role),
            },
        )
        logger.info("login_success", extra={"user_id": str(user.id), "ip": ip, "actor_type": "partner"})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "partner_id": str(user.partner_id),
            "role": cast(str, user.role),
        }

    # Resolve default tenant from user_tenants
    user_tenant_list = _get_user_tenants(db, cast(UUID, user.id))
    default_tenant_id = str(user.tenant_id)
    if user_tenant_list:
        default_entry = next((t for t in user_tenant_list if t.is_default), user_tenant_list[0])
        default_tenant_id = str(default_entry.id)

    # Resolve plan_slug from active subscription
    plan_slug = "trial"
    sub_row = db.execute(
        select(Subscription, Plan)
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(
            Subscription.user_id == user.id,
            Subscription.status.in_(("active", "trial", "pending")),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    ).first()
    if sub_row:
        _, plan_obj = sub_row
        plan_slug = cast(str, plan_obj.slug)

    # Grant Adapter (ADR-0008): Grant ativo tem precedência sobre a assinatura.
    # Ponto único de resolução de licença — 2 fontes, ASAAS intacto.
    plan_slug, license_source = resolve_effective_license(db, UUID(default_tenant_id), plan_slug)

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "actor_type": "tenant",
            "tenant_id": default_tenant_id,
            "role": cast(str, user.role),
            "account_type": cast(str, user.account_type),
            "plan_slug": plan_slug,
        },
    )

    logger.info(
        "login_success",
        extra={"user_id": str(user.id), "ip": ip, "license_source": license_source},
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "tenant_id": default_tenant_id,
        "account_type": cast(str, user.account_type),
        "plan_slug": plan_slug,
        "role": cast(str, user.role),
        "tenants": [t.model_dump() for t in user_tenant_list],
    }


# ── Register ─────────────────────────────────────────────────

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    _register_limiter.check_or_raise(f"register:{ip}")

    if not await verify_captcha(data.captcha_token, ip):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CAPTCHA verification failed",
        )

    # CNPJ validation via BrasilAPI
    company_name = ""
    if data.cnpj:
        cnpj_result = await validate_cnpj(data.cnpj)
        if not cnpj_result.valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=cnpj_result.error,
            )
        company_name = cnpj_result.company_name

    # Check duplicate email globally
    existing = db.execute(
        select(User).where(User.email == data.email)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email já cadastrado.",
        )

    # Auto-create tenant from CNPJ
    if data.cnpj:
        tenant = _get_or_create_tenant_for_cnpj(db, data.cnpj, company_name)
        # ── Contenção de isolamento (Round 10, SEC-INV-1/2) ──────────────────
        # Saber um CNPJ público NÃO concede ingresso automático num tenant que já
        # possui usuários. Reprodução dinâmica (tests/security/test_tenant_
        # isolation_r10.py) provou que, sem esta trava, register com CNPJ
        # preexistente nascia dentro do tenant da vítima com role=admin (leitura,
        # escrita e operação privilegiada cross-tenant). Shell vazio (pré-
        # provisionado por diagnóstico/founding partner) permanece reivindicável
        # pelo 1º usuário; o ingresso de um 2º usuário exige fluxo autorizado
        # explícito (a projetar — não é este ato). Fail-closed.
        existing_users = (
            db.execute(
                select(func.count(User.id)).where(User.tenant_id == tenant.id)
            ).scalar()
            or 0
        )
        if existing_users > 0:
            logger.warning(
                "register_blocked_existing_tenant",
                extra={"cnpj": data.cnpj, "tenant_slug": cast(str, tenant.slug)},
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Este CNPJ já possui uma conta ativa. O ingresso de um novo "
                    "usuário requer autorização do titular — em breve por convite. "
                    "Se você é o responsável, use 'Esqueci minha senha' ou fale com o suporte."
                ),
            )
        # Proveniência comercial (RFC-0025): captura não-bloqueante do Partner.
        _attach_partner_from_code(db, tenant, data.partner_code)
        # Atribuição de diagnóstico gratuito (Escopo A): captura não-bloqueante.
        _attach_prospect_diagnostic(db, tenant, data.diag_id)
    else:
        # Fallback to default tenant
        tenant = db.execute(
            select(Tenant).where(Tenant.slug == "default")
        ).scalar_one_or_none()
        if not tenant:
            tenant = Tenant(name="Default", slug="default")
            db.add(tenant)
            db.flush()

    # Resolve plan
    plan = db.execute(
        select(Plan).where(Plan.slug == data.plan_slug, Plan.is_active == True)  # noqa: E712
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plano '{data.plan_slug}' não encontrado.",
        )

    # Create user
    consent_at = datetime.now(timezone.utc)
    user = User(
        tenant_id=tenant.id,
        email=data.email,
        full_name=data.full_name,
        password_hash=get_password_hash(data.password),
        cnpj=data.cnpj or None,
        phone=data.phone or None,
        account_type=data.account_type,
        role="admin" if data.account_type == "empresa" else "contador",
        lgpd_consent_at=consent_at,
        terms_accepted_at=consent_at,
        refund_policy_accepted_at=consent_at,
        consent_ip=ip,
        email_verified=False,
    )
    db.add(user)
    db.flush()

    # Create user_tenants association
    user_tenant = UserTenant(
        user_id=user.id,
        tenant_id=tenant.id,
        role=user.role,
        is_default=True,
    )
    db.add(user_tenant)

    # Create subscription
    now = datetime.now(timezone.utc)
    is_trial = data.plan_slug == "trial"

    subscription = Subscription(
        tenant_id=tenant.id,
        user_id=user.id,
        plan_id=plan.id,
        status="trial" if is_trial else "pending",
        # #635: prazo vem da política canônica, não de literal. Antes, mudar a
        # duração do Trial exigia lembrar deste ponto além da copy e do plano.
        trial_ends_at=now + timedelta(days=TRIAL_DURATION_DAYS) if is_trial else None,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db.add(subscription)

    # Create usage tracking for current month
    usage = UsageTracking(
        tenant_id=tenant.id,
        user_id=user.id,
        period=now.strftime("%Y-%m"),
    )
    db.add(usage)

    db.commit()
    db.refresh(user)
    db.refresh(subscription)

    # Billing: create Asaas customer + payment for paid plans
    checkout_url = None
    pix_qr_code = None
    pix_copy_paste = None

    if not is_trial:
        try:
            from app.services.asaas_service import asaas

            # Create Asaas customer
            customer = await asaas.create_customer(
                name=data.full_name,
                email=data.email,
                cpf_cnpj=data.cnpj or "",
                phone=data.phone or "",
            )
            asaas_customer_id = customer["id"]
            subscription.asaas_customer_id = asaas_customer_id  # type: ignore[assignment]

            # Create recurring Asaas subscription (monthly)
            price_reais = cast(int, plan.price_cents) / 100
            sub_resp = await asaas.create_subscription(
                customer_id=asaas_customer_id,
                value=price_reais,
                billing_type=data.billing_type,
                description=f"Assinatura Tribultz — {cast(str, plan.name)}",
            )
            asaas_subscription_id = sub_resp["id"]
            subscription.asaas_subscription_id = asaas_subscription_id  # type: ignore[assignment]

            # Asaas creates the first payment automatically — retrieve it
            sub_payments = await asaas.get_subscription_payments(asaas_subscription_id)
            if not sub_payments:
                raise ValueError("Asaas subscription created but no payment found")
            first_payment = sub_payments[0]
            asaas_payment_id = first_payment["id"]

            # Store payment record
            from app.models.billing import Payment

            db_payment = Payment(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                asaas_payment_id=asaas_payment_id,
                amount_cents=cast(int, plan.price_cents),
                status="pending",
                payment_method=data.billing_type.lower(),
            )

            # PIX: get QR code
            if data.billing_type == "PIX":
                pix_data = await asaas.get_pix_qr_code(asaas_payment_id)
                pix_qr_code = pix_data.get("encodedImage")
                pix_copy_paste = pix_data.get("payload")
                db_payment.pix_qr_code = pix_qr_code  # type: ignore[assignment]
                db_payment.pix_copy_paste = pix_copy_paste  # type: ignore[assignment]
            else:
                # Credit card: get checkout URL
                checkout_url = asaas.get_checkout_url(asaas_payment_id)

            db.add(db_payment)
            db.commit()

        except Exception as e:
            logger.error("asaas_registration_error", extra={"error": str(e), "user_id": str(user.id)})
            # Don't fail registration — user can pay later via billing page
            checkout_url = None

    # Send email verification for all new accounts (trial and paid)
    verification_token = create_email_verification_token(str(user.id))
    user.email_verification_token = verification_token  # type: ignore[assignment]
    db.commit()

    send_verification_email(
        to_email=data.email,
        user_name=data.full_name,
        token=verification_token,
    )

    # CRM: sync new contact/deal
    from app.tasks.task_crm import crm_sync
    _crm_event = "register" if is_trial else "subscription_pending"
    crm_sync.delay(user_id=str(user.id), event_type=_crm_event)

    logger.info(
        "user_registered",
        extra={
            "user_id": str(user.id),
            "tenant_slug": cast(str, tenant.slug),
            "account_type": data.account_type,
            "plan": data.plan_slug,
            "ip": ip,
        },
    )

    tenants = _get_user_tenants(db, cast(UUID, user.id))

    return UserRead(
        id=cast(UUID, user.id),
        email=cast(str, user.email),
        full_name=cast(str, user.full_name),
        role=cast(str, user.role),
        tenant_id=cast(UUID, user.tenant_id),
        is_active=cast(bool, user.is_active),
        cnpj=cast(str, user.cnpj) if cast(str, user.cnpj) else None,
        account_type=cast(str, user.account_type),
        lgpd_consent_at=user.lgpd_consent_at,  # type: ignore[arg-type]
        tenants=tenants,
        plan_slug=data.plan_slug,
        subscription_status=cast(str, subscription.status),
        checkout_url=checkout_url,
        pix_qr_code=pix_qr_code,
        pix_copy_paste=pix_copy_paste,
    )


# ── Verify Email ─────────────────────────────────────────────

@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify user email via JWT token link (24h expiry)."""
    user_id = verify_email_verification_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido ou expirado.",
        )

    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    if cast(bool, user.email_verified):
        return {"status": "already_verified", "message": "Email já verificado."}

    user.email_verified = True  # type: ignore[assignment]
    user.email_verification_token = None  # type: ignore[assignment]
    db.commit()

    logger.info("email_verified", extra={"user_id": str(user.id)})
    return {"status": "verified", "message": "Email verificado com sucesso!"}


# ── Resend Verification ──────────────────────────────────────

@router.post("/resend-verification")
async def resend_verification(
    data: UserLogin, request: Request, db: Session = Depends(get_db)
):
    """Resend verification email for unverified users."""
    ip = _client_ip(request)
    _register_limiter.check_or_raise(f"resend:{ip}")

    user = db.execute(
        select(User).where(User.email == data.email)
    ).scalar_one_or_none()

    if not user:
        return {"message": "Se o email estiver cadastrado, um novo link será enviado."}

    if cast(bool, user.email_verified):
        return {"message": "Email já verificado. Faça login normalmente."}

    new_token = create_email_verification_token(str(user.id))
    user.email_verification_token = new_token  # type: ignore[assignment]
    db.commit()

    send_verification_email(
        to_email=cast(str, user.email),
        user_name=cast(str, user.full_name),
        token=new_token,
    )

    return {"message": "Se o email estiver cadastrado, um novo link será enviado."}


# ── Add CNPJ (for contadores) ────────────────────────────────

class AddCnpjRequest(BaseModel):
    cnpj: str


@router.post("/add-cnpj")
async def add_cnpj(
    data: AddCnpjRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Add a new CNPJ/tenant for contador accounts."""
    from app.api.deps import get_current_actor, oauth2_scheme

    token = await oauth2_scheme(request)
    if not token:
        raise HTTPException(status_code=401, detail="Token ausente.")
    user = await get_current_actor(token, db)
    user_id = cast(UUID, user.id)

    if cast(str, user.account_type) != "contador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas contas de contador podem adicionar CNPJs.",
        )

    # Limite numérico de CNPJs por plano (Escopo 3.5 do go-live de billing,
    # 28/07/2026) — Trial/Starter/Profissional=1, Empresarial=10, Contador=50.
    from app.api.plan_gate import get_effective_plan
    plan = get_effective_plan(db, user)
    max_cnpj = int(plan.max_cnpj) if plan is not None else 1
    current_cnpj_count = db.execute(
        select(func.count(UserTenant.id)).where(UserTenant.user_id == user_id)
    ).scalar() or 0
    if current_cnpj_count >= max_cnpj:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Limite de {max_cnpj} CNPJ(s) do seu plano atingido. "
                "Faça upgrade para adicionar mais empresas."
            ),
            headers={"X-Upgrade-Required": "true"},
        )

    cnpj_normalized = normalize_cnpj(data.cnpj)
    if not is_valid_cnpj_format(cnpj_normalized):
        raise HTTPException(
            status_code=400,
            detail="CNPJ deve ter 14 caracteres (12 alfanuméricos + 2 dígitos verificadores).",
        )

    # Validate CNPJ
    cnpj_result = await validate_cnpj(cnpj_normalized)
    if not cnpj_result.valid:
        raise HTTPException(status_code=400, detail="CNPJ inválido ou não encontrado na Receita Federal.")
    company_name = cnpj_result.company_name

    # Get or create tenant
    tenant = _get_or_create_tenant_for_cnpj(db, cnpj_normalized, company_name)

    # Check if association already exists
    existing = db.execute(
        select(UserTenant).where(
            UserTenant.user_id == user_id,
            UserTenant.tenant_id == tenant.id,
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CNPJ já associado à sua conta.",
        )

    user_tenant = UserTenant(
        user_id=user_id,
        tenant_id=tenant.id,
        role="contador",
        is_default=False,
    )
    db.add(user_tenant)
    db.commit()

    logger.info(
        "cnpj_added",
        extra={"user_id": str(user_id), "cnpj": cnpj_normalized, "tenant_slug": cast(str, tenant.slug)},
    )

    tenants = _get_user_tenants(db, user_id)
    return {"tenants": [t.model_dump() for t in tenants]}


# ── Switch Tenant ─────────────────────────────────────────────

class SwitchTenantRequest(BaseModel):
    tenant_id: UUID


@router.post("/switch-tenant", response_model=Token)
async def switch_tenant(
    data: SwitchTenantRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Switch active tenant — returns new JWT with updated tenant_id."""
    from app.api.deps import get_current_actor, oauth2_scheme

    token = await oauth2_scheme(request)
    if not token:
        raise HTTPException(status_code=401, detail="Token ausente.")
    user = await get_current_actor(token, db)
    user_id = cast(UUID, user.id)

    # Verify user has access to this tenant
    user_tenant = db.execute(
        select(UserTenant).where(
            UserTenant.user_id == user_id,
            UserTenant.tenant_id == data.tenant_id,
        )
    ).scalar_one_or_none()

    if not user_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem acesso a este tenant.",
        )

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "actor_type": "tenant",
            "tenant_id": str(data.tenant_id),
            "role": cast(str, user_tenant.role),
            "account_type": cast(str, user.account_type),
        },
    )

    tenant = db.execute(
        select(Tenant).where(Tenant.id == data.tenant_id)
    ).scalar_one_or_none()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "tenant_id": str(data.tenant_id),
        "tenant_name": cast(str, tenant.name) if tenant else "",
        "role": cast(str, user_tenant.role),
        "account_type": cast(str, user.account_type),
    }


# ── Select Mode (superadmin only) ────────────────────────────

VALID_TEST_MODES = ("trial", "starter", "profissional", "empresarial", "contador", "admin")


class SelectModeRequest(BaseModel):
    plan_slug: str


@router.post("/select-mode")
async def select_mode(
    data: SelectModeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Superadmin-only: override plan_slug in JWT for functional testing.

    Returns a new JWT with the chosen plan_slug so that superadmins can
    experience the platform as any plan tier (trial, starter, etc.) or
    enter the admin dashboard (plan_slug="admin").
    """
    from app.api.deps import get_current_actor, oauth2_scheme

    token = await oauth2_scheme(request)
    if not token:
        raise HTTPException(status_code=401, detail="Token ausente.")
    user = await get_current_actor(token, db)

    # Only superadmins may switch test mode
    if cast(str, user.role) != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a superadmins.",
        )

    if data.plan_slug not in VALID_TEST_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Modo inválido. Opções: {', '.join(VALID_TEST_MODES)}",
        )

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "actor_type": "tenant",
            "tenant_id": str(user.tenant_id),
            "role": cast(str, user.role),
            "account_type": cast(str, user.account_type),
            "plan_slug": data.plan_slug,
            "test_mode": True,
        },
    )

    logger.info(
        "select_mode",
        extra={"user_id": str(user.id), "plan_slug": data.plan_slug},
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "plan_slug": data.plan_slug,
        "test_mode": True,
    }


# ── Forgot Password ──────────────────────────────────────────

_forgot_limiter = RateLimiter()
_forgot_limiter.limit = 3


class ForgotPasswordRequest(BaseModel):
    email: str


@router.post("/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Send password reset email. Always returns 200 to prevent email enumeration."""
    ip = _client_ip(request)
    _forgot_limiter.check_or_raise(f"forgot:{ip}")

    user = db.execute(
        select(User).where(User.email == data.email)
    ).scalar_one_or_none()

    if user and cast(bool, user.is_active) and user.deleted_at is None:
        token = create_password_reset_token(str(user.id))
        send_password_reset_email(
            to_email=cast(str, user.email),
            user_name=cast(str, user.full_name),
            token=token,
        )
        logger.info("password_reset_requested", extra={"email": data.email})
    else:
        logger.info("password_reset_ignored", extra={"email": data.email})

    return {"message": "Se o email estiver cadastrado, você receberá um link para redefinir sua senha."}


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Troca a senha do próprio usuário autenticado.

    Existia um buraco no fluxo de onboarding: contas provisionadas pelo Command
    Center (Founding Partners) nascem com senha DEFINIDA POR TERCEIRO — o Owner —
    e não havia como o titular trocá-la de dentro da plataforma. A única saída era
    sair, pedir "Esqueci minha senha" e recuperar por e-mail. Para uma consultoria
    recebendo acesso, isso é a primeira coisa que se tenta fazer.

    Exige a senha atual: sem isso, um token vazado permitiria trocar a senha e
    tomar a conta em definitivo.
    """
    ip = _client_ip(request)
    _login_limiter.check_or_raise(f"changepw:{ip}")

    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ter no mínimo 8 caracteres.",
        )

    if not verify_password(data.current_password, cast(str, current_user.password_hash)):
        logger.warning("change_password_wrong_current", extra={"user_id": str(current_user.id)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta.",
        )

    if verify_password(data.new_password, cast(str, current_user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ser diferente da atual.",
        )

    current_user.password_hash = get_password_hash(data.new_password)  # type: ignore[assignment]
    db.commit()

    logger.info("password_changed", extra={"user_id": str(current_user.id)})
    return {"status": "ok", "message": "Senha alterada."}


@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Reset password using a valid reset token."""
    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha deve ter no mínimo 8 caracteres.",
        )

    user_id = verify_password_reset_token(data.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link expirado ou inválido. Solicite um novo link.",
        )

    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()

    if not user or not cast(bool, user.is_active):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conta não encontrada ou inativa.",
        )

    user.password_hash = get_password_hash(data.new_password)  # type: ignore[assignment]
    db.commit()

    logger.info("password_reset_completed", extra={"user_id": user_id})
    return {"message": "Senha redefinida com sucesso. Faça login com sua nova senha."}


@router.get("/health")
def auth_health(db: Session = Depends(get_db)):
    """Auth subsystem health check — validates DB connectivity."""
    try:
        db.execute(select(User).limit(1))
        return {"status": "ok", "subsystem": "auth", "db": "connected"}
    except Exception as exc:
        logger.error("auth_health_db_error: %s", exc)
        raise HTTPException(status_code=503, detail="Auth DB unavailable")


# ── Tenant settings ──────────────────────────────────────────────────────────

class TenantSettingsResponse(BaseModel):
    pedagogical_mode_2026: bool


class TenantSettingsUpdate(BaseModel):
    pedagogical_mode_2026: bool


@router.get("/settings/tenant", response_model=TenantSettingsResponse)
def get_tenant_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TenantSettingsResponse:
    """Get tenant settings (pedagogical mode, etc.)."""
    tenant = db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id)).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    return TenantSettingsResponse(pedagogical_mode_2026=bool(tenant.pedagogical_mode_2026))


@router.patch("/settings/tenant", response_model=TenantSettingsResponse)
def patch_tenant_settings(
    data: TenantSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TenantSettingsResponse:
    """Update tenant settings."""
    tenant = db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id)).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    tenant.pedagogical_mode_2026 = data.pedagogical_mode_2026  # type: ignore[assignment]
    db.commit()
    logger.info(
        "tenant_settings_updated tenant=%s pedagogical_mode_2026=%s",
        current_user.tenant_id, data.pedagogical_mode_2026,
    )
    return TenantSettingsResponse(pedagogical_mode_2026=bool(tenant.pedagogical_mode_2026))
