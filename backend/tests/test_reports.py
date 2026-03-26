"""Tests for PDF report generation — S18."""

import hashlib
import json
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.pdf_service import generate_validation_report_pdf, generate_batch_report_pdf


client = TestClient(app)

JOB_ID = str(uuid.uuid4())
CNPJ = "11.222.333/0001-81"


# ── Unit: pdf_service ──────────────────────────────────────────


class TestPdfServiceValidation:
    def _basic_pdf(self, **kwargs) -> bytes:
        defaults = dict(
            company_name="Empresa Teste LTDA",
            cnpj=CNPJ,
            reference_period="2026-03",
            job_id=JOB_ID,
            findings=[
                {
                    "rule_id": "CBS_001",
                    "severity": "ERROR",
                    "title": "CBS não calculado",
                    "where": "tag <CBS>",
                    "recommendation": "Incluir CBS no XML",
                }
            ],
            overall_status="NÃO CONFORME",
            total_base="10000.00",
            total_cbs="10.00",
            total_ibs="90.00",
        )
        defaults.update(kwargs)
        return generate_validation_report_pdf(**defaults)

    def test_returns_bytes(self):
        result = self._basic_pdf()
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_pdf_not_empty(self):
        result = self._basic_pdf()
        # PDF magic bytes or HTML fallback
        assert result.startswith(b"%PDF") or result.startswith(b"<!DOCTYPE")

    def test_with_report_hash(self):
        result = self._basic_pdf(report_hash="abc123deadbeef")
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_no_findings(self):
        result = self._basic_pdf(findings=[], overall_status="CONFORME")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_hash_is_deterministic(self):
        """Same inputs → same hash."""
        payload = {
            "job_id": JOB_ID,
            "cnpj": CNPJ,
            "reference_period": "2026-03",
            "overall_status": "CONFORME",
            "total_cbs": "10.00",
            "total_ibs": "90.00",
            "findings": [],
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        h1 = hashlib.sha256(canonical.encode()).hexdigest()
        h2 = hashlib.sha256(canonical.encode()).hexdigest()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex length


class TestPdfServiceBatch:
    def test_batch_pdf_returns_bytes(self):
        result = generate_batch_report_pdf(
            company_name="Escritório Contábil LTDA",
            cnpj=CNPJ,
            reference_period="2026-03",
            job_id=JOB_ID,
            invoices=[
                {
                    "nf_number": "001",
                    "cnpj_emitente": CNPJ,
                    "valor_total": "5000.00",
                    "status": "PASS",
                    "findings_count": 0,
                },
                {
                    "nf_number": "002",
                    "cnpj_emitente": CNPJ,
                    "valor_total": "3000.00",
                    "status": "FAIL",
                    "findings_count": 2,
                },
            ],
            overall_status="PARCIAL",
            report_hash="deadbeef1234",
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_empty_invoices(self):
        result = generate_batch_report_pdf(
            company_name="Empresa X",
            cnpj=CNPJ,
            reference_period="2026-03",
            job_id=JOB_ID,
            invoices=[],
            overall_status="CONFORME",
        )
        assert isinstance(result, bytes)


# ── Router registration (no-DB check) ──────────────────────────


class TestReportsRouterRegistered:
    """Verify the reports router is registered — checks app routes list directly."""

    def test_pdf_validation_route_in_app(self):
        routes = [r.path for r in app.routes]  # type: ignore[attr-defined]
        assert "/api/v1/reports/pdf/validation" in routes

    def test_pdf_batch_route_in_app(self):
        routes = [r.path for r in app.routes]  # type: ignore[attr-defined]
        assert "/api/v1/reports/pdf/batch" in routes


class TestReportsHashIntegrity:
    def test_hash_length_is_64(self):
        """SHA-256 hex digest must be 64 chars."""
        payload = {"job_id": JOB_ID, "cnpj": CNPJ, "ref": "2026-03"}
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        h = hashlib.sha256(canonical.encode()).hexdigest()
        assert len(h) == 64

    def test_different_payloads_produce_different_hashes(self):
        p1 = json.dumps({"job_id": "aaa"}, sort_keys=True)
        p2 = json.dumps({"job_id": "bbb"}, sort_keys=True)
        h1 = hashlib.sha256(p1.encode()).hexdigest()
        h2 = hashlib.sha256(p2.encode()).hexdigest()
        assert h1 != h2

    def test_sort_keys_canonical_is_stable(self):
        """Dict with different key order → same hash."""
        p1 = json.dumps({"b": 2, "a": 1}, sort_keys=True)
        p2 = json.dumps({"a": 1, "b": 2}, sort_keys=True)
        assert hashlib.sha256(p1.encode()).hexdigest() == hashlib.sha256(p2.encode()).hexdigest()
