"""Tests for PDF report generation — S18."""

import hashlib
import importlib.metadata
import json
import uuid

from fastapi.testclient import TestClient

from app.main import app
from datetime import datetime, timezone

from app.services.pdf_service import (
    generate_validation_report_pdf,
    generate_batch_report_pdf,
    generate_credit_report_pdf,
    generate_prospect_diagnostic_pdf,
    _format_brasilia,
    _temporal_governance_stamp,
    _tzdata_version,
    TZDATA_VERSION,
    PLATFORM_TZ_LABEL,
)


client = TestClient(app)

JOB_ID = str(uuid.uuid4())
CNPJ = "11.222.333/0001-81"


def _all_registered_paths(routes) -> list[str]:
    """FastAPI >=0.139 envolve include_router() em _IncludedRouter (lazy) —
    o path só existe no original_router aninhado, não direto em app.routes."""
    paths = []
    for r in routes:
        path = getattr(r, "path", None)
        if path is not None:
            paths.append(path)
        elif hasattr(r, "original_router"):
            paths.extend(_all_registered_paths(r.original_router.routes))
    return paths


# ── Unit: pdf_service ──────────────────────────────────────────


class TestPdfServiceValidation:
    def _basic_pdf(self, **kwargs) -> dict:
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
        return generate_validation_report_pdf(**defaults)  # type: ignore[arg-type]

    def test_returns_bytes(self):
        result = self._basic_pdf()
        assert isinstance(result["bytes"], bytes)
        assert len(result["bytes"]) > 0

    def test_pdf_not_empty(self):
        result = self._basic_pdf()
        data = result["bytes"]
        # PDF magic bytes or HTML fallback
        assert data.startswith(b"%PDF") or data.startswith(b"<!DOCTYPE")

    def test_with_report_hash(self):
        result = self._basic_pdf(report_hash="abc123deadbeef")
        assert isinstance(result["bytes"], bytes)
        assert len(result["bytes"]) > 100

    def test_no_findings(self):
        result = self._basic_pdf(findings=[], overall_status="CONFORME")
        assert isinstance(result["bytes"], bytes)
        assert len(result["bytes"]) > 0

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


class TestPdfServiceTimezone:
    """#419 — laudo PDF apresenta horário de Brasília, não UTC.

    Storage continua UTC aware (datetime.now(timezone.utc)) — só a borda de
    apresentação converte, conforme knowledge/engineering/tempo-e-auditoria.md.
    """

    def test_utc_instant_converts_to_sao_paulo_deterministically(self):
        # 2026-06-15 12:00 UTC -> horário de verão não se aplica no Brasil
        # desde 2019; America/Sao_Paulo é UTC-3 o ano inteiro -> 09:00.
        instant = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        assert _format_brasilia(instant) == "15/06/2026 09:00 horário de Brasília"

    def test_label_says_brasilia_not_utc(self):
        instant = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        result = _format_brasilia(instant)
        assert "horário de Brasília" in result
        assert "UTC" not in result

    def test_date_rolls_back_across_midnight_boundary(self):
        # 2026-03-01 02:00 UTC -> 2026-02-28 23:00 em São Paulo (UTC-3):
        # o dia muda, não só a hora — é exatamente o bug que o laudo tinha.
        instant = datetime(2026, 3, 1, 2, 0, tzinfo=timezone.utc)
        assert _format_brasilia(instant) == "28/02/2026 23:00 horário de Brasília"

    def test_validation_pdf_report_shows_brasilia_label(self):
        result = generate_validation_report_pdf(
            company_name="Empresa Teste LTDA",
            cnpj=CNPJ,
            reference_period="2026-03",
            job_id=JOB_ID,
            findings=[],
            overall_status="CONFORME",
        )
        # HTML fallback (sem WeasyPrint) ou PDF real — ambos carregam o texto
        # gerado pelo template; se for HTML puro dá pra inspecionar direto.
        data = result["bytes"]
        if data.startswith(b"<!DOCTYPE"):
            assert "horário de Brasília".encode("utf-8") in data
            assert b"UTC" not in data


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
        assert isinstance(result["bytes"], bytes)
        assert len(result["bytes"]) > 0

    def test_empty_invoices(self):
        result = generate_batch_report_pdf(
            company_name="Empresa X",
            cnpj=CNPJ,
            reference_period="2026-03",
            job_id=JOB_ID,
            invoices=[],
            overall_status="CONFORME",
        )
        assert isinstance(result["bytes"], bytes)


class TestTemporalGovernanceStamp:
    """#606 — carimbo duplo (UTC+IANA+tzdata) + quadro "Governança Temporal".

    Formato exato: knowledge/engineering/tempo-e-auditoria.md (RF-3, Brain).
    """

    def test_stamp_fields_are_all_present(self):
        instant = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stamp = _temporal_governance_stamp(instant)
        assert stamp["emitted_at_utc"] == "2026-06-15T12:00:00Z"
        assert stamp["emitted_tz"] == "America/Sao_Paulo"
        assert stamp["emitted_local"] == "15/06/2026 09:00:00"
        assert stamp["tzdata_version"] == TZDATA_VERSION

    def test_platform_tz_label_uses_canonical_format(self):
        """Formato único: "Area/Localidade (UTC±hh:mm)", sem abreviação."""
        assert PLATFORM_TZ_LABEL == "America/Sao_Paulo (UTC\u221203:00)"

    def test_emitted_local_line_pairs_local_time_with_platform_label(self):
        instant = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        stamp = _temporal_governance_stamp(instant)
        assert stamp["emitted_local_line"] == f"31/12/2025 21:00:00 \u00b7 {PLATFORM_TZ_LABEL}"

    def test_emitted_utc_line_carries_tzdata_version(self):
        instant = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        stamp = _temporal_governance_stamp(instant)
        assert stamp["emitted_utc_line"] == f"2026-01-01T00:00:00Z \u00b7 tzdata {TZDATA_VERSION}"

    def test_date_rolls_across_midnight_boundary(self):
        """Mesma armadilha do #419 — instante UTC pode virar o dia anterior em BRT."""
        instant = datetime(2026, 3, 1, 2, 0, 0, tzinfo=timezone.utc)
        stamp = _temporal_governance_stamp(instant)
        assert stamp["emitted_local"] == "28/02/2026 23:00:00"

    def test_tzdata_version_reads_installed_pypi_package(self):
        """Fonte única (RNF-1): importlib.metadata, não o tzdata do SO."""
        assert _tzdata_version() == importlib.metadata.version("tzdata")
        assert TZDATA_VERSION == _tzdata_version()

    def test_tzdata_version_falls_back_when_package_missing(self, monkeypatch):
        def _raise(_name: str) -> str:
            raise importlib.metadata.PackageNotFoundError

        monkeypatch.setattr(importlib.metadata, "version", _raise)
        assert _tzdata_version() == "desconhecida"


class TestTemporalGovernanceInPdfArtifacts:
    """O carimbo deve aparecer no HTML/PDF real de cada um dos 4 tipos de laudo,
    e o dict de retorno de cada função deve carregar os campos de evidência."""

    def _assert_stamp_in_html_fallback(self, data: bytes) -> None:
        if not data.startswith(b"<!DOCTYPE"):
            return  # PDF binário real — checagem de string não aplica
        assert "Governança Temporal".encode("utf-8") in data
        assert "tzdata".encode("utf-8") in data
        assert PLATFORM_TZ_LABEL.encode("utf-8") in data

    def test_validation_pdf_carries_stamp(self):
        result = generate_validation_report_pdf(
            company_name="Empresa Teste LTDA", cnpj=CNPJ,
            reference_period="2026-03", job_id=JOB_ID,
            findings=[], overall_status="CONFORME",
        )
        assert {"emitted_at_utc", "emitted_tz", "emitted_local", "tzdata_version"} <= result.keys()
        self._assert_stamp_in_html_fallback(result["bytes"])

    def test_batch_pdf_carries_stamp(self):
        result = generate_batch_report_pdf(
            company_name="Empresa Teste LTDA", cnpj=CNPJ,
            reference_period="2026-03", job_id=JOB_ID,
            invoices=[], overall_status="CONFORME",
        )
        assert {"emitted_at_utc", "emitted_tz", "emitted_local", "tzdata_version"} <= result.keys()
        self._assert_stamp_in_html_fallback(result["bytes"])

    def test_credit_pdf_carries_stamp(self):
        result = generate_credit_report_pdf(
            company_name="Empresa Teste LTDA", cnpj=CNPJ,
            period_type="month", periods=[],
        )
        assert {"emitted_at_utc", "emitted_tz", "emitted_local", "tzdata_version"} <= result.keys()
        self._assert_stamp_in_html_fallback(result["bytes"])

    def test_prospect_diagnostic_pdf_carries_stamp(self):
        result = generate_prospect_diagnostic_pdf(
            office_name="Escritório Teste", invoices=[],
            trial_url="https://tribultz.com.br/trial",
        )
        assert {"emitted_at_utc", "emitted_tz", "emitted_local", "tzdata_version"} <= result.keys()
        self._assert_stamp_in_html_fallback(result["bytes"])


# ── Router registration (no-DB check) ──────────────────────────


class TestReportsRouterRegistered:
    """Verify the reports router is registered — checks app routes list directly."""

    def test_pdf_validation_route_in_app(self):
        routes = _all_registered_paths(app.routes)
        assert "/api/v1/reports/pdf/validation" in routes

    def test_pdf_batch_route_in_app(self):
        routes = _all_registered_paths(app.routes)
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
