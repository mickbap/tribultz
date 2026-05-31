"""Simulador de Impacto por Regime Tributário — Fase A.

Compara carga tributária atual (ICMS + PIS/COFINS + ISS) vs reforma
(CBS + IBS) para planejamento de longo prazo.

Endpoint público, stateless, sem migration, sem autenticação.

Fase A: taxas referenciais simplificadas por regime.
Fase B (futuras issues): regimes diferenciados, cashback, setor específico.
"""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from app.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["simulator"])

_rate_limiter = RateLimiter()
_rate_limiter.limit = 30  # 30 req/min por IP


def _client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return [p.strip() for p in fwd.split(",")][-1]
    return request.client.host if request.client else "unknown"


# ── Taxas simplificadas por regime (Fase A) ──────────────────────────────────

# Old regime — taxas referenciais nacionais (simplificado para planejamento)
_PISCOFINS = {
    "lucro_real":       Decimal("0.0925"),  # PIS 1,65% + COFINS 7,6% (não-cumulativo)
    "lucro_presumido":  Decimal("0.0365"),  # PIS 0,65% + COFINS 3% (cumulativo)
    "simples_comercio": Decimal("0.0350"),  # Simples Anexo I — alíquota efetiva média
    "simples_servicos": Decimal("0.0600"),  # Simples Anexo III — alíquota efetiva média
}

# ICMS médio nacional em produtos (simplificado)
_ICMS_PRODUTO = Decimal("0.1200")  # 12%
# ISS médio em serviços
_ISS_SERVICO  = Decimal("0.0300")  # 3%

# New regime — alíquotas de referência plenas (2033, LC 214/2025)
# Usamos referência plena para planejamento de longo prazo, não a transição 2026.
_CBS_PLENA = Decimal("0.0880")   # 8,80%
_IBS_PLENA = Decimal("0.1770")   # 17,70% (média nacional UF + Municipal)


# ── Schemas ──────────────────────────────────────────────────────────────────

REGIMES = {"lucro_real", "lucro_presumido", "simples_comercio", "simples_servicos"}
SETORES = {"servicos", "produtos", "misto"}


class SimulatorRequest(BaseModel):
    faturamento_anual: Decimal = Field(..., gt=0, description="Faturamento anual em R$")
    regime_tributario: str = Field(..., description="lucro_real | lucro_presumido | simples_comercio | simples_servicos")
    setor: str = Field("misto", description="servicos | produtos | misto")
    percentual_servicos: int = Field(50, ge=0, le=100, description="% da receita de serviços (0-100)")
    uf: str = Field("SP", description="UF do estabelecimento")

    @field_validator("regime_tributario")
    @classmethod
    def validate_regime(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in REGIMES:
            raise ValueError(f"regime_tributario deve ser um de: {', '.join(sorted(REGIMES))}")
        return v

    @field_validator("setor")
    @classmethod
    def validate_setor(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in SETORES:
            raise ValueError(f"setor deve ser um de: {', '.join(sorted(SETORES))}")
        return v

    @field_validator("uf")
    @classmethod
    def validate_uf(cls, v: str) -> str:
        return v.upper().strip()[:2]


class RegimeTaxDetail(BaseModel):
    pis_cofins: Decimal
    icms: Decimal
    iss: Decimal
    total: Decimal
    aliquota_efetiva_pct: Decimal  # porcentagem (ex: 6.65)


class ReformTaxDetail(BaseModel):
    cbs: Decimal
    ibs: Decimal
    total: Decimal
    aliquota_efetiva_pct: Decimal


class DeltaDetail(BaseModel):
    valor_absoluto: Decimal        # R$ a mais ou a menos
    pontos_percentuais: Decimal    # diferença em p.p.
    variacao_relativa_pct: Decimal # % de variação vs regime atual
    direcao: str                   # "aumento" | "reducao" | "neutro"


class SimulatorResponse(BaseModel):
    faturamento_anual: Decimal
    regime_tributario: str
    setor: str
    percentual_servicos: int

    regime_atual: RegimeTaxDetail
    regime_novo: ReformTaxDetail
    delta: DeltaDetail

    insight: str
    notas: list[str]

    # Metadados
    fase: str = "A"
    disclaimer: str = (
        "Estimativa simplificada para planejamento. Taxas referenciais nacionais (LC 214/2025 + "
        "LC 227/2026). Regimes diferenciados, cashback e benefícios setoriais não incluídos "
        "nesta fase. Consulte um contador para análise específica."
    )


# ── Cálculo ───────────────────────────────────────────────────────────────────

_Q = Decimal("0.01")
_QP = Decimal("0.001")  # percentual com 3 casas


def _q(v: Decimal) -> Decimal:
    return v.quantize(_Q, ROUND_HALF_UP)


def _qp(v: Decimal) -> Decimal:
    return v.quantize(_QP, ROUND_HALF_UP)


def _brl(v: Decimal) -> str:
    """Formata Decimal como moeda pt-BR: R$ 198.500,00"""
    abs_v = abs(v)
    int_part = int(abs_v)
    dec_part = int(round((abs_v - int_part) * 100))
    int_str = f"{int_part:,}".replace(",", ".")
    return f"R$ {int_str},{dec_part:02d}"


def _simulate(req: SimulatorRequest) -> SimulatorResponse:
    fat = req.faturamento_anual
    pct_svc = Decimal(req.percentual_servicos) / Decimal(100)
    pct_prod = Decimal(1) - pct_svc

    fat_svc  = fat * pct_svc
    fat_prod = fat * pct_prod

    # ── Regime atual ──────────────────────────────────────────────────────────
    piscofins_rate = _PISCOFINS[req.regime_tributario]
    piscofins_val  = _q(fat * piscofins_rate)
    icms_val       = _q(fat_prod * _ICMS_PRODUTO)
    iss_val        = _q(fat_svc  * _ISS_SERVICO)
    total_atual    = piscofins_val + icms_val + iss_val
    aliq_atual     = _qp(total_atual / fat * 100) if fat else Decimal(0)

    regime_atual = RegimeTaxDetail(
        pis_cofins=piscofins_val,
        icms=icms_val,
        iss=iss_val,
        total=total_atual,
        aliquota_efetiva_pct=aliq_atual,
    )

    # ── Reforma (alíquotas plenas 2033) ───────────────────────────────────────
    cbs_val    = _q(fat * _CBS_PLENA)
    ibs_val    = _q(fat * _IBS_PLENA)
    total_novo = cbs_val + ibs_val
    aliq_novo  = _qp(total_novo / fat * 100) if fat else Decimal(0)

    regime_novo = ReformTaxDetail(
        cbs=cbs_val,
        ibs=ibs_val,
        total=total_novo,
        aliquota_efetiva_pct=aliq_novo,
    )

    # ── Delta ─────────────────────────────────────────────────────────────────
    delta_val = _q(total_novo - total_atual)
    delta_pp  = _qp(aliq_novo - aliq_atual)
    var_rel   = _qp(delta_val / total_atual * 100) if total_atual else Decimal(0)
    direcao   = "aumento" if delta_val > 0 else ("reducao" if delta_val < 0 else "neutro")

    delta = DeltaDetail(
        valor_absoluto=abs(delta_val),
        pontos_percentuais=abs(delta_pp),
        variacao_relativa_pct=abs(var_rel),
        direcao=direcao,
    )

    # ── Insight ───────────────────────────────────────────────────────────────
    regime_labels = {
        "lucro_real":       "Lucro Real",
        "lucro_presumido":  "Lucro Presumido",
        "simples_comercio": "Simples Nacional (comércio)",
        "simples_servicos": "Simples Nacional (serviços)",
    }
    setor_label = {
        "servicos": "serviços",
        "produtos": "produtos",
        "misto":    f"{req.percentual_servicos}% serviços / {100 - req.percentual_servicos}% produtos",
    }[req.setor]

    if direcao == "aumento":
        insight = (
            f"No {regime_labels[req.regime_tributario]}, sua carga tributária sobre {setor_label} "
            f"deve aumentar de {aliq_atual}% para {aliq_novo}% com a Reforma Tributária — "
            f"acréscimo de {_brl(delta_val)}/ano ({var_rel}% a mais). "
            f"Agosto/2026 inicia o período de penalidades."
        )
    elif direcao == "reducao":
        insight = (
            f"No {regime_labels[req.regime_tributario]}, sua carga tributária sobre {setor_label} "
            f"deve cair de {aliq_atual}% para {aliq_novo}% com a Reforma Tributária — "
            f"economia de {_brl(delta_val)}/ano ({abs(var_rel)}% a menos). "
            f"A não-cumulatividade plena do IBS pode ampliar o benefício."
        )
    else:
        insight = (
            f"Sua carga tributária estimada permanece em torno de {aliq_atual}% "
            f"na transição para CBS/IBS."
        )

    # ── Notas ─────────────────────────────────────────────────────────────────
    notas = [
        "Taxas referenciais plenas (2033): CBS 8,80% + IBS 17,70% = 26,50% total.",
        f"Regime atual: PIS/COFINS {float(piscofins_rate*100):.2f}%"
        + (" + ICMS ~12% (produtos)" if pct_prod > 0 else "")
        + (" + ISS ~3% (serviços)" if pct_svc > 0 else "") + ".",
        "Durante 2026 (transição), as alíquotas CBS/IBS são frações das plenas — o impacto financeiro real é progressivo até 2033.",
    ]
    if req.regime_tributario.startswith("simples"):
        notas.append(
            "Empresas do Simples Nacional podem ter tratamento especial na Reforma. "
            "Verifique enquadramento com seu contador."
        )
    if pct_svc > Decimal("0.5"):
        notas.append(
            "Empresas de serviços geralmente terão a maior mudança na carga tributária "
            "devido ao fim do ISS e entrada do IBS com alíquota superior."
        )

    return SimulatorResponse(
        faturamento_anual=fat,
        regime_tributario=regime_labels[req.regime_tributario],
        setor=req.setor,
        percentual_servicos=req.percentual_servicos,
        regime_atual=regime_atual,
        regime_novo=regime_novo,
        delta=delta,
        insight=insight,
        notas=notas,
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/api/v1/public/simulator/regime",
    response_model=SimulatorResponse,
    summary="Simulador de impacto CBS/IBS por regime tributário (público)",
)
async def simulate_regime(body: SimulatorRequest, request: Request) -> SimulatorResponse:
    """Compara carga tributária atual vs reforma (CBS+IBS) para planejamento.

    Fase A: taxas referenciais simplificadas por regime tributário e setor.
    Sem autenticação. Rate-limited por IP.
    """
    ip = _client_ip(request)
    _rate_limiter.check_or_raise(f"simulator:{ip}")
    return _simulate(body)
