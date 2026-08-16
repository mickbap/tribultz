"""Tests for S13 cross-validation rules (NCM, ClassTrib, CNPJ, batch)."""

from app.routers.validate_xml import (
    validate_xml,
    batch_cross_check,
    BatchDocSummary,
)
from app.data.ncm_codes import VALID_NCM_CODES, is_valid_ncm


# -- Fixtures ----------------------------------------------------------------

NFE_TEMPLATE = """<?xml version="1.0"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod></ide>
  <emit><CNPJ>{cnpj}</CNPJ></emit>
  <det nItem="1">
    <prod><NCM>{ncm}</NCM><CEST>2104900</CEST><CFOP>5102</CFOP><vProd>1000.00</vProd></prod>
    <imposto>
      <IBSCBS>
        <CST>{cst}</CST>
        <cClassTrib>{classtrib}</cClassTrib>
        <gIBSCBS>
          <vBC>1000.00</vBC>
          <gIBSUF><pIBSUF>0.0500</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
          <gIBSMun><pIBSMun>0.0500</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
          <vIBS>1.00</vIBS>
          <gCBS><pCBS>0.9000</pCBS><vCBS>9.00</vCBS></gCBS>
        </gIBSCBS>
      </IBSCBS>
    </imposto>
  </det>
  <total><IBSCBSTot><vIBS>1.00</vIBS><vCBS>9.00</vCBS></IBSCBSTot></total>
</infNFe></NFe></nfeProc>"""

NFE_WITH_NF_NUM = """<?xml version="1.0"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod><nNF>{nf_num}</nNF><dhEmi>{date}</dhEmi></ide>
  <emit><CNPJ>{cnpj}</CNPJ></emit>
  <det nItem="1">
    <prod><NCM>{ncm}</NCM><CEST>2104900</CEST><vProd>{valor}</vProd></prod>
    <imposto>
      <IBSCBS>
        <CST>{cst}</CST>
        <cClassTrib>100001</cClassTrib>
        <gIBSCBS>
          <vBC>1000.00</vBC>
          <gIBSUF><pIBSUF>0.0500</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
          <gIBSMun><pIBSMun>0.0500</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
          <vIBS>1.00</vIBS>
          <gCBS><pCBS>0.9000</pCBS><vCBS>9.00</vCBS></gCBS>
        </gIBSCBS>
      </IBSCBS>
    </imposto>
  </det>
  <total><IBSCBSTot><vIBS>1.00</vIBS><vCBS>9.00</vCBS></IBSCBSTot></total>
</infNFe></NFe></nfeProc>"""


def _nfe(ncm="84713012", cst="000", classtrib="654321", cnpj="12345678000195"):
    return NFE_TEMPLATE.format(ncm=ncm, cst=cst, classtrib=classtrib, cnpj=cnpj)


def _nfe_batch(cnpj="12345678000195", nf_num="1001", date="2026-03-24",
               ncm="84713012", cst="000", valor="1000.00"):
    return NFE_WITH_NF_NUM.format(
        cnpj=cnpj, nf_num=nf_num, date=date, ncm=ncm, cst=cst, valor=valor,
    )


# -- NCM data module tests ---------------------------------------------------

class TestNcmDataModule:
    def test_valid_ncm_codes_has_entries(self):
        assert len(VALID_NCM_CODES) >= 200

    def test_known_ncm_is_valid(self):
        assert is_valid_ncm("84713012")

    def test_invalid_ncm_is_not_valid(self):
        assert not is_valid_ncm("00000000")

    def test_all_codes_are_8_digits(self):
        for code in VALID_NCM_CODES:
            assert len(code) == 8 and code.isdigit(), f"Invalid NCM: {code}"


# -- Rule 15: NCM_FORMAT -----------------------------------------------------

class TestNcmFormat:
    def test_valid_8_digit_ncm_no_format_finding(self):
        result = validate_xml(_nfe(ncm="84713012"))
        rule_ids = [f.rule_id for f in result.findings]
        assert "NCM_FORMAT" not in rule_ids

    def test_5_digit_ncm_generates_fatal(self):
        result = validate_xml(_nfe(ncm="84713"))
        findings = [f for f in result.findings if f.rule_id == "NCM_FORMAT"]
        assert len(findings) == 1
        assert findings[0].severity == "FATAL"

    def test_ncm_with_letters_generates_fatal(self):
        result = validate_xml(_nfe(ncm="8471301X"))
        findings = [f for f in result.findings if f.rule_id == "NCM_FORMAT"]
        assert len(findings) == 1


# -- Rule 16: NCM_VALID ------------------------------------------------------

class TestNcmValid:
    def test_known_ncm_no_finding(self):
        result = validate_xml(_nfe(ncm="84713012"))
        rule_ids = [f.rule_id for f in result.findings]
        assert "NCM_VALID" not in rule_ids

    def test_unknown_ncm_generates_fatal(self):
        result = validate_xml(_nfe(ncm="99999999"))
        findings = [f for f in result.findings if f.rule_id == "NCM_VALID"]
        assert len(findings) == 1
        assert findings[0].severity == "FATAL"
        assert "99999999" in findings[0].title

    def test_format_error_skips_valid_check(self):
        result = validate_xml(_nfe(ncm="84713"))
        rule_ids = [f.rule_id for f in result.findings]
        assert "NCM_FORMAT" in rule_ids
        assert "NCM_VALID" not in rule_ids


# -- Rule 17: CLASSTRIB_VALID ------------------------------------------------

class TestClassTribValid:
    def test_classtrib_found_no_finding(self):
        result = validate_xml(
            _nfe(classtrib="100001"),
            classtrib_results={"100001": True},
        )
        rule_ids = [f.rule_id for f in result.findings]
        assert "CLASSTRIB_VALID" not in rule_ids

    def test_classtrib_not_found_generates_fatal(self):
        result = validate_xml(
            _nfe(classtrib="999999"),
            classtrib_results={"999999": False},
        )
        findings = [f for f in result.findings if f.rule_id == "CLASSTRIB_VALID"]
        assert len(findings) == 1
        assert findings[0].severity == "FATAL"

    def test_classtrib_api_error_generates_alert(self):
        result = validate_xml(
            _nfe(classtrib="100001"),
            classtrib_results={"100001": None},
        )
        findings = [f for f in result.findings if f.rule_id == "CLASSTRIB_VALID"]
        assert len(findings) == 1
        assert findings[0].severity == "ALERT"

    def test_no_enrichment_skips_classtrib_rule(self):
        result = validate_xml(_nfe(classtrib="999999"))
        rule_ids = [f.rule_id for f in result.findings]
        assert "CLASSTRIB_VALID" not in rule_ids


# -- Rule 18: CNPJ_ACTIVE ----------------------------------------------------

class TestCnpjActive:
    def test_active_cnpj_no_finding(self):
        result = validate_xml(
            _nfe(cnpj="12345678000195"),
            cnpj_result=(True, "ATIVA"),
        )
        rule_ids = [f.rule_id for f in result.findings]
        assert "CNPJ_ACTIVE" not in rule_ids

    def test_inactive_cnpj_generates_fatal(self):
        result = validate_xml(
            _nfe(cnpj="12345678000195"),
            cnpj_result=(False, "BAIXADA"),
        )
        findings = [f for f in result.findings if f.rule_id == "CNPJ_ACTIVE"]
        assert len(findings) == 1
        assert findings[0].severity == "FATAL"
        assert "BAIXADA" in findings[0].title

    def test_api_unavailable_generates_alert(self):
        result = validate_xml(
            _nfe(cnpj="12345678000195"),
            cnpj_result=(False, "API_UNAVAILABLE"),
        )
        findings = [f for f in result.findings if f.rule_id == "CNPJ_ACTIVE"]
        assert len(findings) == 1
        assert findings[0].severity == "ALERT"

    def test_no_enrichment_skips_cnpj_rule(self):
        result = validate_xml(_nfe())
        rule_ids = [f.rule_id for f in result.findings]
        assert "CNPJ_ACTIVE" not in rule_ids


# -- Batch cross-check -------------------------------------------------------

class TestBatchCrossCheck:
    def test_duplicate_by_cnpj_and_nf_number(self):
        xml1 = _nfe_batch(cnpj="12345678000195", nf_num="1001")
        xml2 = _nfe_batch(cnpj="12345678000195", nf_num="1001")
        docs = [BatchDocSummary(xml=xml1, fatals=0), BatchDocSummary(xml=xml2, fatals=0)]
        result = batch_cross_check(docs)
        assert len(result.duplicates) >= 1
        assert result.duplicates[0].indices == [0, 1]

    def test_different_nf_numbers_no_duplicate(self):
        xml1 = _nfe_batch(cnpj="12345678000195", nf_num="1001", valor="1000.00")
        xml2 = _nfe_batch(cnpj="12345678000195", nf_num="1002", valor="2000.00")
        docs = [BatchDocSummary(xml=xml1, fatals=0), BatchDocSummary(xml=xml2, fatals=0)]
        result = batch_cross_check(docs)
        assert len(result.duplicates) == 0

    def test_cst_same_ncm_same_cst_no_anomaly(self):
        xml1 = _nfe_batch(ncm="84713012", cst="000")
        xml2 = _nfe_batch(ncm="84713012", cst="000", nf_num="1002")
        docs = [BatchDocSummary(xml=xml1, fatals=0), BatchDocSummary(xml=xml2, fatals=0)]
        result = batch_cross_check(docs)
        assert len(result.cst_anomalies) == 0

    def test_cst_different_cst_generates_alert(self):
        xml1 = _nfe_batch(ncm="84713012", cst="000")
        xml2 = _nfe_batch(ncm="84713012", cst="200", nf_num="1002")
        docs = [BatchDocSummary(xml=xml1, fatals=0), BatchDocSummary(xml=xml2, fatals=0)]
        result = batch_cross_check(docs)
        assert len(result.cst_anomalies) == 1
        assert result.cst_anomalies[0].severity == "ALERT"

    def test_cst_000_vs_070_is_fatal(self):
        xml1 = _nfe_batch(ncm="84713012", cst="000")
        xml2 = _nfe_batch(ncm="84713012", cst="070", nf_num="1002")
        docs = [BatchDocSummary(xml=xml1, fatals=0), BatchDocSummary(xml=xml2, fatals=0)]
        result = batch_cross_check(docs)
        assert len(result.cst_anomalies) == 1
        assert result.cst_anomalies[0].severity == "FATAL"

    def test_batch_stats(self):
        xml1 = _nfe_batch(nf_num="1001")
        xml2 = _nfe_batch(nf_num="1002")
        docs = [BatchDocSummary(xml=xml1, fatals=0), BatchDocSummary(xml=xml2, fatals=3)]
        result = batch_cross_check(docs)
        assert result.stats.total_documents == 2
        assert result.stats.pass_count == 1
        assert result.stats.fail_count == 1
        assert result.stats.pass_rate == 50.0

    def test_risk_score_low_for_clean_batch(self):
        xml1 = _nfe_batch(nf_num="1001")
        xml2 = _nfe_batch(nf_num="1002", cnpj="98765432000100")
        docs = [BatchDocSummary(xml=xml1, fatals=0), BatchDocSummary(xml=xml2, fatals=0)]
        result = batch_cross_check(docs)
        assert result.risk_score <= 25
        assert result.risk_level == "LOW"

    def test_risk_score_high_for_bad_batch(self):
        xml1 = _nfe_batch(nf_num="1001")
        xml2 = _nfe_batch(nf_num="1001")
        docs = [
            BatchDocSummary(xml=xml1, fatals=5, has_inactive_cnpj=True, has_unknown_ncm=True),
            BatchDocSummary(xml=xml2, fatals=5, has_inactive_cnpj=True, has_unknown_ncm=True),
        ]
        result = batch_cross_check(docs)
        assert result.risk_score >= 50
        assert result.risk_level in ("HIGH", "CRITICAL")


# -- Backwards compatibility --------------------------------------------------

class TestBackwardsCompatibility:
    def test_valid_nfe_still_passes(self):
        result = validate_xml(_nfe())
        fatals = [f for f in result.findings if f.severity == "FATAL"]
        assert len(fatals) == 0

    def test_enrichment_params_default_to_none(self):
        result = validate_xml(_nfe())
        assert result.document_type == "NFE"
