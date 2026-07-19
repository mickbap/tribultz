"""Founding Partners — camada de licenciamento (RFC-0017 + ADR-0008) + Cockpit
Operacional do Programa Early Adopters (RFC-0024).

Entidades + um resolvedor:

- ``EarlyAdopter`` — a empresa admitida no programa (RF001). "Founding Partner" é
  o **reconhecimento** (`recognition`), não o nome do programa nem outra entidade;
  a entidade técnica permanece Early Adopter.
- ``EarlyGrant`` — a **autorização operacional**: concede um plano (Contador) por
  uma vigência, sem assinatura ASAAS. Nunca representa pagamento.
- ``EarlyAdopterJourneyEvent`` — eventos de jornada lançados manualmente pelo
  Owner (Tela 02). Os eventos automáticos (1º login, XML recebido) **não são
  armazenados aqui** — são derivados ao vivo no endpoint de detalhe a partir do
  próprio sistema (`users.first_login_at`/`last_login_at`, contagem de `Job`),
  para honrar o princípio "observar, não replicar" (RFC-0024).
- ``CustomerEvidence`` — captura de Discovery por participante (RFC-0019/ADR-0005):
  este módulo nunca altera o Brain automaticamente; é só a superfície de captura.
- ``EarlyAdopterTera`` — registro **manual** do TERA (upload/link de PDF); a
  geração automática depende do RFC-0018, ainda não construído.
- ``resolve_effective_license`` — o Grant Adapter (ADR-0008): no login,
  ``plan_slug = grant.plan_slug`` se houver Grant ativo, senão ``subscription``.

Guardrails (RFC-0017 RNF001/002, ADR-0008): ASAAS é a única origem de assinaturas
pagas; o Grant é autorização excepcional — nunca cria/altera Subscription.
Expiração é **lazy no login** (sem Celery beat): "ativo = status ativo E
hoje ∈ [starts_at, ends_at]".
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from app.database import Base

# Enum de origem de aquisição — reconciliado na RFC-0024 (Tela 02). Valores
# legados do RFC-0017 (microsoft_forms, contato_direto) foram migrados para
# "outro" na migration 2026_07_19_0028; alimenta o Marketing Brain.
EA_ORIGINS: tuple[str, ...] = (
    "linkedin",
    "instagram",
    "indicacao",
    "cliente_6tech",
    "google",
    "site",
    "evento",
    "outro",
)

EA_STATUSES: tuple[str, ...] = ("active", "closed")
GRANT_STATUSES: tuple[str, ...] = ("active", "revoked", "expired")

# Reconhecimento (RFC-0024): status conquistado, permanente — não é etapa da
# jornada. "founding_partner" quando atingir critério (reuniões, XML, validação,
# melhorias, permanência como cliente); avaliação é manual pelo Owner.
RECOGNITION_LEVELS: tuple[str, ...] = ("early_adopter", "founding_partner")

# Jornada (RFC-0024, Tela 02) — eventos manuais; os automáticos (Primeiro login,
# XML recebido) são derivados ao vivo, nunca gravados nesta tabela.
JOURNEY_STAGES: tuple[str, ...] = (
    "convite_enviado",
    "formulario_recebido",
    "selecionado",
    "convite_acesso_enviado",
    "primeiro_login",
    "xml_recebido",
    "tera_em_preparacao",
    "tera_apresentado",
    "reuniao_realizada",
    "em_acompanhamento",
    "convertido",
    "encerrado",
)

# Customer Evidence (RFC-0024, guardrail RFC-0019/ADR-0005: Discovery, nunca Knowledge).
EVIDENCE_TYPES: tuple[str, ...] = (
    "problema_percebido",
    "problema_confirmado",
    "objecao",
    "frase_marcante",
    "momento_wow",
    "momento_friccao",
    "insight",
    "hipotese",
    "aprendizado",
    "proximo_passo",
)

TERA_STATUSES: tuple[str, ...] = ("rascunho", "apresentado")

CONVERSION_INTERESSE: tuple[str, ...] = ("sim", "nao", "pensando")

# Plano concedido por padrão a um Founding Partner (RF003).
DEFAULT_GRANT_PLAN = "contador"


class EarlyAdopter(Base):
    __tablename__ = "early_adopters"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # A empresa provisionada (login vive aqui). RESTRICT: nunca apagar com histórico.
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    empresa = Column(String(200), nullable=False)
    cnpj = Column(String(20), nullable=True)
    email = Column(String(255), nullable=False)
    responsavel = Column(String(200), nullable=True)
    telefone = Column(String(32), nullable=True)  # exibido como "WhatsApp" na Tela 02
    origem = Column(String(32), nullable=False, server_default="outro")
    status = Column(String(16), nullable=False, server_default="active")
    observacoes = Column(Text, nullable=True)
    # Cadastrais expandidos (RFC-0024, Tela 02).
    cargo = Column(String(100), nullable=True)
    cidade = Column(String(100), nullable=True)
    uf = Column(String(2), nullable=True)
    erp = Column(String(100), nullable=True)
    qtd_cnpjs = Column(Integer, nullable=True)
    volume_nfe_mensal_aprox = Column(Integer, nullable=True)
    # Operação do cockpit (RFC-0024).
    proxima_acao = Column(Text, nullable=True)
    owner_email = Column(String(255), nullable=True)
    recognition = Column(String(20), nullable=False, server_default="early_adopter")
    # Conversão (Tela 02) — inicia o fluxo ASAAS existente, nunca substitui.
    conversion_interesse = Column(String(20), nullable=True)
    conversion_motivo = Column(Text, nullable=True)
    conversion_plano_slug = Column(String(50), nullable=True)
    conversion_data = Column(DateTime(timezone=True), nullable=True)
    conversion_valor_cents = Column(Integer, nullable=True)
    conversion_origem = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class EarlyGrant(Base):
    __tablename__ = "early_grants"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    early_adopter_id = Column(
        UUID(as_uuid=True), ForeignKey("early_adopters.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalizado para a resolução no login ser uma consulta de tabela única.
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    plan_slug = Column(String(50), nullable=False, server_default=DEFAULT_GRANT_PLAN)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(16), nullable=False, server_default="active")
    granted_by_email = Column(String(255), nullable=True)
    reason = Column(Text, nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class EarlyAdopterJourneyEvent(Base):
    __tablename__ = "early_adopter_journey_events"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    early_adopter_id = Column(
        UUID(as_uuid=True), ForeignKey("early_adopters.id", ondelete="CASCADE"), nullable=False
    )
    stage = Column(String(40), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    note = Column(Text, nullable=True)
    created_by_email = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CustomerEvidence(Base):
    __tablename__ = "customer_evidence"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    early_adopter_id = Column(
        UUID(as_uuid=True), ForeignKey("early_adopters.id", ondelete="CASCADE"), nullable=False
    )
    tipo = Column(String(30), nullable=False)
    texto = Column(Text, nullable=False)
    autor = Column(String(200), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EarlyAdopterTera(Base):
    __tablename__ = "early_adopter_tera"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    early_adopter_id = Column(
        UUID(as_uuid=True), ForeignKey("early_adopters.id", ondelete="CASCADE"), nullable=False
    )
    versao = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, server_default="rascunho")
    responsavel = Column(String(200), nullable=True)
    storage_key = Column(String(500), nullable=True)
    pdf_link = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _aware(dt: datetime) -> datetime:
    """Garante timezone-aware (colunas são timezone=True; defensivo para SQLite/testes)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def grant_is_active(grant: EarlyGrant, now: datetime | None = None) -> bool:
    """Vigência efetiva (ADR-0008): status ativo E hoje ∈ [starts_at, ends_at].

    Um Grant expirado (``ends_at`` no passado) ou revogado retorna ``False`` —
    é assim que a expiração/revogação encerra o acesso automaticamente, sem beat.
    """
    if str(grant.status) != "active":
        return False
    moment = now or datetime.now(timezone.utc)
    starts = _aware(cast(datetime, grant.starts_at))
    ends = _aware(cast(datetime, grant.ends_at))
    return starts <= moment <= ends


def effective_grant_status(grant: EarlyGrant, now: datetime | None = None) -> str:
    """Status para exibição no Command Center: 'active' vencido vira 'expired'."""
    if str(grant.status) == "active" and not grant_is_active(grant, now):
        return "expired"
    return str(grant.status)


def resolve_effective_license(
    db: Session,
    tenant_id,
    subscription_plan_slug: str,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Grant Adapter (ADR-0008) — ponto único de resolução de licença.

    Retorna ``(plan_slug, source)``: o plano do Grant ativo do tenant, se houver;
    senão o plano da assinatura. **2 fontes, 1 pergunta, 1 ponto.** ASAAS intacto.
    """
    moment = now or datetime.now(timezone.utc)
    grant = db.execute(
        select(EarlyGrant)
        .where(
            EarlyGrant.tenant_id == tenant_id,
            EarlyGrant.status == "active",
            EarlyGrant.starts_at <= moment,
            EarlyGrant.ends_at >= moment,
        )
        .order_by(EarlyGrant.ends_at.desc())
        .limit(1)
    ).scalars().first()
    if grant is not None:
        return str(grant.plan_slug), "early_grant"
    return subscription_plan_slug, "subscription"
