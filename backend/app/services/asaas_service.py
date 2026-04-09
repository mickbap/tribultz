"""Asaas payment gateway integration — customers, subscriptions, PIX, webhooks."""

import logging
import re
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URLS = {
    "sandbox": "https://sandbox.asaas.com/api",
    "production": "https://api.asaas.com",
}


def resolve_asaas_base_url(environment: str) -> str:
    """Return the canonical Asaas API origin for the given environment."""
    return _BASE_URLS.get(environment, _BASE_URLS["sandbox"])


def resolve_asaas_v3_base_url(environment: str) -> str:
    """Return the canonical v3 base URL used by health checks and probes."""
    return f"{resolve_asaas_base_url(environment)}/v3"


class AsaasError(Exception):
    """Raised when the Asaas API returns a non-2xx response."""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"Asaas API {status}: {detail}")


# ── CPF / CNPJ local validation ─────────────────────────────────

def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def _validate_cnpj(digits: str) -> bool:
    """Return True if CNPJ check digits are mathematically valid."""
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def _check(d: str, weights: list[int]) -> int:
        remainder = sum(int(d[i]) * w for i, w in enumerate(weights)) % 11
        return 0 if remainder < 2 else 11 - remainder

    return (
        _check(digits, weights1) == int(digits[12])
        and _check(digits, weights2) == int(digits[13])
    )


def _validate_cpf(digits: str) -> bool:
    """Return True if CPF check digits are mathematically valid."""
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    weights1 = list(range(10, 1, -1))
    weights2 = list(range(11, 1, -1))

    def _check(d: str, weights: list[int]) -> int:
        remainder = (sum(int(d[i]) * w for i, w in enumerate(weights)) * 10) % 11
        return 0 if remainder >= 10 else remainder

    return (
        _check(digits, weights1) == int(digits[9])
        and _check(digits, weights2) == int(digits[10])
    )


def validate_cpf_cnpj(raw: str) -> str:
    """Validate and return cleaned CPF/CNPJ digits, or raise AsaasError(400).

    Validates both format (length) and check-digit checksum so that invalid
    documents are caught *before* hitting the Asaas API.
    """
    digits = _digits_only(raw)
    if len(digits) == 14:
        if not _validate_cnpj(digits):
            raise AsaasError(400, f"CNPJ inválido: '{raw}'. Verifique os dígitos verificadores.")
        return digits
    if len(digits) == 11:
        if not _validate_cpf(digits):
            raise AsaasError(400, f"CPF inválido: '{raw}'. Verifique os dígitos verificadores.")
        return digits
    raise AsaasError(
        400,
        f"CPF/CNPJ deve ter 11 (CPF) ou 14 (CNPJ) dígitos. Recebido: {len(digits)} dígito(s).",
    )


class AsaasService:
    """Thin async wrapper around the Asaas REST API v3."""

    def __init__(self) -> None:
        env = settings.ASAAS_ENVIRONMENT
        self.base_url = resolve_asaas_base_url(env)
        self.api_key = settings.ASAAS_API_KEY
        self.webhook_token = settings.ASAAS_WEBHOOK_TOKEN

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "access_token": self.api_key,
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(
                method, url, headers=self._headers(), json=json
            )
        if resp.status_code >= 400:
            detail = resp.text
            logger.error("Asaas %s %s → %s: %s", method, path, resp.status_code, detail)
            raise AsaasError(resp.status_code, detail)
        return resp.json()

    # ── Customers ───────────────────────────────────────────────

    async def create_customer(
        self,
        name: str,
        email: str,
        cpf_cnpj: str,
        phone: str = "",
    ) -> dict[str, Any]:
        """Create an Asaas customer. Returns the full customer object.

        Validates CPF/CNPJ checksum locally before calling the API so that
        invalid documents surface with a clear error rather than an opaque 400.
        """
        clean_cpf_cnpj = validate_cpf_cnpj(cpf_cnpj)  # raises AsaasError(400) if invalid
        payload: dict[str, Any] = {
            "name": name,
            "email": email,
            "cpfCnpj": clean_cpf_cnpj,
        }
        if phone:
            payload["mobilePhone"] = phone
        result = await self._request("POST", "/v3/customers", json=payload)
        logger.info("Asaas customer created: %s", result.get("id"))
        return result

    # ── Subscriptions ───────────────────────────────────────────

    async def create_subscription(
        self,
        customer_id: str,
        value: float,
        billing_type: str = "CREDIT_CARD",
        description: str = "Assinatura Tribultz",
        next_due_date: str | None = None,
    ) -> dict[str, Any]:
        """Create a monthly subscription. billing_type: CREDIT_CARD | PIX | BOLETO."""
        payload: dict[str, Any] = {
            "customer": customer_id,
            "billingType": billing_type,
            "value": value,
            "cycle": "MONTHLY",
            "description": description,
        }
        if next_due_date:
            payload["nextDueDate"] = next_due_date
        result = await self._request("POST", "/v3/subscriptions", json=payload)
        logger.info("Asaas subscription created: %s", result.get("id"))
        return result

    async def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v3/subscriptions/{subscription_id}")

    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        return await self._request("DELETE", f"/v3/subscriptions/{subscription_id}")

    # ── Payments ────────────────────────────────────────────────

    async def create_payment(
        self,
        customer_id: str,
        value: float,
        billing_type: str = "PIX",
        description: str = "Pagamento Tribultz",
        due_date: str | None = None,
    ) -> dict[str, Any]:
        """Create a standalone payment (useful for first payment + PIX)."""
        payload: dict[str, Any] = {
            "customer": customer_id,
            "billingType": billing_type,
            "value": value,
            "description": description,
        }
        if due_date:
            payload["dueDate"] = due_date
        result = await self._request("POST", "/v3/payments", json=payload)
        logger.info("Asaas payment created: %s", result.get("id"))
        return result

    async def get_payment(self, payment_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v3/payments/{payment_id}")

    async def get_pix_qr_code(self, payment_id: str) -> dict[str, Any]:
        """Returns {encodedImage: base64_png, payload: copy_paste_code, expirationDate}."""
        result = await self._request("GET", f"/v3/payments/{payment_id}/pixQrCode")
        logger.info("Asaas PIX QR code retrieved for payment %s", payment_id)
        return result

    # ── Checkout ────────────────────────────────────────────────

    def get_checkout_url(self, payment_id: str) -> str:
        """Returns the Asaas hosted checkout URL for SAQ-A compliant card payment."""
        env_prefix = "sandbox" if "sandbox" in self.base_url else "www"
        return f"https://{env_prefix}.asaas.com/c/{payment_id}"

    # ── Webhook verification ────────────────────────────────────

    def verify_webhook_token(self, token: str) -> bool:
        """Validate the asaas-access-token header from webhooks."""
        if not self.webhook_token:
            logger.warning("ASAAS_WEBHOOK_TOKEN not configured, rejecting webhook")
            return False
        return token == self.webhook_token


# Singleton instance
asaas = AsaasService()
