"""Tests for ParseNFSeXMLTool and ValidateFiscalRulesTool."""
import json
from unittest.mock import patch

from app.crews.tools.parse_nfse_xml_tool import ParseNFSeXMLTool
from app.crews.tools.validate_fiscal_rules_tool import ValidateFiscalRulesTool

# ── Fixtures ──────────────────────────────────────────────────────────────────

VALID_NFSE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<NFS-e>
  <infNfse>
    <CST>400</CST>
    <cClassTrib>654321</cClassTrib>
    <CodigoServico>123456</CodigoServico>
    <NCM>12345678</NCM>
  </infNfse>
</NFS-e>"""

INVALID_NFSE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<NFS-e>
  <infNfse>
    <CST>12</CST>
    <cClassTrib>65432</cClassTrib>
    <CodigoServico>1234</CodigoServico>
  </infNfse>
</NFS-e>"""

MALFORMED_XML = "<NFS-e><unclosed>"

TENANT_ID = "00000000-0000-0000-0000-000000000001"


# ── ParseNFSeXMLTool ──────────────────────────────────────────────────────────

class TestParseNFSeXMLTool:
    def _tool(self) -> ParseNFSeXMLTool:
        return ParseNFSeXMLTool(tenant_id=TENANT_ID)

    @patch("app.crews.tools.parse_nfse_xml_tool.put_object")
    def test_extracts_valid_fields(self, mock_s3):
        mock_s3.return_value = {"key": "k"}
        result = json.loads(self._tool()._run(VALID_NFSE_XML))
        assert result["parse_error"] is None
        assert result["fields"]["cst"] == "400"
        assert result["fields"]["cclasstrib"] == "654321"
        assert result["fields"]["codigo_servico"] == "123456"
        assert result["fields"]["ncm"] == "12345678"
        assert "invoice_id" in result

    @patch("app.crews.tools.parse_nfse_xml_tool.put_object")
    def test_extracts_invalid_fields(self, mock_s3):
        mock_s3.return_value = {"key": "k"}
        result = json.loads(self._tool()._run(INVALID_NFSE_XML))
        assert result["parse_error"] is None
        assert result["fields"]["cst"] == "12"
        assert result["fields"]["cclasstrib"] == "65432"

    @patch("app.crews.tools.parse_nfse_xml_tool.put_object")
    def test_malformed_xml_sets_parse_error(self, mock_s3):
        mock_s3.return_value = {"key": "k"}
        result = json.loads(self._tool()._run(MALFORMED_XML))
        assert result["parse_error"] is not None
        assert result["fields"]["cst"] == ""

    @patch("app.crews.tools.parse_nfse_xml_tool.put_object", side_effect=Exception("s3 down"))
    def test_s3_failure_does_not_raise(self, mock_s3):
        result = json.loads(self._tool()._run(VALID_NFSE_XML))
        assert "s3-unavailable" in result["s3_key"]
        assert result["fields"]["cst"] == "400"


# ── ValidateFiscalRulesTool ───────────────────────────────────────────────────

class TestValidateFiscalRulesTool:
    def _tool(self) -> ValidateFiscalRulesTool:
        return ValidateFiscalRulesTool()

    def _fields_json(self, **overrides) -> str:
        base = {
            "cst": "400",
            "cclasstrib": "654321",
            "codigo_servico": "123456",
            "ncm": "12345678",
            "parse_error": None,
        }
        base.update(overrides)
        return json.dumps(base)

    def test_all_valid_no_findings(self):
        result = json.loads(self._tool()._run("inv-1", self._fields_json()))
        assert result["findings"] == []

    def test_cst_too_short_is_fatal(self):
        result = json.loads(self._tool()._run("inv-1", self._fields_json(cst="12")))
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "CST_3_DIGITS" in rule_ids
        fatal = next(f for f in result["findings"] if f["rule_id"] == "CST_3_DIGITS")
        assert fatal["severity"] == "FATAL"

    def test_cclasstrib_too_short_is_fatal(self):
        result = json.loads(self._tool()._run("inv-1", self._fields_json(cclasstrib="65432")))
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "CCLASSTRIB_6_DIGITS" in rule_ids

    def test_codigo_servico_too_short_is_fatal(self):
        result = json.loads(self._tool()._run("inv-1", self._fields_json(codigo_servico="1234")))
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "SERVICE_CODE_6_DIGITS" in rule_ids

    def test_missing_ncm_is_alert(self):
        result = json.loads(self._tool()._run("inv-1", self._fields_json(ncm="")))
        finding = next(f for f in result["findings"] if f["rule_id"] == "NCM_PLACEHOLDER")
        assert finding["severity"] == "ALERT"

    def test_parse_error_is_fatal(self):
        result = json.loads(self._tool()._run("inv-1", self._fields_json(parse_error="syntax error at line 1")))
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "XML_PARSE" in rule_ids
        xml_finding = next(f for f in result["findings"] if f["rule_id"] == "XML_PARSE")
        assert xml_finding["severity"] == "FATAL"

    def test_finding_has_required_keys(self):
        result = json.loads(self._tool()._run("inv-1", self._fields_json(cst="12")))
        f = result["findings"][0]
        for key in ("rule_id", "severity", "field", "xpath", "snippet", "recommendation"):
            assert key in f, f"Missing key: {key}"
