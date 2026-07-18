"""CRM Engagement Crew — personalized dunning and win-back emails via LLM.

Status: Produção — ver knowledge/engineering/crews.md (tribultz-brain).

Architecture:
  1. CRM Analyst reads customer context (plan, usage, days since signup, subscription status)
  2. Email Copywriter composes a personalized PT-BR email targeting CBS/IBS compliance urgency
  3. Executor sends the email and logs an interaction note to HubSpot

This crew is triggered only for dunning (payment_overdue) and win-back (subscription_cancelled).
All HubSpot contact/deal stage sync is handled separately by the deterministic crm_sync task.

On LLMUnavailableError the caller falls back to a static template via email_service.
No memory — each invocation is a one-shot event.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from crewai import Agent, Crew, LLM, Process, Task

from app.crews.llm_config import LLMUnavailableError, execute_with_fallback
from app.crews.tools.crm_tools import (
    GetCustomerContextTool,
    HubSpotLogNoteTool,
    SendEmailTool,
)

logger = logging.getLogger(__name__)

# ── Event-specific copy guidance ───────────────────────────────

_EVENT_GUIDANCE: dict[str, dict[str, str]] = {
    "payment_overdue": {
        "tone": "urgent but empathetic",
        "objective": (
            "Recover the overdue payment. Remind the customer that their CBS/IBS compliance "
            "documentation is at risk. Mention the August/2026 LC 214 penalty deadline. "
            "Provide a clear CTA to update their payment method."
        ),
        "subject_hint": "Pagamento pendente — mantenha sua conformidade CBS/IBS",
    },
    "subscription_cancelled": {
        "tone": "warm and inviting",
        "objective": (
            "Win back the customer. Highlight what they'll miss (CBS/IBS validation, "
            "audit trails, LC 214 compliance) and the upcoming August/2026 deadline. "
            "Offer an easy path to reactivate."
        ),
        "subject_hint": "Sentimos sua falta — conformidade CBS/IBS ainda está ao seu alcance",
    },
}


class CRMEngagementCrew:
    """
    Runs the 3-agent CRM crew (Analyst → Copywriter → Executor).

    tenant_id, user_id, and customer PII are injected at construction
    and never flow through the LLM — agents receive only the tool output.
    """

    def __init__(
        self,
        user_id: str,
        tenant_id: str,
        event_type: str,
        to_email: str,
        user_name: str,
        company_name: str,
        transaction_id: str | None = None,
    ) -> None:
        self._user_id = user_id
        self._tenant_id = tenant_id
        self._event_type = event_type
        self._to_email = to_email
        self._user_name = user_name
        self._company_name = company_name
        self._transaction_id = transaction_id or str(uuid4())
        self._guidance = _EVENT_GUIDANCE.get(event_type, _EVENT_GUIDANCE["payment_overdue"])

    def _build_crew(self, llm: LLM) -> Crew:
        context_tool = GetCustomerContextTool(
            user_id=self._user_id,
            tenant_id=self._tenant_id,
        )
        email_tool = SendEmailTool(
            to_email=self._to_email,
            user_name=self._user_name,
        )
        note_tool = HubSpotLogNoteTool(company_name=self._company_name)

        analyst = Agent(
            role="CRM Analyst",
            goal=(
                "Read the customer context and produce a concise situation report "
                "covering subscription status, plan, usage, and compliance risk level."
            ),
            backstory=(
                "You are a B2B SaaS customer success analyst specializing in "
                "Brazilian tax reform compliance (CBS/IBS, LC 214). You understand "
                "that companies face real financial penalties if not compliant by August/2026."
            ),
            tools=[context_tool],
            llm=llm,
            verbose=False,
        )

        copywriter = Agent(
            role="Email Copywriter",
            goal=(
                f"Write a {self._guidance['tone']} email in Brazilian Portuguese. "
                f"Objective: {self._guidance['objective']} "
                f"Subject hint: '{self._guidance['subject_hint']}'. "
                "Keep the body under 200 words. No filler phrases. "
                "Sign off as 'Equipe Tribultz'."
            ),
            backstory=(
                "You are a senior B2B copywriter expert in PT-BR business communication. "
                "You write concise, direct emails that create urgency without being pushy. "
                "You never use CAPS LOCK for emphasis and avoid generic greetings."
            ),
            tools=[],
            llm=llm,
            verbose=False,
        )

        executor = Agent(
            role="CRM Executor",
            goal=(
                "Send the composed email using the send_email tool. "
                "Then log a summary note to HubSpot using the hubspot_log_note tool. "
                "The note must include: event type, date, and a one-line email summary."
            ),
            backstory=(
                "You are a reliable automation executor. You call tools in sequence, "
                "report the outcome precisely, and never hallucinate tool results."
            ),
            tools=[email_tool, note_tool],
            llm=llm,
            verbose=False,
        )

        task_analyze = Task(
            description=(
                "Call get_customer_context to retrieve the customer profile. "
                f"Customer email: {self._to_email}. Event: {self._event_type}. "
                "Summarize: plan, subscription status, days since signup, usage, and compliance risk."
            ),
            expected_output=(
                "A JSON-formatted situation report: {plan_slug, status, days_since_signup, "
                "validations_used, compliance_risk_level (low|medium|high)}."
            ),
            agent=analyst,
        )

        task_compose = Task(
            description=(
                "Using the analyst's situation report, write the email. "
                f"The customer's first name is extracted from: '{self._user_name}'. "
                "Output ONLY a JSON object: "
                "{\"subject\": \"...\", \"html_body\": \"...\", \"text_body\": \"...\"}. "
                "html_body must be valid HTML (use <p> tags, no external CSS). "
                "No markdown, no explanation outside the JSON."
            ),
            expected_output=(
                "A JSON object with keys: subject (str), html_body (str), text_body (str)."
            ),
            agent=copywriter,
            context=[task_analyze],
        )

        task_send = Task(
            description=(
                "1. Parse the JSON from the copywriter (subject, html_body, text_body). "
                "2. Call send_email with those exact values. "
                "3. Call hubspot_log_note with a note_body summarizing: "
                f"   event='{self._event_type}', date=today, action='personalized email sent'. "
                "Report the outcome of both tool calls."
            ),
            expected_output=(
                "A JSON object: {email_sent: bool, hubspot_logged: bool}."
            ),
            agent=executor,
            context=[task_compose],
        )

        return Crew(
            agents=[analyst, copywriter, executor],
            tasks=[task_analyze, task_compose, task_send],
            process=Process.sequential,
            verbose=False,
            memory=False,
        )

    def run(self) -> dict[str, Any]:
        """Execute the crew with LLM fallback chain. Returns outcome dict."""

        def _kickoff(llm: LLM) -> str:
            crew = self._build_crew(llm)
            return str(crew.kickoff())

        try:
            raw_output, tier_used, elapsed = execute_with_fallback(_kickoff)
            logger.info(
                "crm_engagement_complete event=%s user_id=%s tier=%s elapsed=%.2fs",
                self._event_type,
                self._user_id,
                tier_used.name,
                elapsed,
            )
            return {"status": "crew_completed", "event_type": self._event_type, "output": raw_output}

        except LLMUnavailableError as exc:
            logger.error(
                "crm_engagement LLM exhausted event=%s user_id=%s error=%s",
                self._event_type,
                self._user_id,
                str(exc)[:200],
            )
            return {"status": "llm_unavailable", "event_type": self._event_type}
