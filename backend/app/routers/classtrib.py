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

from app.api.deps import get_current_user
from app.data.classtrib_table import classtrib_api_item, classtrib_api_search
from app.data.ncm_cclasstrib_table import ncm_candidatos
from app.models.auth import User

router = APIRouter(tags=["classtrib"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ClassTribItem(BaseModel):
    codigo: str
    descricao: str
    p_cbs: float            # alíquota de referência PLENA (8,8) ajustada pela redução
    p_ibs: float            # alíquota de referência PLENA (17,7) ajustada pela redução
    p_cbs_2026: float       # alíquota da fase de teste 2026 (0,9) ajustada pela redução
    p_ibs_2026: float       # alíquota da fase de teste 2026 (0,1) ajustada pela redução
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
    # Sempre None: a fonte delimita candidatos, não elege um. Ver
    # app/data/ncm_cclasstrib_table. Mantido por compatibilidade de contrato.
    classtrib_sugerido: Optional[str]
    #: Candidatos que os anexos delimitam para a NCM — substitui a "sugestão"
    #: única, que era o primeiro item da lista (posição, não evidência).
    classtrib_candidatos: list[str] = []
    status: str          # OK | NAO_DETERMINAVEL | NAO_ENCONTRADO
    #: Divergência COMPROVADA. A ausência do código informado entre os candidatos
    #: da NCM não a comprova — os anexos catalogam exceções condicionadas e não
    #: esgotam o espaço de tratamentos (000001 não consta de nenhuma NCM).
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
) -> Any:
    # Fonte única: classtrib.json (mesma do motor), via #365 — sem tabela DB.
    return classtrib_api_search(q, limit)


@router.get(
    "/api/v1/public/classtrib/{codigo}",
    response_model=ClassTribItem,
    summary="Lookup cClassTrib por código (público)",
)
def get_classtrib(codigo: str) -> Any:
    item = classtrib_api_item(codigo)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"cClassTrib '{codigo}' não encontrado.")
    return item


# ── Endpoint autenticado ──────────────────────────────────────────────────────

@router.post(
    "/api/v1/classtrib/validate",
    response_model=ValidateClassTribResponse,
    summary="Validar NCM × cClassTrib — devolve os candidatos que os anexos delimitam",
)
def validate_classtrib(
    payload: ValidateClassTribRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    # Buscar o cClassTrib informado na fonte única (classtrib.json) — #365.
    item = classtrib_api_item(payload.classtrib_informado)

    if item is None:
        return ValidateClassTribResponse(
            ncm=payload.ncm,
            classtrib_informado=payload.classtrib_informado,
            classtrib_sugerido=None,
            classtrib_candidatos=[],
            status="NAO_ENCONTRADO",
            divergencia=False,
            p_cbs_correto=None,
            p_ibs_correto=None,
            finding=None,
        )

    # Candidatos pelo mapeamento oficial NCM→cClassTrib (anexos SVRS) — NÃO por
    # prefixo de capítulo na taxonomia de produto (#313 Part 2), e NÃO elegendo um
    # deles (#672 Fase 2).
    #
    # Duas inferências foram removidas aqui, ambas vedadas pela ontologia canônica
    # (Brain, legislation-ontologia-cclasstrib, approved v1):
    #
    #   (a) `sugestao = candidatos[0]` — escolhia pela POSIÇÃO na lista. A fonte não
    #       ordena por probabilidade; o primeiro elemento não é o mais provável.
    #   (b) `divergente = informado not in candidatos` → Finding ERROR. Os anexos
    #       catalogam tratamentos EXCEPCIONAIS e CONDICIONADOS; 000001 (tributação
    #       integral) não é candidato de nenhuma das 1.982 NCMs mapeadas. A regra
    #       antiga, portanto, acusava ERRO em toda operação de tributação comum
    #       sobre NCM anexada — falso positivo por construção.
    #
    # O que resta é verificável: o código existe na tabela oficial (checado acima) e
    # consta ou não entre os candidatos que os anexos delimitam. Se a operação se
    # enquadra na condição do anexo, isso depende de destinação/finalidade/regime —
    # dimensões que este endpoint não recebe e que não se inferem da NCM.
    candidatos = [c["codigo"] for c in ncm_candidatos(payload.ncm)]

    fora_dos_candidatos = bool(candidatos) and payload.classtrib_informado not in candidatos

    finding = None
    if fora_dos_candidatos:
        opcoes = ", ".join(candidatos)
        finding = {
            "id":             f"classtrib-{payload.ncm}-{payload.classtrib_informado}",
            "severity":       "WARNING",
            "rule_id":        "CBS-011",
            "title":          "cClassTrib informado não consta entre os candidatos da NCM",
            "where":          {"field": "cClassTrib", "snippet": payload.classtrib_informado},
            "recommendation": (
                f"Os Anexos da LC 214 relacionam a NCM {payload.ncm} aos cClassTrib {opcoes}, "
                f"e o código informado ('{payload.classtrib_informado}') não está entre eles. "
                "Os anexos catalogam tratamentos específicos e condicionados — não esgotam as "
                "situações possíveis para a NCM, e a tributação integral não é objeto de anexo. "
                "Não é, por si só, divergência: confirme se a operação se enquadra na condição "
                "do anexo (destinação, finalidade, regime) antes de alterar a classificação."
            ),
            "evidence_ids":   [],
        }

    return ValidateClassTribResponse(
        ncm=payload.ncm,
        classtrib_informado=payload.classtrib_informado,
        classtrib_sugerido=None,
        classtrib_candidatos=candidatos,
        status="NAO_DETERMINAVEL" if fora_dos_candidatos else "OK",
        divergencia=False,
        p_cbs_correto=float(item["p_cbs"]),
        p_ibs_correto=float(item["p_ibs"]),
        finding=finding,
    )
