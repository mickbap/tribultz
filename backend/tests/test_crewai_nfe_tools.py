"""Tests for CrewAI NF-e/NFC-e tools (ParseNFeXMLTool + ValidateIBSCBSRulesTool).

These tests validate the tools directly (no LLM needed), following the same
pattern as existing tool tests: call _run() and assert JSON output.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from app.crews.tools.parse_nfe_xml_tool import CST_TABLE, ParseNFeXMLTool
from app.crews.tools.validate_ibscbs_rules_tool import ValidateIBSCBSRulesTool

# ── Test fixtures ──────────────────────────────────────────────

NFE_OK_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe versao="4.00" Id="NFe35260312345678000195550010000001231234567890">
      <ide><mod>55</mod></ide>
      <emit><CNPJ>12345678000195</CNPJ></emit>
      <det nItem="1">
        <prod>
          <NCM>84713012</NCM>
          <CEST>2104900</CEST>
        </prod>
        <imposto>
          <ICMS><ICMS00><CST>00</CST></ICMS00></ICMS>
          <IBSCBS>
            <CST>000</CST>
            <cClassTrib>654321</cClassTrib>
            <gIBSCBS>
              <vBC>1000.00</vBC>
              <gIBSUF><pIBSUF>0.0005</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
              <gIBSMun><pIBSMun>0.0005</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
              <vIBS>1.00</vIBS>
              <gCBS><pCBS>0.0090</pCBS><vCBS>9.00</vCBS></gCBS>
            </gIBSCBS>
          </IBSCBS>
        </imposto>
      </det>
      <total>
        <IBSCBSTot>
          <vCBS>9.00</vCBS>
          <vIBS>1.00</vIBS>
        </IBSCBSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>"""

NFCE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00">
  <NFe>
    <infNFe versao="4.00">
      <ide><mod>65</mod></ide>
      <emit><CNPJ>12345678000195</CNPJ></emit>
      <det nItem="1">
        <prod><NCM>22021000</NCM><CEST>0300100</CEST></prod>
        <imposto>
          <IBSCBS>
            <CST>000</CST>
            <cClassTrib>123456</cClassTrib>
            <gIBSCBS>
              <vBC>50.00</vBC>
              <gIBSUF><pIBSUF>0.0005</pIBSUF><vIBSUF>0.03</vIBSUF></gIBSUF>
              <gIBSMun><pIBSMun>0.0005</pIBSMun><vIBSMun>0.03</vIBSMun></gIBSMun>
              <vIBS>0.05</vIBS>
              <gCBS><pCBS>0.0090</pCBS><vCBS>0.45</vCBS></gCBS>
            </gIBSCBS>
          </IBSCBS>
        </imposto>
      </det>
      <total>
        <IBSCBSTot><vCBS>0.45</vCBS><vIBS>0.05</vIBS></IBSCBSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>"""

NFE_SPLIT_ERROR_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00">
  <NFe>
    <infNFe versao="4.00">
      <ide><mod>55</mod></ide>
      <emit><CNPJ>12345678000195</CNPJ></emit>
      <det nItem="1">
        <prod><NCM>84713012</NCM><CEST>2104900</CEST></prod>
        <imposto>
          <IBSCBS>
            <CST>000</CST>
            <cClassTrib>654321</cClassTrib>
            <gIBSCBS>
              <vBC>1000.00</vBC>
              <gIBSUF><pIBSUF>0.0005</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
              <gIBSMun><pIBSMun>0.0005</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
              <vIBS>1.50</vIBS>
              <gCBS><pCBS>0.0090</pCBS><vCBS>9.00</vCBS></gCBS>
            </gIBSCBS>
          </IBSCBS>
        </imposto>
      </det>
      <total>
        <IBSCBSTot><vCBS>9.00</vCBS><vIBS>1.50</vIBS></IBSCBSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>"""

NFE_INVALID_CST_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00">
  <NFe>
    <infNFe versao="4.00">
      <ide><mod>55</mod></ide>
      <emit><CNPJ>12345678000195</CNPJ></emit>
      <det nItem="1">
        <prod><NCM>84713012</NCM><CEST>2104900</CEST></prod>
        <imposto>
          <IBSCBS>
            <CST>999</CST>
            <cClassTrib>654321</cClassTrib>
            <gIBSCBS>
              <vBC>1000.00</vBC>
              <gIBSUF><pIBSUF>0.0005</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
              <gIBSMun><pIBSMun>0.0005</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
              <vIBS>1.00</vIBS>
              <gCBS><pCBS>0.0090</pCBS><vCBS>9.00</vCBS></gCBS>
            </gIBSCBS>
          </IBSCBS>
        </imposto>
      </det>
      <total>
        <IBSCBSTot><vCBS>9.00</vCBS><vIBS>1.00</vIBS></IBSCBSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>"""


# ── CST_TABLE tests ────────────────────────────────────────────


def test_cst_table_has_14_entries():
    assert len(CST_TABLE) == 14


def test_cst_table_keys_are_3_digit_strings():
    for code in CST_TABLE:
        assert len(code) == 3
        assert code.isdigit()


# ── ParseNFeXMLTool tests ─────────────────────────────────────


@patch("app.crews.tools.parse_nfe_xml_tool.put_object")
def test_parse_nfe_ok(mock_s3):
    tool = ParseNFeXMLTool(tenant_id="t-test-001")
    result = json.loads(tool._run(NFE_OK_XML))

    assert result["parse_error"] is None
    assert result["doc_type"] == "NFE"
    assert result["fields"]["cst"] == "000"
    assert result["fields"]["cclasstrib"] == "654321"
    assert result["fields"]["vbc"] == "1000.00"
    assert result["fields"]["pcbs"] == "0.0090"
    assert result["fields"]["vcbs"] == "9.00"
    assert result["fields"]["pibsuf"] == "0.0005"
    assert result["fields"]["vibsuf"] == "0.50"
    assert result["fields"]["pibsmun"] == "0.0005"
    assert result["fields"]["vibsmun"] == "0.50"
    assert result["fields"]["vibs"] == "1.00"
    assert len(result["items"]) == 1


@patch("app.crews.tools.parse_nfe_xml_tool.put_object")
def test_parse_nfce_detects_mod_65(mock_s3):
    tool = ParseNFeXMLTool(tenant_id="t-test-001")
    result = json.loads(tool._run(NFCE_XML))
    assert result["doc_type"] == "NFCE"
    assert result["fields"]["cst"] == "000"


@patch("app.crews.tools.parse_nfe_xml_tool.put_object")
def test_parse_nfe_extracts_ibscbs_cst_not_icms(mock_s3):
    """CST must come from IBSCBS (3 digits), not ICMS (2 digits)."""
    tool = ParseNFeXMLTool(tenant_id="t-test-001")
    result = json.loads(tool._run(NFE_OK_XML))
    assert result["fields"]["cst"] == "000"  # not "00" from ICMS


@patch("app.crews.tools.parse_nfe_xml_tool.put_object")
def test_parse_nfe_totals(mock_s3):
    tool = ParseNFeXMLTool(tenant_id="t-test-001")
    result = json.loads(tool._run(NFE_OK_XML))
    assert result["fields"]["tot_vcbs"] == "9.00"
    assert result["fields"]["tot_vibs"] == "1.00"


@patch("app.crews.tools.parse_nfe_xml_tool.put_object")
def test_parse_nfe_layout_tags(mock_s3):
    tool = ParseNFeXMLTool(tenant_id="t-test-001")
    result = json.loads(tool._run(NFE_OK_XML))
    tags = result["fields"]["layout_tags"]
    assert "emit" in tags
    assert "det" in tags
    assert "total" in tags
    assert "IBSCBS" in tags
    assert "IBSCBSTot" in tags


@patch("app.crews.tools.parse_nfe_xml_tool.put_object")
def test_parse_nfe_s3_soft_fail(mock_s3):
    """S3 failure should not break parsing."""
    mock_s3.side_effect = ConnectionError("minio down")
    tool = ParseNFeXMLTool(tenant_id="t-test-001")
    result = json.loads(tool._run(NFE_OK_XML))
    assert result["parse_error"] is None
    assert "s3-unavailable" in result["s3_key"]


@patch("app.crews.tools.parse_nfe_xml_tool.put_object")
def test_parse_nfe_invalid_xml(mock_s3):
    tool = ParseNFeXMLTool(tenant_id="t-test-001")
    result = json.loads(tool._run("<broken>xml"))
    assert result["parse_error"] is not None


# ── ValidateIBSCBSRulesTool tests ─────────────────────────────


def _parse_and_validate(xml: str) -> dict:
    """Helper: parse XML then validate — returns validation result."""
    with patch("app.crews.tools.parse_nfe_xml_tool.put_object"):
        parser = ParseNFeXMLTool(tenant_id="t-test-001")
        parsed = json.loads(parser._run(xml))

    validator = ValidateIBSCBSRulesTool()
    return json.loads(validator._run(
        invoice_id=parsed["invoice_id"],
        fields_json=json.dumps(parsed),
    ))


def test_validate_nfe_ok_no_fatals():
    result = _parse_and_validate(NFE_OK_XML)
    fatals = [f for f in result["findings"] if f["severity"] == "FATAL"]
    assert len(fatals) == 0
    assert result["summary"]["status"] == "PASS"


def test_validate_nfce_ok():
    result = _parse_and_validate(NFCE_XML)
    fatals = [f for f in result["findings"] if f["severity"] == "FATAL"]
    assert len(fatals) == 0


def test_validate_ibs_split_error():
    result = _parse_and_validate(NFE_SPLIT_ERROR_XML)
    rule_ids = [f["rule_id"] for f in result["findings"]]
    assert "IBSCBS_SPLIT" in rule_ids
    assert result["summary"]["status"] == "FAIL"


def test_validate_invalid_cst():
    result = _parse_and_validate(NFE_INVALID_CST_XML)
    rule_ids = [f["rule_id"] for f in result["findings"]]
    assert "CST_VALID" in rule_ids


def test_validate_missing_ibscbs():
    """XML without IBSCBS group should trigger IBSCBS_MISSING."""
    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00">
  <NFe>
    <infNFe versao="4.00">
      <ide><mod>55</mod></ide>
      <emit><CNPJ>12345678000195</CNPJ></emit>
      <det nItem="1">
        <prod><NCM>84713012</NCM><CEST>2104900</CEST></prod>
        <imposto></imposto>
      </det>
      <total></total>
    </infNFe>
  </NFe>
</nfeProc>"""
    result = _parse_and_validate(xml)
    rule_ids = [f["rule_id"] for f in result["findings"]]
    assert "IBSCBS_MISSING" in rule_ids


def test_validate_cst_semantic_070():
    """CST 070 (imunidade) with vCBS > 0 should trigger CST_SEMANTIC."""
    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00">
  <NFe>
    <infNFe versao="4.00">
      <ide><mod>55</mod></ide>
      <emit><CNPJ>12345678000195</CNPJ></emit>
      <det nItem="1">
        <prod><NCM>84713012</NCM><CEST>2104900</CEST></prod>
        <imposto>
          <IBSCBS>
            <CST>070</CST>
            <cClassTrib>654321</cClassTrib>
            <gIBSCBS>
              <vBC>1000.00</vBC>
              <gIBSUF><pIBSUF>0.0005</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
              <gIBSMun><pIBSMun>0.0005</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
              <vIBS>1.00</vIBS>
              <gCBS><pCBS>0.0090</pCBS><vCBS>9.00</vCBS></gCBS>
            </gIBSCBS>
          </IBSCBS>
        </imposto>
      </det>
      <total><IBSCBSTot><vCBS>9.00</vCBS><vIBS>1.00</vIBS></IBSCBSTot></total>
    </infNFe>
  </NFe>
</nfeProc>"""
    result = _parse_and_validate(xml)
    rule_ids = [f["rule_id"] for f in result["findings"]]
    assert "CST_SEMANTIC" in rule_ids


def test_validate_cbs_calc_error():
    """vCBS wrong calculation should trigger IBSCBS_CALC."""
    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00">
  <NFe>
    <infNFe versao="4.00">
      <ide><mod>55</mod></ide>
      <emit><CNPJ>12345678000195</CNPJ></emit>
      <det nItem="1">
        <prod><NCM>84713012</NCM><CEST>2104900</CEST></prod>
        <imposto>
          <IBSCBS>
            <CST>000</CST>
            <cClassTrib>654321</cClassTrib>
            <gIBSCBS>
              <vBC>1000.00</vBC>
              <gIBSUF><pIBSUF>0.0005</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
              <gIBSMun><pIBSMun>0.0005</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
              <vIBS>1.00</vIBS>
              <gCBS><pCBS>0.0090</pCBS><vCBS>99.99</vCBS></gCBS>
            </gIBSCBS>
          </IBSCBS>
        </imposto>
      </det>
      <total><IBSCBSTot><vCBS>99.99</vCBS><vIBS>1.00</vIBS></IBSCBSTot></total>
    </infNFe>
  </NFe>
</nfeProc>"""
    result = _parse_and_validate(xml)
    rule_ids = [f["rule_id"] for f in result["findings"]]
    assert "IBSCBS_CALC" in rule_ids


def test_validate_layout_nfe_missing_emit():
    """Missing emit tag should trigger LAYOUT_NFE."""
    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00">
  <NFe>
    <infNFe versao="4.00">
      <ide><mod>55</mod></ide>
      <det nItem="1">
        <prod><NCM>84713012</NCM><CEST>2104900</CEST></prod>
        <imposto>
          <IBSCBS>
            <CST>000</CST>
            <cClassTrib>654321</cClassTrib>
            <gIBSCBS>
              <vBC>1000.00</vBC>
              <gIBSUF><pIBSUF>0.0005</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
              <gIBSMun><pIBSMun>0.0005</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
              <vIBS>1.00</vIBS>
              <gCBS><pCBS>0.0090</pCBS><vCBS>9.00</vCBS></gCBS>
            </gIBSCBS>
          </IBSCBS>
        </imposto>
      </det>
      <total><IBSCBSTot><vCBS>9.00</vCBS><vIBS>1.00</vIBS></IBSCBSTot></total>
    </infNFe>
  </NFe>
</nfeProc>"""
    result = _parse_and_validate(xml)
    rule_ids = [f["rule_id"] for f in result["findings"]]
    assert "LAYOUT_NFE" in rule_ids
