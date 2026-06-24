"""cClassTrib Engine — classificação tributária LC 214.

GET  /api/v1/public/classtrib/{codigo}      — lookup por código (público)
GET  /api/v1/public/classtrib/search        — busca por descrição (público)
POST /api/v1/classtrib/validate             — valida NCM × cClassTrib (autenticado)
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.data.ncm_cclasstrib_table import ncm_candidatos
from app.database import get_db
from app.models.auth import User

router = APIRouter(tags=["classtrib"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ClassTribItem(BaseModel):
    codigo: str
    descricao: str
    p_cbs: float
    p_ibs: float
    regime_especial: Optional[str]
    vigencia_ini: Optional[date]
    vigencia_fim: Optional[date]
    is_active: bool
    last_synced_at: Optional[str] = None


class ValidateClassTribRequest(BaseModel):
    ncm: str
    classtrib_informado: str
    vl_item: Optional[float] = None


class ValidateClassTribResponse(BaseModel):
    ncm: str
    classtrib_informado: str
    classtrib_sugerido: Optional[str]
    status: str          # OK | DIVERGENTE | NAO_ENCONTRADO
    divergencia: bool
    p_cbs_correto: Optional[float]
    p_ibs_correto: Optional[float]
    finding: Optional[dict]


# ── Endpoints públicos ─────────────────────────────────────────────────────────

@router.get(
    "/api/v1/public/classtrib/search",
    response_model=list[ClassTribItem],
    summary="Busca cClassTrib por descrição (público)",
)
def search_classtrib(
    q: str = Query(..., min_length=2, description="Texto para busca na descrição"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Any:
    rows = db.execute(
        text("""
            SELECT * FROM cclass_trib_items
            WHERE is_active = TRUE
              AND (
                descricao ILIKE :q
                OR to_tsvector('portuguese', descricao) @@ plainto_tsquery('portuguese', :q2)
              )
            ORDER BY descricao
            LIMIT :lim
        """),
        {"q": f"%{q}%", "q2": q, "lim": limit},
    ).mappings().all()
    return [dict(r) for r in rows]


@router.get(
    "/api/v1/public/classtrib/{codigo}",
    response_model=ClassTribItem,
    summary="Lookup cClassTrib por código (público)",
)
def get_classtrib(codigo: str, db: Session = Depends(get_db)) -> Any:
    row = db.execute(
        text("""
            SELECT *, synced_at::text AS last_synced_at
            FROM cclass_trib_items
            WHERE codigo = :c AND is_active = TRUE
        """),
        {"c": codigo},
    ).mappings().fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"cClassTrib '{codigo}' não encontrado.")
    return dict(row)


# ── Endpoint autenticado ──────────────────────────────────────────────────────

@router.post(
    "/api/v1/classtrib/validate",
    response_model=ValidateClassTribResponse,
    summary="Validar NCM × cClassTrib — gera Finding se divergente",
)
def validate_classtrib(
    payload: ValidateClassTribRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    # Buscar o cClassTrib informado
    item = db.execute(
        text("SELECT * FROM cclass_trib_items WHERE codigo = :c AND is_active = TRUE"),
        {"c": payload.classtrib_informado},
    ).mappings().fetchone()

    if item is None:
        return ValidateClassTribResponse(
            ncm=payload.ncm,
            classtrib_informado=payload.classtrib_informado,
            classtrib_sugerido=None,
            status="NAO_ENCONTRADO",
            divergencia=False,
            p_cbs_correto=None,
            p_ibs_correto=None,
            finding=None,
        )

    item = dict(item)

    # Sugestão pelo mapeamento oficial NCM→cClassTrib (anexos SVRS) — NÃO mais por prefixo
    # de capítulo na taxonomia de produto (#313 Part 2). A mesma NCM pode admitir vários
    # cClassTrib: divergência só quando o informado NÃO consta entre os candidatos.
    candidatos = [c["codigo"] for c in ncm_candidatos(payload.ncm)]
    sugestao = candidatos[0] if candidatos else None

    divergente = bool(candidatos) and payload.classtrib_informado not in candidatos

    finding = None
    if divergente:
        opcoes = ", ".join(candidatos)
        finding = {
            "id":             f"classtrib-{payload.ncm}-{payload.classtrib_informado}",
            "severity":       "ERROR",
            "rule_id":        "CBS-011",
            "title":          "cClassTrib divergente do NCM informado",
            "where":          {"field": "cClassTrib", "snippet": payload.classtrib_informado},
            "recommendation": f"cClassTrib '{payload.classtrib_informado}' não consta entre os candidatos da NCM {payload.ncm} ({opcoes}), conforme os Anexos da LC 214. Validar a classificação.",
            "evidence_ids":   [],
        }

    return ValidateClassTribResponse(
        ncm=payload.ncm,
        classtrib_informado=payload.classtrib_informado,
        classtrib_sugerido=sugestao,
        status="DIVERGENTE" if divergente else "OK",
        divergencia=divergente,
        p_cbs_correto=float(item["p_cbs"]),
        p_ibs_correto=float(item["p_ibs"]),
        finding=finding,
    )
