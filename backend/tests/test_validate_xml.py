"""Tests for the unified XML validation endpoint and engine."""

from app.routers.validate_xml import validate_xml, _detect_doc_type, CST_TABLE

# ── Fixtures ─────────────────────────────────────────────────────────────────

NFSE_OK = """<?xml version="1.0" encoding="UTF-8"?>
<NFS-e><infNfse>
  <PrestadorServico><RazaoSocial>X</RazaoSocial></PrestadorServico>
  <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
  <PrestacaoServico>
    <Servico>
      <CodigoServico>123456</CodigoServico>
      <cClassTrib>654321</cClassTrib>
      <CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST>
    </Servico>
    <Valores>
      <BaseCalculo>10000.00</BaseCalculo>
      <AliquotaCBS>0.0010</AliquotaCBS><ValorCBS>10.00</ValorCBS>
      <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>90.00</ValorIBS>
    </Valores>
  </PrestacaoServico>
</infNfse></NFS-e>"""

NFE_OK = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod></ide>
  <emit><CNPJ>12345678000195</CNPJ></emit>
  <dest><CNPJ>98765432000100</CNPJ></dest>
  <det nItem="1">
    <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
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
  <total><IBSCBSTot><vIBS>1.00</vIBS><vCBS>9.00</vCBS></IBSCBSTot></total>
</infNFe></NFe></nfeProc>"""

NFCE_OK = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>65</mod></ide>
  <emit><CNPJ>12345678000195</CNPJ></emit>
  <det nItem="1">
    <prod><NCM>22021000</NCM><CEST>0300100</CEST><vProd>100.00</vProd></prod>
    <imposto>
      <IBSCBS>
        <CST>000</CST>
        <cClassTrib>030010</cClassTrib>
        <gIBSCBS>
          <vBC>100.00</vBC>
          <gIBSUF><pIBSUF>0.0005</pIBSUF><vIBSUF>0.05</vIBSUF></gIBSUF>
          <gIBSMun><pIBSMun>0.0005</pIBSMun><vIBSMun>0.05</vIBSMun></gIBSMun>
          <vIBS>0.10</vIBS>
          <gCBS><pCBS>0.0090</pCBS><vCBS>0.90</vCBS></gCBS>
        </gIBSCBS>
      </IBSCBS>
    </imposto>
  </det>
  <total><IBSCBSTot><vIBS>0.10</vIBS><vCBS>0.90</vCBS></IBSCBSTot></total>
</infNFe></NFe></nfeProc>"""


# ── Detection ────────────────────────────────────────────────────────────────


class TestDetectDocType:
    def test_nfse(self):
        assert _detect_doc_type(NFSE_OK) == "NFSE"

    def test_nfe(self):
        assert _detect_doc_type(NFE_OK) == "NFE"

    def test_nfce(self):
        assert _detect_doc_type(NFCE_OK) == "NFCE"


# ── CST table ────────────────────────────────────────────────────────────────


class TestCstTable:
    def test_has_14_entries(self):
        assert len(CST_TABLE) == 14

    def test_known_csts(self):
        for code in ("000", "070", "200", "620", "830"):
            assert code in CST_TABLE


# ── NFS-e validation ─────────────────────────────────────────────────────────


class TestNfseValidation:
    def test_ok_no_fatals(self):
        result = validate_xml(NFSE_OK)
        fatals = [f for f in result.findings if f.severity == "FATAL"]
        assert len(fatals) == 0, f"Unexpected: {[f.rule_id for f in fatals]}"
        assert result.document_type == "NFSE"

    def test_missing_ibscbs(self):
        xml = """<NFS-e><infNfse>
          <PrestadorServico><RazaoSocial>X</RazaoSocial></PrestadorServico>
          <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
          <PrestacaoServico>
            <Servico><CodigoServico>123456</CodigoServico><cClassTrib>654321</cClassTrib>
            <CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST></Servico>
            <Valores><BaseCalculo>10000.00</BaseCalculo></Valores>
          </PrestacaoServico>
        </infNfse></NFS-e>"""
        result = validate_xml(xml)
        rules = [f.rule_id for f in result.findings if f.severity == "FATAL"]
        assert "IBSCBS_MISSING" in rules


# ── NF-e validation ──────────────────────────────────────────────────────────


class TestNfeValidation:
    def test_ok_no_fatals(self):
        result = validate_xml(NFE_OK)
        fatals = [f for f in result.findings if f.severity == "FATAL"]
        assert len(fatals) == 0, f"Unexpected: {[f.rule_id for f in fatals]}"
        assert result.document_type == "NFE"

    def test_ibs_split_error(self):
        xml = NFE_OK.replace("<vIBS>1.00</vIBS>", "<vIBS>1.50</vIBS>", 1)
        result = validate_xml(xml, "NFE")
        rules = [f.rule_id for f in result.findings if f.severity == "FATAL"]
        assert "IBSCBS_SPLIT" in rules

    def test_cst_invalid(self):
        xml = NFE_OK.replace("<CST>000</CST>", "<CST>999</CST>")
        result = validate_xml(xml, "NFE")
        rules = [f.rule_id for f in result.findings if f.severity == "FATAL"]
        assert "CST_VALID" in rules

    def test_cst_group_mismatch(self):
        """CST 000 requires gIBSCBS group."""
        xml = """<nfeProc><NFe><infNFe>
          <ide><mod>55</mod></ide>
          <emit><CNPJ>12345678000195</CNPJ></emit>
          <det nItem="1">
            <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000</vProd></prod>
            <imposto>
              <IBSCBS><CST>000</CST><cClassTrib>654321</cClassTrib></IBSCBS>
            </imposto>
          </det>
          <total><IBSCBSTot><vIBS>0</vIBS><vCBS>0</vCBS></IBSCBSTot></total>
        </infNFe></NFe></nfeProc>"""
        result = validate_xml(xml, "NFE")
        rules = [f.rule_id for f in result.findings if f.severity == "FATAL"]
        assert "CST_GROUP_MATCH" in rules

    def test_cbs_calc_error(self):
        xml = NFE_OK.replace("<vCBS>9.00</vCBS>", "<vCBS>99.00</vCBS>", 1)
        result = validate_xml(xml, "NFE")
        rules = [f.rule_id for f in result.findings if f.severity == "FATAL"]
        assert "IBSCBS_CALC" in rules


# ── NFC-e validation ─────────────────────────────────────────────────────────


class TestNfceValidation:
    def test_ok_no_fatals(self):
        result = validate_xml(NFCE_OK)
        fatals = [f for f in result.findings if f.severity == "FATAL"]
        assert len(fatals) == 0, f"Unexpected: {[f.rule_id for f in fatals]}"
        assert result.document_type == "NFCE"


# ── Router registration ─────────────────────────────────────────────────────


class TestRouterRegistered:
    def test_validate_xml_route_exists(self):
        from app.main import app
        paths = [getattr(r, "path", "") for r in app.routes]
        assert "/api/v1/validate/xml" in paths
