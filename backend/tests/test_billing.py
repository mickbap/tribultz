"""Tests for billing models, Asaas service, plan gate, and Celery tasks."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.asaas_service import AsaasService, AsaasError
from app.schemas.auth import UserRegister


# ── Asaas Service tests ─────────────────────────────────────────────────────


class TestAsaasService:
    def setup_method(self):
        self.svc = AsaasService()
        self.svc.api_key = "test_key"
        self.svc.base_url = "https://sandbox.asaas.com/api"
        self.svc.webhook_token = "test_webhook_token"

    def test_headers(self):
        h = self.svc._headers()
        assert h["access_token"] == "test_key"
        assert h["Content-Type"] == "application/json"

    def test_checkout_url_sandbox(self):
        url = self.svc.get_checkout_url("pay_123")
        assert url == "https://sandbox.asaas.com/c/pay_123"

    def test_checkout_url_production(self):
        self.svc.base_url = "https://api.asaas.com"
        url = self.svc.get_checkout_url("pay_456")
        assert url == "https://www.asaas.com/c/pay_456"

    def test_verify_webhook_token_valid(self):
        assert self.svc.verify_webhook_token("test_webhook_token") is True

    def test_verify_webhook_token_invalid(self):
        assert self.svc.verify_webhook_token("wrong_token") is False

    def test_verify_webhook_token_empty_config(self):
        self.svc.webhook_token = ""
        assert self.svc.verify_webhook_token("any") is False

    @pytest.mark.asyncio
    async def test_create_customer(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "cus_123", "name": "Test"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.svc.create_customer(
                name="Empresa X",
                email="test@example.com",
                cpf_cnpj="11.222.333/0001-81",  # valid CNPJ with check digits
                phone="11999998888",
            )
            assert result["id"] == "cus_123"
            call_args = mock_client.request.call_args
            assert call_args[0][0] == "POST"
            body = call_args[1]["json"]
            assert body["cpfCnpj"] == "11222333000181"  # cleaned digits sent to API
            assert body["mobilePhone"] == "11999998888"

    @pytest.mark.asyncio
    async def test_create_customer_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"errors":[{"description":"cpfCnpj inválido"}]}'

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(AsaasError) as exc_info:
                await self.svc.create_customer("X", "x@x.com", "invalid")
            assert exc_info.value.status == 400

    @pytest.mark.asyncio
    async def test_get_pix_qr_code(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "encodedImage": "iVBORw0KGgo...",
            "payload": "00020101021226...",
            "expirationDate": "2026-12-31",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.svc.get_pix_qr_code("pay_789")
            assert "encodedImage" in result
            assert "payload" in result


# ── Plan definitions tests ───────────────────────────────────────────────────


class TestPlanDefinitions:
    """Verify plan feature matrix is consistent."""

    PLANS = {
        "trial": {
            "price_cents": 0,
            "max_validations": 5,
            "max_ai_messages": 25,
            "has_pdf_reports": False,
            "has_batch": False,
            "has_dashboard": False,
            "trial_days": 3,
        },
        "starter": {
            "price_cents": 4990,
            "max_validations": 10,
            "max_ai_messages": 50,
            "has_pdf_reports": False,
            "has_batch": False,
            "has_dashboard": True,
            "trial_days": None,
        },
        "profissional": {
            "price_cents": 14900,
            "max_validations": 500,
            "max_ai_messages": None,
            "has_pdf_reports": True,
            "has_batch": True,
            "has_dashboard": True,
            "trial_days": None,
        },
        "contador": {
            "price_cents": 34900,
            "max_validations": None,
            "max_ai_messages": None,
            "has_pdf_reports": True,
            "has_batch": True,
            "has_dashboard": True,
            "trial_days": None,
        },
    }

    def test_trial_is_free(self):
        assert self.PLANS["trial"]["price_cents"] == 0

    def test_starter_price(self):
        assert self.PLANS["starter"]["price_cents"] == 4990  # R$49,90

    def test_profissional_price(self):
        assert self.PLANS["profissional"]["price_cents"] == 14900  # R$149,00

    def test_contador_price(self):
        assert self.PLANS["contador"]["price_cents"] == 34900  # R$349,00

    def test_trial_limits(self):
        assert self.PLANS["trial"]["max_validations"] == 5
        assert self.PLANS["trial"]["max_ai_messages"] == 25

    def test_starter_limits(self):
        assert self.PLANS["starter"]["max_validations"] == 10
        assert self.PLANS["starter"]["max_ai_messages"] == 50

    def test_pro_has_pdf(self):
        assert self.PLANS["profissional"]["has_pdf_reports"] is True
        assert self.PLANS["contador"]["has_pdf_reports"] is True

    def test_starter_no_pdf(self):
        assert self.PLANS["trial"]["has_pdf_reports"] is False
        assert self.PLANS["starter"]["has_pdf_reports"] is False

    def test_trial_no_dashboard(self):
        assert self.PLANS["trial"]["has_dashboard"] is False

    def test_starter_has_dashboard(self):
        assert self.PLANS["starter"]["has_dashboard"] is True

    def test_contador_unlimited_validations(self):
        assert self.PLANS["contador"]["max_validations"] is None

    def test_pro_unlimited_ai(self):
        assert self.PLANS["profissional"]["max_ai_messages"] is None


# ── Registration schema validation tests ──────────────────────────────────


class TestUserRegisterValidation:
    """Validate UserRegister Pydantic schema validators."""

    def _base_data(self, **overrides):
        defaults = {
            "email": "test@example.com",
            "password": "Senha123!",
            "full_name": "Maria Silva",
            "cnpj": "",
            "phone": "",
            "account_type": "empresa",
            "plan_slug": "trial",
            "billing_type": "PIX",
            "lgpd_consent": True,
            "tenant_slug": "default",
        }
        defaults.update(overrides)
        return defaults

    def test_valid_trial_registration(self):
        data = UserRegister(**self._base_data())
        assert data.plan_slug == "trial"

    def test_valid_paid_registration(self):
        data = UserRegister(**self._base_data(plan_slug="starter"))
        assert data.plan_slug == "starter"

    def test_invalid_plan_slug(self):
        with pytest.raises(ValueError):
            UserRegister(**self._base_data(plan_slug="enterprise"))

    def test_phone_valid_11_digits(self):
        data = UserRegister(**self._base_data(phone="(11) 99999-8888"))
        assert data.phone == "11999998888"

    def test_phone_valid_10_digits(self):
        data = UserRegister(**self._base_data(phone="(11) 3333-8888"))
        assert data.phone == "1133338888"

    def test_phone_too_short(self):
        with pytest.raises(ValueError):
            UserRegister(**self._base_data(phone="123"))

    def test_phone_empty_allowed(self):
        data = UserRegister(**self._base_data(phone=""))
        assert data.phone == ""

    def test_password_too_short(self):
        with pytest.raises(ValueError):
            UserRegister(**self._base_data(password="abc"))

    def test_cnpj_valid_14_digits(self):
        data = UserRegister(**self._base_data(cnpj="12.345.678/0001-99"))
        assert data.cnpj == "12345678000199"

    def test_cnpj_wrong_length(self):
        with pytest.raises(ValueError):
            UserRegister(**self._base_data(cnpj="12345"))

    def test_lgpd_consent_required(self):
        with pytest.raises(ValueError):
            UserRegister(**self._base_data(lgpd_consent=False))

    def test_account_type_invalid(self):
        with pytest.raises(ValueError):
            UserRegister(**self._base_data(account_type="admin"))

    def test_full_name_too_short(self):
        with pytest.raises(ValueError):
            UserRegister(**self._base_data(full_name="A"))


# ── Celery task imports test ──────────────────────────────────────────────


class TestBillingCeleryTasks:
    """Verify billing Celery tasks are importable and registered."""

    def test_expire_trials_importable(self):
        from app.tasks.task_g_billing import expire_trials
        assert expire_trials.name == "billing.expire_trials"

    def test_reset_monthly_usage_importable(self):
        from app.tasks.task_g_billing import reset_monthly_usage
        assert reset_monthly_usage.name == "billing.reset_monthly_usage"


# ── Billing router imports test ───────────────────────────────────────────


class TestBillingRouter:
    """Verify billing router is importable and has expected endpoints."""

    def test_router_importable(self):
        from app.routers.billing import router
        assert router.prefix == "/api/v1/billing"

    def test_webhook_route_exists(self):
        from app.routers.billing import router
        paths = [getattr(r, "path", "") for r in router.routes]
        assert any("webhooks/asaas" in p for p in paths)

    def test_billing_me_route_exists(self):
        from app.routers.billing import router
        paths = [getattr(r, "path", "") for r in router.routes]
        assert any(p.endswith("/me") for p in paths)

    def test_payments_route_exists(self):
        from app.routers.billing import router
        paths = [getattr(r, "path", "") for r in router.routes]
        assert any(p.endswith("/payments") for p in paths)

    def test_upgrade_route_exists(self):
        from app.routers.billing import router
        paths = [getattr(r, "path", "") for r in router.routes]
        assert any(p.endswith("/upgrade") for p in paths)

    def test_cancel_route_exists(self):
        from app.routers.billing import router
        paths = [getattr(r, "path", "") for r in router.routes]
        assert any(p.endswith("/cancel") for p in paths)


# ── Plan gate imports test ────────────────────────────────────────────────


class TestPlanGate:
    """Verify plan gate functions are importable and return callables."""

    def test_require_plan_returns_callable(self):
        from app.api.plan_gate import require_plan
        dep = require_plan("profissional", "contador")
        assert callable(dep)

    def test_check_usage_limit_returns_callable(self):
        from app.api.plan_gate import check_usage_limit
        dep = check_usage_limit("validations")
        assert callable(dep)

    def test_increment_usage_importable(self):
        from app.api.plan_gate import increment_usage
        assert callable(increment_usage)


# ── Trial plan access to XML validation (issue #231) ──────────────────────


class TestValidateXmlTrialAccess:
    """Trial plan must reach /validate/xml and be bounded by max_validations quota."""

    def _routes(self):
        from app.routers.validate_xml import router
        return {getattr(r, "path", ""): r for r in router.routes}

    def _allowed_slugs(self, route):
        # require_plan closure captures allowed_slugs; inspect free vars
        for dep in route.dependant.dependencies:
            fn = dep.call
            cells = getattr(fn, "__closure__", None) or ()
            for cell in cells:
                val = cell.cell_contents
                if isinstance(val, tuple) and val and all(isinstance(s, str) for s in val):
                    if "starter" in val or "profissional" in val or "trial" in val:
                        return val
        return None

    def _has_usage_check(self, route):
        for dep in route.dependant.dependencies:
            fn = dep.call
            cells = getattr(fn, "__closure__", None) or ()
            for cell in cells:
                if cell.cell_contents == "validations":
                    return True
        return False

    def test_validate_xml_allows_trial(self):
        route = self._routes().get("/api/v1/validate/xml")
        assert route is not None
        slugs = self._allowed_slugs(route)
        assert slugs is not None and "trial" in slugs

    def test_validate_xml_has_usage_limit(self):
        route = self._routes().get("/api/v1/validate/xml")
        assert self._has_usage_check(route) is True

    def test_correct_xml_allows_trial(self):
        route = self._routes().get("/api/v1/validate/xml/correct")
        assert route is not None
        slugs = self._allowed_slugs(route)
        assert slugs is not None and "trial" in slugs

    def test_correct_xml_has_usage_limit(self):
        route = self._routes().get("/api/v1/validate/xml/correct")
        assert self._has_usage_check(route) is True

    def test_batch_cross_check_still_blocks_trial(self):
        # Batch is not advertised for Trial — must stay Profissional+
        route = self._routes().get("/api/v1/validate/batch-cross-check")
        assert route is not None
        slugs = self._allowed_slugs(route)
        assert slugs is not None and "trial" not in slugs

    def test_check_usage_limit_blocks_trial_at_quota(self):
        # At 5/5, Trial user must be rejected with 403
        from fastapi import HTTPException
        from app.api.plan_gate import check_usage_limit

        mock_plan = MagicMock(max_validations=5)
        mock_user = MagicMock(id="u1", tenant_id="t1")
        mock_usage = MagicMock(validations_used=5)

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_usage

        with patch("app.api.plan_gate._get_active_subscription", return_value=(MagicMock(), mock_plan)):
            dep = check_usage_limit("validations")
            with pytest.raises(HTTPException) as exc:
                dep(current_user=mock_user, db=mock_db)
            assert exc.value.status_code == 403
            assert "Limite mensal" in exc.value.detail

    def test_check_usage_limit_allows_trial_under_quota(self):
        from app.api.plan_gate import check_usage_limit

        mock_plan = MagicMock(max_validations=5)
        mock_user = MagicMock(id="u1", tenant_id="t1")
        mock_usage = MagicMock(validations_used=3)

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_usage

        with patch("app.api.plan_gate._get_active_subscription", return_value=(MagicMock(), mock_plan)):
            dep = check_usage_limit("validations")
            result = dep(current_user=mock_user, db=mock_db)
            assert result is mock_user


# ── PDF service tests ─────────────────────────────────────────────────────


class TestPdfService:
    """Test PDF service template rendering (HTML fallback when WeasyPrint not installed)."""

    def test_validation_report_renders(self):
        from app.services.pdf_service import generate_validation_report_pdf
        result = generate_validation_report_pdf(
            company_name="Empresa Teste",
            cnpj="12345678000199",
            reference_period="2026-03",
            job_id="test-job-001",
            findings=[
                {"severity": "ERROR", "rule_id": "CBS_RATE", "title": "Alíquota CBS incorreta"},
                {"severity": "WARNING", "rule_id": "IBS_RATE", "title": "Alíquota IBS divergente"},
            ],
            overall_status="NÃO CONFORME",
            total_base="10000.00",
            total_cbs="10.00",
            total_ibs="90.00",
        )
        data = result["bytes"]
        assert len(data) > 0
        if data[:5] == b"%PDF-":
            # WeasyPrint installed — just verify it produced a valid PDF
            assert len(data) > 100
        else:
            text = data.decode("utf-8")
            assert "Empresa Teste" in text
            assert "12345678000199" in text
            assert "CBS_RATE" in text

    def test_batch_report_renders(self):
        from app.services.pdf_service import generate_batch_report_pdf
        result = generate_batch_report_pdf(
            company_name="Empresa Lote",
            cnpj="98765432000111",
            reference_period="2026-03",
            job_id="test-batch-001",
            invoices=[
                {"invoice_number": "NF001", "status": "PASS", "base": "5000"},
                {"invoice_number": "NF002", "status": "FAIL", "base": "3000"},
            ],
            overall_status="NÃO CONFORME",
        )
        data = result["bytes"]
        assert len(data) > 0
        if data[:5] == b"%PDF-":
            assert len(data) > 100
        else:
            text = data.decode("utf-8")
            assert "Empresa Lote" in text
            assert "NF001" in text
            assert "NF002" in text

    def test_brl_filter(self):
        from app.services.pdf_service import _format_brl
        assert _format_brl("1234.56") == "R$ 1.234,56"
        assert _format_brl("0") == "R$ 0,00"
        assert _format_brl("49.90") == "R$ 49,90"

    def test_validation_report_no_findings(self):
        from app.services.pdf_service import generate_validation_report_pdf
        result = generate_validation_report_pdf(
            company_name="OK Corp",
            cnpj="11111111000100",
            reference_period="2026-01",
            job_id="test-clean",
            findings=[],
            overall_status="CONFORME",
        )
        data = result["bytes"]
        if data[:5] == b"%PDF-":
            assert len(data) > 100
        else:
            text = data.decode("utf-8")
            assert "CONFORME" in text
            assert "Nenhum finding" in text


# ── Jobs router PDF endpoint test ─────────────────────────────────────────


class TestJobsPdfEndpoint:
    """Verify the PDF report endpoint exists on the jobs router."""

    def test_report_pdf_route_exists(self):
        from app.routers.jobs import router
        paths = [getattr(r, "path", "") for r in router.routes]
        assert any("report.pdf" in p for p in paths)
