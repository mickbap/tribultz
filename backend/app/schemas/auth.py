import re
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_validator

from app.services.cnpj_validator import is_valid_cnpj_format, normalize_cnpj


class TenantInfo(BaseModel):
    id: UUID
    name: str
    slug: str
    is_default: bool = False


class Token(BaseModel):
    """response_model de /login e /switch-tenant.

    Precisa declarar TODO campo que os handlers colocam no dict de retorno —
    response_model descarta silenciosamente qualquer chave extra não listada
    aqui (FastAPI serializa através do schema). Os opcionais cobrem os 3
    formatos de resposta: login tenant, login partner e switch-tenant.
    """

    access_token: str
    token_type: str
    role: Optional[str] = None
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
    partner_id: Optional[str] = None
    account_type: Optional[str] = None
    plan_slug: Optional[str] = None
    tenants: Optional[list[TenantInfo]] = None


class TokenPayload(BaseModel):
    sub: str  # user_id (UUID string) — âncora de identidade, qualquer ator
    actor_type: str  # "tenant" | "partner" — domínio do ator (RFC-0026)
    role: str
    # Contextuais: exatamente um preenchido, conforme actor_type.
    tenant_id: Optional[str] = None
    partner_id: Optional[str] = None
    exp: int
    iat: int


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    tenant_slug: str = "default"
    captcha_token: str = ""


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    cnpj: str = ""
    phone: str = ""
    account_type: str = "empresa"  # empresa | contador
    plan_slug: str = "trial"  # trial | starter | profissional | contador
    billing_type: str = "PIX"  # PIX | CREDIT_CARD (boleto not supported)
    lgpd_consent: bool = False
    terms_accepted: bool = False
    refund_policy_accepted: bool = False
    tenant_slug: str = "default"
    captcha_token: str = ""
    # Proveniência comercial (RFC-0025): código do Partner que indicou a empresa,
    # capturado do link ?partner=/?ref=. Inválido/inativo NÃO bloqueia o cadastro.
    partner_code: str = ""
    # Atribuição de diagnóstico gratuito (Escopo A, plano de aquisição comercial):
    # id do ProspectDiagnostic capturado do link ?diag= no PDF. Inválido NÃO
    # bloqueia o cadastro. Independente de partner_code (não é o mesmo conceito).
    diag_id: str = ""

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not v:
            return v
        digits = re.sub(r"\D", "", v)
        if len(digits) < 10 or len(digits) > 11:
            raise ValueError("Telefone deve ter 10 ou 11 dígitos.")
        return digits

    @field_validator("plan_slug")
    @classmethod
    def validate_plan_slug(cls, v: str) -> str:
        allowed = ("trial", "starter", "profissional", "contador")
        if v not in allowed:
            raise ValueError(f"Plano deve ser um de: {', '.join(allowed)}.")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 200:
            raise ValueError("Nome deve ter entre 2 e 200 caracteres.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Senha deve ter no mínimo 8 caracteres.")
        return v

    @field_validator("cnpj")
    @classmethod
    def validate_cnpj(cls, v: str) -> str:
        if not v:
            return v
        normalized = normalize_cnpj(v)
        if not is_valid_cnpj_format(normalized):
            raise ValueError("CNPJ deve ter 14 caracteres (12 alfanuméricos + 2 dígitos verificadores).")
        return normalized

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v: str) -> str:
        if v not in ("empresa", "contador"):
            raise ValueError("Tipo de conta deve ser 'empresa' ou 'contador'.")
        return v

    @field_validator("lgpd_consent")
    @classmethod
    def validate_lgpd_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "Consentimento LGPD obrigatório para cadastro."
            )
        return v

    @field_validator("terms_accepted")
    @classmethod
    def validate_terms_accepted(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "Aceite dos Termos de Uso obrigatório para cadastro."
            )
        return v

    @field_validator("refund_policy_accepted")
    @classmethod
    def validate_refund_policy_accepted(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "Aceite da Política de Reembolso obrigatório para cadastro."
            )
        return v


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: str
    tenant_id: UUID
    is_active: bool
    cnpj: Optional[str] = None
    account_type: str = "empresa"
    lgpd_consent_at: Optional[datetime] = None
    tenants: list[TenantInfo] = []
    plan_slug: Optional[str] = None
    subscription_status: Optional[str] = None
    checkout_url: Optional[str] = None
    pix_qr_code: Optional[str] = None
    pix_copy_paste: Optional[str] = None

    class Config:
        from_attributes = True
