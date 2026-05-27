"""CRM crew tools — DB context reader, email sender, HubSpot note logger."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.database import SessionLocal

logger = logging.getLogger(__name__)


# ── GetCustomerContextTool ────────────────────────────────────

class _NoArgs(BaseModel):
    pass


class GetCustomerContextTool(BaseTool):
    name: str = "get_customer_context"
    description: str = (
        "Retrieve full customer context from the database: user profile, "
        "subscription status, plan details, and usage statistics. "
        "No arguments needed. Returns a JSON string."
    )
    args_schema: Type[BaseModel] = _NoArgs

    # Injected at construction — not exposed to LLM
    user_id: str
    tenant_id: str

    def _run(self) -> str:
        from sqlalchemy import select
        from app.models.auth import User, Tenant
        from app.models.billing import Subscription, Plan, UsageTracking

        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            period = now.strftime("%Y-%m")

            user = db.execute(
                select(User).where(User.id == self.user_id)
            ).scalar_one_or_none()

            if not user:
                return json.dumps({"error": "user not found"})

            tenant = db.execute(
                select(Tenant).where(Tenant.id == self.tenant_id)
            ).scalar_one_or_none()

            sub_row = db.execute(
                select(Subscription, Plan)
                .join(Plan, Subscription.plan_id == Plan.id)
                .where(Subscription.user_id == self.user_id)
                .order_by(Subscription.created_at.desc())
                .limit(1)
            ).first()

            usage = db.execute(
                select(UsageTracking).where(
                    UsageTracking.user_id == self.user_id,
                    UsageTracking.period == period,
                )
            ).scalar_one_or_none()

            sub_info: dict[str, Any] = {}
            plan_info: dict[str, Any] = {}
            if sub_row:
                sub, plan = sub_row
                trial_ends_at = sub.trial_ends_at
                period_end = sub.current_period_end
                days_since_signup = (
                    (now - sub.created_at.replace(tzinfo=timezone.utc)).days
                    if sub.created_at else 0
                )
                sub_info = {
                    "status": str(sub.status),
                    "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at else None,
                    "current_period_end": period_end.isoformat() if period_end else None,
                    "days_since_signup": days_since_signup,
                    "asaas_subscription_id": str(sub.asaas_subscription_id) if sub.asaas_subscription_id else None,
                }
                plan_info = {
                    "slug": str(plan.slug),
                    "name": str(plan.name),
                    "price_cents": int(plan.price_cents),  # type: ignore[arg-type]
                    "max_validations": plan.max_validations,
                    "has_pdf_reports": bool(plan.has_pdf_reports),
                }

            ctx = {
                "user": {
                    "full_name": str(user.full_name),
                    "email": str(user.email),
                    "account_type": str(user.account_type),
                    "cnpj": str(user.cnpj) if user.cnpj is not None else None,
                    "created_at": user.created_at.isoformat() if user.created_at is not None else None,
                },
                "company": {
                    "name": str(tenant.name) if tenant else "Empresa",
                    "slug": str(tenant.slug) if tenant else "",
                },
                "subscription": sub_info,
                "plan": plan_info,
                "usage": {
                    "validations_used": int(usage.validations_used) if usage else 0,  # type: ignore[arg-type]
                    "ai_messages_used": int(usage.ai_messages_used) if usage else 0,  # type: ignore[arg-type]
                    "period": period,
                },
                "compliance_context": (
                    "CBS/IBS penalties under LC 214 begin August/2026. "
                    "Companies without auditável documentation face fines."
                ),
            }
            return json.dumps(ctx, ensure_ascii=False)
        except Exception as exc:
            logger.exception("GetCustomerContextTool failed for user_id=%s", self.user_id)
            return json.dumps({"error": str(exc)})
        finally:
            db.close()


# ── SendEmailTool ─────────────────────────────────────────────

class SendEmailInput(BaseModel):
    subject: str = Field(description="Email subject line in PT-BR")
    html_body: str = Field(description="Full HTML body of the email")
    text_body: str = Field(description="Plain-text fallback body of the email")


class SendEmailTool(BaseTool):
    name: str = "send_email"
    description: str = (
        "Send a personalized email to the customer. "
        "Provide subject (PT-BR), html_body (full HTML), and text_body (plain text). "
        "Returns a JSON string with {sent: bool}."
    )
    args_schema: Type[BaseModel] = SendEmailInput

    # Injected at construction
    to_email: str
    user_name: str

    def _run(self, subject: str, html_body: str, text_body: str) -> str:
        from app.services.email_service import _send_email

        sent = _send_email(
            to_email=self.to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            log_url="",
        )
        logger.info("SendEmailTool sent=%s to=%s subject=%r", sent, self.to_email, subject)
        return json.dumps({"sent": sent, "to": self.to_email})


# ── HubSpotLogNoteTool ────────────────────────────────────────

class HubSpotLogNoteInput(BaseModel):
    note_body: str = Field(
        description="Note body summarizing the interaction (in PT-BR). Include event type, date, and what was done."
    )


class HubSpotLogNoteTool(BaseTool):
    name: str = "hubspot_log_note"
    description: str = (
        "Log an interaction note to the HubSpot company record. "
        "Provide note_body summarizing what happened (event type, action taken). "
        "Returns JSON with {logged: bool}."
    )
    args_schema: Type[BaseModel] = HubSpotLogNoteInput

    # Injected at construction
    company_name: str

    def _run(self, note_body: str) -> str:
        from app.tools.hubspot_tool import upsert_company, log_note
        from app.config import settings

        if not settings.HUBSPOT_ENABLED:
            return json.dumps({"logged": False, "reason": "hubspot_disabled"})

        try:
            company_result = upsert_company(name=self.company_name)
            company_id = company_result.get("id", "")
            if not company_id:
                return json.dumps({"logged": False, "reason": "company_id_missing"})

            log_note(
                object_type="companies",
                object_id=company_id,
                body=note_body,
            )
            logger.info("HubSpotLogNoteTool: note logged for company=%s", self.company_name)
            return json.dumps({"logged": True, "company_id": company_id})
        except Exception as exc:
            logger.exception("HubSpotLogNoteTool failed for company=%s", self.company_name)
            return json.dumps({"logged": False, "error": str(exc)})
