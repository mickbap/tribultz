"""API Pública pay-per-call — classificação NCM + cálculo CBS/IBS (#175).

Autenticação via header X-API-Key (não Bearer JWT).
1 crédito por chamada a POST /classify.
Gestão de keys em GET/POST/DELETE /api-keys (Bearer JWT).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional, cast

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.data.ncm_codes import is_valid_ncm
from app.data.ncm_cclasstrib_table import resolve_cclasstrib
from app.data.uf_rates import VALID_UF_CODES
from app.api.plan_gate import _get_effective_plan
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.auth import User
from app.services.tax_rate_resolver import calculate_full

router = APIRouter(tags=["public-api"])

_KEY_PREFIX = "tribultz_sk_"
_FREE_CREDITS = 100


# ── Schemas ───────────────────────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    ncm: str
    uf_destino: str
    base_value: str
    cst: str = "000"

    @field_validator("ncm")
    @classmethod
    def validate_ncm(cls, v: str) -> str:
        v = v.strip().replace(".", "").replace("-", "")
        if not is_valid_ncm(v):
            raise ValueError(f"NCM inválido: {v}")
        return v

    @field_validator("uf_destino")
    @classmethod
    def validate_uf(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in VALID_UF_CODES:
            raise ValueError(f"UF inválida: {v}")
        return v

    @field_validator("base_value")
    @classmethod
    def validate_base_value(cls, v: str) -> str:
        try:
            val = Decimal(v.replace(",", "."))
            if val <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            raise ValueError("base_value deve ser um número positivo (ex: '150.00')")
        return v

    @field_validator("cst")
    @classmethod
    def validate_cst(cls, v: str) -> str:
        v = v.strip().zfill(3)
        if len(v) != 3 or not v.isdigit():
            raise ValueError("cst deve ter 3 dígitos (ex: '000')")
        return v


class ClassifyResponse(BaseModel):
    ncm: str
    # cClassTrib: NUNCA taxonomia de produto (RF-A1). SEMPRE null (#672 Fase 2) — não
    # por falta de mapeamento (ele existe, #313), mas porque os anexos delimitam
    # candidatos condicionados e a determinação depende do contexto da operação, que
    # este endpoint não recebe. A classificação entregue está em cclasstrib_candidatos.
    cClassTrib: None = None
    cclasstrib_candidatos: list = []
    # "requer_validacao" | "candidato_unico" | "multiplos" — cardinalidade, não veredito.
    cclasstrib_status: str = "requer_validacao"
    cest: None = None
    cst: str
    vBC: str
    vCBS: str
    vIBS: str
    total_tributos: str
    aliquota_efetiva_pct: str
    xml_snippet: str
    credits_used: int
    credits_remaining: int


class ApiKeyOut(BaseModel):
    id: str
    name: str
    key_prefix: str
    credits_balance: int
    is_active: bool
    last_used_at: Optional[str]
    created_at: str


class ApiKeyCreateRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 80:
            raise ValueError("name é obrigatório e deve ter até 80 caracteres")
        return v


class ApiKeyCreateResponse(BaseModel):
    id: str
    name: str
    key: str
    key_prefix: str
    credits_balance: int
    message: str


# ── Auth por X-API-Key ────────────────────────────────────────────────────────

def _resolve_api_key(x_api_key: str = Header(..., alias="X-API-Key"), db: Session = Depends(get_db)) -> ApiKey:
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    api_key: ApiKey | None = db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    ).scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-API-Key inválida ou revogada.")
    if cast(int, api_key.credits_balance) <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Créditos esgotados. Adquira mais em tribultz.com.br/settings/api.",
            headers={"X-Credits-Remaining": "0"},
        )
    return api_key


# ── Endpoints públicos (X-API-Key) ────────────────────────────────────────────

@router.post(
    "/api/v1/public-api/classify",
    response_model=ClassifyResponse,
    summary="Classificar NCM → cClassTrib + CBS/IBS (pay-per-call)",
)
def classify(
    payload: ClassifyRequest,
    api_key: ApiKey = Depends(_resolve_api_key),
    db: Session = Depends(get_db),
) -> ClassifyResponse:
    # 1. cClassTrib via mapeamento oficial NCM→cClassTrib (anexos SVRS). NUNCA taxonomia
    #    de produto (RF-A1); candidatos a validar, não veredito (RF-A2); null honesto sem
    #    mapeamento (RF-A3).
    #
    #    `cClassTrib` é null em TODA cardinalidade (#672 Fase 2). Antes vinha preenchido
    #    quando a NCM tinha um candidato só — o que lia "candidato único" como
    #    "determinado". Os anexos catalogam tratamentos condicionados por destinação e
    #    finalidade; a NCM delimita o espaço, o contexto da operação é que escolhe dentro
    #    dele, e este endpoint não recebe esse contexto. Os candidatos seguem na lista.
    classtrib_codigo, cc_candidatos, cc_status = resolve_cclasstrib(payload.ncm)

    # 2. Calcular CBS/IBS
    result = calculate_full(
        vBC=Decimal(payload.base_value.replace(",", ".")),
        ncm=payload.ncm,
        uf=payload.uf_destino,
        cst=payload.cst,
    )

    # 3. Debitar 1 crédito SOMENTE quando há classificação entregue (>= 1 candidato).
    #    Sem mapeamento (requer_validacao) → NÃO cobra: o cliente não paga por
    #    classificação que não acendeu. last_used_at é registrado.
    charge = bool(cc_candidatos)
    new_balance = cast(int, api_key.credits_balance) - (1 if charge else 0)
    db.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key.id)
        .values(
            credits_balance=new_balance,
            last_used_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    return ClassifyResponse(
        ncm=payload.ncm,
        cClassTrib=classtrib_codigo,
        cclasstrib_candidatos=cc_candidatos,
        cclasstrib_status=cc_status,
        cst=result.cst,
        vBC=str(result.vBC),
        vCBS=str(result.vCBS),
        vIBS=str(result.vIBS),
        total_tributos=str(result.total_tributos),
        aliquota_efetiva_pct=str((result.aliquota_efetiva * 100).quantize(Decimal("0.01"))),
        xml_snippet=result.xml_snippet,
        credits_used=1 if charge else 0,
        credits_remaining=new_balance,
    )


# ── Gestão de API Keys (Bearer JWT) ──────────────────────────────────────────

@router.get(
    "/api/v1/api-keys",
    response_model=list[ApiKeyOut],
    summary="Listar API Keys do usuário autenticado",
)
def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApiKeyOut]:
    rows = db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc())
    ).scalars().all()
    out: list[ApiKeyOut] = []
    for k in rows:
        lua = cast(Optional[datetime], k.last_used_at)
        out.append(ApiKeyOut(
            id=str(k.id),
            name=str(k.name),
            key_prefix=str(k.key_prefix),
            credits_balance=cast(int, k.credits_balance),
            is_active=cast(bool, k.is_active),
            last_used_at=lua.isoformat() if lua is not None else None,
            created_at=cast(datetime, k.created_at).isoformat(),
        ))
    return out


@router.post(
    "/api/v1/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar nova API Key (requer plano com acesso à API)",
)
def create_api_key(
    payload: ApiKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyCreateResponse:
    # #635, item 4 da régua: "API indisponível no Trial". O plano `trial` já
    # trazia has_api_access=FALSE desde o seed original, mas ESTE endpoint nunca
    # consultou a flag — bastava estar autenticado para emitir chave e receber
    # 100 créditos. A decisão de Produto de 16/08 é explícita (`trial.api =
    # false`); o gate faltava.
    _plan = _get_effective_plan(db, current_user)
    if _plan is None or not bool(_plan.has_api_access):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso à API não está disponível no seu plano. Faça upgrade para continuar.",
            headers={"X-Upgrade-Required": "true"},
        )

    existing = db.execute(
        select(ApiKey).where(ApiKey.user_id == current_user.id, ApiKey.is_active.is_(True))
    ).scalars().all()
    if len(existing) >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limite de 5 API Keys ativas atingido. Revogue uma antes de criar outra.",
        )

    raw_key = _KEY_PREFIX + secrets.token_hex(24)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:20] + "..."

    api_key = ApiKey(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        name=payload.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        credits_balance=_FREE_CREDITS,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return ApiKeyCreateResponse(
        id=str(api_key.id),
        name=str(api_key.name),
        key=raw_key,
        key_prefix=key_prefix,
        credits_balance=_FREE_CREDITS,
        message="Guarde esta chave agora — ela não será exibida novamente.",
    )


@router.delete(
    "/api/v1/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revogar API Key",
)
def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    api_key: ApiKey | None = db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
    ).scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key não encontrada.")
    db.execute(update(ApiKey).where(ApiKey.id == api_key.id).values(is_active=False))
    db.commit()
