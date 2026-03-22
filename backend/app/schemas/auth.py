import re
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_validator


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: str  # user_id (UUID string)
    tenant_id: str
    role: str
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
    account_type: str = "empresa"  # empresa | contador
    lgpd_consent: bool = False
    tenant_slug: str = "default"
    captcha_token: str = ""

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
            raise ValueError("Senha deve ter no minimo 8 caracteres.")
        return v

    @field_validator("cnpj")
    @classmethod
    def validate_cnpj(cls, v: str) -> str:
        if not v:
            return v
        digits = re.sub(r"\D", "", v)
        if len(digits) != 14:
            raise ValueError("CNPJ deve ter 14 digitos.")
        return digits

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
                "Consentimento LGPD obrigatorio para cadastro."
            )
        return v


class TenantInfo(BaseModel):
    id: UUID
    name: str
    slug: str
    is_default: bool = False


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

    class Config:
        from_attributes = True
