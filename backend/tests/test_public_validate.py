"""Tests for public validation endpoint — freemium diagnostic funnel."""

import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.routers.public import _to_public_result, _client_ip, _rate_limiter
from app.routers.validate_xml import validate_xml


@pytest.fixture(autouse=True)
def reset_public_rate_limiter():
    """Clear rate limiter state between tests to avoid 429s in CI (double pytest run)."""
    _rate_limiter._memory_store.clear()
    if _rate_limiter.redis is not None:
        try:
            _rate_limiter.redis.delete("ratelimit:public:testclient")
            _rate_limiter.redis.delete("ratelimit:public:127.0.0.1")
            _rate_limiter.redis.delete("ratelimit:public:unknown")
        except Exception:
            pass
    yield
    _rate_limiter._memory_store.clear()

# ── Sample XMLs ────────────────────────────────────────────────────────────────

VALID_NFE_XML = """<?xml version="1.0"?>
<nfeProc>
  <NFe>
    <infNFe>
      <emit><CNPJ>12345678000195</CNPJ></emit>
      <det nItem="1">
        <prod>
          <NCM>84713012</NCM>
          <CEST>2106300</CEST>
          <CFOP>5102</CFOP>
        </prod>
        <imposto>
          <IBSCBS>
            <CST>000</CST>
            <cClassTrib>100001</cClassTrib>
            <gIBSCBS>
              <vBC>1000.00</vBC>
              <pCBS>0.0010</pCBS>
              <vCBS>1.00</vCBS>
              <pIBSUF>0.0050</pIBSUF>
              <vIBSUF>5.00</vIBSUF>
              <pIBSMun>0.0040</pIBSMun>
              <vIBSMun>4.00</vIBSMun>
              <vIBS>9.00</vIBS>
            </gIBSCBS>
          </IBSCBS>
        </imposto>
      </det>
      <total>
        <IBSCBSTot>
          <vCBS>1.00</vCBS>
          <vIBS>9.00</vIBS>
        </IBSCBSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>
"""

INVALID_NFE_XML_MISSING_CST = """<?xml version="1.0"?>
<nfeProc>
  <NFe>
    <infNFe>
      <emit><CNPJ>12345678000195</CNPJ></emit>
      <det nItem="1">
        <prod><NCM>84713012</NCM><CEST>2106300</CEST></prod>
        <imposto>
          <IBSCBS>
            <CST>999</CST>
            <cClassTrib>100001</cClassTrib>
          </IBSCBS>
        </imposto>
      </det>
      <total></total>
    </infNFe>
  </NFe>
</nfeProc>
"""

MINIMAL_NFSE_XML = """<?xml version="1.0"?>
<NFS-e>
  <infNfse>
    <Valores>
      <BaseCalculo>1000.00</BaseCalculo>
      <AliquotaCBS>0.10</AliquotaCBS>
      <ValorCBS>100.00</ValorCBS>
      <AliquotaIBS>0.90</AliquotaIBS>
      <ValorIBS>900.00</ValorIBS>
    </Valores>
    <PrestadorServico><CNPJ>12345678000195</CNPJ></PrestadorServico>
    <TomadorServico><CNPJ>98765432000100</CNPJ></TomadorServico>
    <CodigoServico>140101</CodigoServico>
  </infNfse>
</NFS-e>
"""


# ── Unit tests ─────────────────────────────────────────────────────────────────


# ── Unit tests: validation engine (no HTTP) ────────────────────────────────────

class TestPublicResultConversion:
    def test_valid_nfe_returns_pass(self):
        result = validate_xml(VALID_NFE_XML)
        public = _to_public_result(result)
        assert public.document_type == "NFE"
        assert public.status == "PASS"
        assert public.fatals == 0
        assert public.rules_checked == 14
        assert "conta gratuita" in public.upgrade_cta

    def test_invalid_nfe_returns_fail_with_findings(self):
        result = validate_xml(INVALID_NFE_XML_MISSING_CST)
        public = _to_public_result(result)
        assert public.status == "FAIL"
        assert public.fatals > 0
        assert public.total_findings > 0
        # Findings should have rule_id but no detailed evidence
        for f in public.findings:
            assert f.rule_id
            assert f.severity in ("FATAL", "ALERT")
            assert f.title

    def test_nfse_detection(self):
        result = validate_xml(MINIMAL_NFSE_XML)
        public = _to_public_result(result)
        assert public.document_type == "NFSE"

    def test_empty_xml_findings(self):
        result = validate_xml("<root></root>")
        public = _to_public_result(result)
        assert public.status == "FAIL"
        assert public.total_findings > 0

    def test_public_result_has_no_evidence_details(self):
        """Ensure the public result doesn't leak xpath/snippet/recommendation."""
        result = validate_xml(INVALID_NFE_XML_MISSING_CST)
        public = _to_public_result(result)
        data = public.model_dump()
        for f in data["findings"]:
            assert "xpath" not in f
            assert "snippet" not in f
            assert "recommendation" not in f
            assert "evidence_ids" not in f


class TestClientIpExtraction:
    def test_forwarded_header(self):
        mock_req = MagicMock()
        mock_req.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
        mock_req.client.host = "127.0.0.1"
        assert _client_ip(mock_req) == "1.2.3.4"

    def test_direct_connection(self):
        mock_req = MagicMock()
        mock_req.headers = {}
        mock_req.client.host = "10.0.0.1"
        assert _client_ip(mock_req) == "10.0.0.1"

    def test_no_client(self):
        mock_req = MagicMock()
        mock_req.headers = {}
        mock_req.client = None
        assert _client_ip(mock_req) == "unknown"


# ── Integration tests with FastAPI TestClient ──────────────────────────────────

client = TestClient(app)


class TestPublicValidateEndpoint:
    def test_post_xml_content_returns_result(self):
        resp = client.post(
            "/api/v1/public/validate",
            data={"xml_content": VALID_NFE_XML},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "NFE"
        assert data["status"] in ("PASS", "FAIL")
        assert "upgrade_cta" in data
        assert data["rules_checked"] == 14

    def test_post_file_upload(self):
        resp = client.post(
            "/api/v1/public/validate",
            files={"file": ("test.xml", VALID_NFE_XML.encode(), "application/xml")},
        )
        assert resp.status_code == 200
        assert resp.json()["document_type"] == "NFE"

    def test_post_invalid_xml_returns_findings(self):
        resp = client.post(
            "/api/v1/public/validate",
            data={"xml_content": INVALID_NFE_XML_MISSING_CST},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "FAIL"
        assert data["fatals"] > 0
        assert len(data["findings"]) > 0

    def test_post_empty_body_returns_400(self):
        resp = client.post("/api/v1/public/validate")
        assert resp.status_code in (400, 422)

    def test_post_empty_xml_returns_400(self):
        resp = client.post(
            "/api/v1/public/validate",
            data={"xml_content": ""},
        )
        assert resp.status_code == 400

    def test_public_health(self):
        resp = client.get("/api/v1/public/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_nfse_xml_via_public(self):
        resp = client.post(
            "/api/v1/public/validate",
            data={"xml_content": MINIMAL_NFSE_XML},
        )
        assert resp.status_code == 200
        assert resp.json()["document_type"] == "NFSE"

    @patch("app.routers.public._rate_limiter")
    def test_rate_limit_returns_429(self, mock_limiter):
        from fastapi import HTTPException
        mock_limiter.check_or_raise.side_effect = HTTPException(
            status_code=429, detail="Limite excedido"
        )
        resp = client.post(
            "/api/v1/public/validate",
            data={"xml_content": VALID_NFE_XML},
        )
        assert resp.status_code == 429
