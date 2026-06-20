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

    # NT 2025.002 v1.40 (#311): obrigatoriedade de IBS/CBS é faseada por regime —
    # CRT 3 (Regime Normal) 03/08/2026; CRT 1/2/4 (Simples/MEI) só 04/01/2027.
    _NFE_SEM_IBSCBS = """<nfeProc><NFe><infNFe>
      <ide><mod>55</mod></ide>
      <emit><CNPJ>12345678000195</CNPJ><CRT>{crt}</CRT></emit>
      <det nItem="1">
        <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
        <imposto><ICMS><ICMSSN101><CST>101</CST></ICMSSN101></ICMS></imposto>
      </det>
      <total></total>
    </infNFe></NFe></nfeProc>"""

    def test_ibscbs_missing_simples_crt1_is_warning(self):
        """Simples Nacional (CRT 1) sem IBS/CBS → WARNING, não FATAL (obrigatório só 04/01/2027)."""
        result = validate_xml(self._NFE_SEM_IBSCBS.format(crt="1"), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBS_MISSING"]
        assert missing, "IBSCBS_MISSING esperado"
        assert all(f.severity == "WARNING" for f in missing), \
            f"CRT 1 (Simples) deve ser WARNING: {[f.severity for f in missing]}"

    def test_ibscbs_missing_mei_crt4_is_warning(self):
        """MEI (CRT 4) sem IBS/CBS → WARNING (obrigatório só 04/01/2027)."""
        result = validate_xml(self._NFE_SEM_IBSCBS.format(crt="4"), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBS_MISSING"]
        assert missing and all(f.severity == "WARNING" for f in missing), \
            f"CRT 4 (MEI) deve ser WARNING: {[f.severity for f in missing]}"

    def test_ibscbs_missing_regime_normal_crt3_is_fatal(self):
        """Regime Normal (CRT 3) sem IBS/CBS → FATAL (obrigatório 03/08/2026)."""
        result = validate_xml(self._NFE_SEM_IBSCBS.format(crt="3"), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBS_MISSING"]
        assert missing, "IBSCBS_MISSING esperado"
        assert all(f.severity == "FATAL" for f in missing), \
            f"CRT 3 (Regime Normal) deve ser FATAL: {[f.severity for f in missing]}"


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


# ── Item 1: janela sem penalidades — Ato Conjunto RFB/CGIBS nº 1/2025 art. 3º ──


class TestNoPenaltyWindow:
    """Multas por obrigação acessória suspensas para fatos geradores até 31/07/2026.
    A partir de 01/08/2026 a penalidade volta a ser FATAL. pedagogical_mode (LC 227)
    permanece como override manual independente da data."""

    _NFE = """<nfeProc><NFe><infNFe>
      <ide><mod>55</mod>{dh}</ide>
      <emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>
      <det nItem="1">
        <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
        <imposto><ICMS><ICMSSN101><CST>101</CST></ICMSSN101></ICMS></imposto>
      </det>
      <total></total>
    </infNFe></NFe></nfeProc>"""

    def _nfe(self, dh=None):
        return self._NFE.format(dh=f"<dhEmi>{dh}</dhEmi>" if dh else "")

    def test_dentro_da_janela_downgrade_para_warning(self):
        result = validate_xml(self._nfe("2026-07-31T10:00:00-03:00"), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBS_MISSING"]
        assert missing, "IBSCBS_MISSING esperado"
        assert all(f.severity == "WARNING" for f in missing)
        assert any("Ato Conjunto RFB/CGIBS" in (f.recommendation or "") for f in missing)

    def test_limite_01_08_2026_volta_a_fatal(self):
        result = validate_xml(self._nfe("2026-08-01T10:00:00-03:00"), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBS_MISSING"]
        assert missing and all(f.severity == "FATAL" for f in missing)

    def test_fora_da_janela_fatal(self):
        result = validate_xml(self._nfe("2026-08-15T10:00:00-03:00"), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBS_MISSING"]
        assert missing and all(f.severity == "FATAL" for f in missing)

    def test_sem_dhemi_preserva_fatal(self):
        result = validate_xml(self._nfe(), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBS_MISSING"]
        assert missing and all(f.severity == "FATAL" for f in missing)

    def test_pedagogical_mode_fora_da_janela_warning(self):
        result = validate_xml(self._nfe("2026-09-10T10:00:00-03:00"), "NFE", pedagogical_mode=True)
        missing = [f for f in result.findings if f.rule_id == "IBSCBS_MISSING"]
        assert missing and all(f.severity == "WARNING" for f in missing)
        assert any("LC 227/2026" in (f.recommendation or "") for f in missing)

    def test_regra_nao_acessoria_permanece_fatal_na_janela(self):
        # IBSCBS_SPLIT é regra de cálculo, não obrigação acessória → não entra na janela.
        xml = NFE_OK.replace("<mod>55</mod>", "<mod>55</mod><dhEmi>2026-05-10T10:00:00-03:00</dhEmi>", 1)
        xml = xml.replace("<vIBS>1.00</vIBS>", "<vIBS>1.50</vIBS>", 1)
        result = validate_xml(xml, "NFE")
        split = [f for f in result.findings if f.rule_id == "IBSCBS_SPLIT"]
        assert split and all(f.severity == "FATAL" for f in split)


# ── Item 2: IMPORT_IBSCBS_REQUIRED — incidência na importação (Decreto 12.955/2026) ──


class TestImportIbscbsRequired:
    """Importação (CFOP 3xxx ou grupo DI/DUIMP) é tributável por IBS/CBS independente
    de importador habitual (art. 65). Escopo: grupo IBSCBS presente porém zerado com
    CST tributável. Export (7xxx) e internas ficam fora."""

    def _nfe(self, cfop="3102", cst="000", dh=None, vcbs="0.00", vibs="0.00", di=False, no_ibscbs=False):
        di_xml = "<DI><nDI>2603001234</nDI></DI>" if di else ""
        ibscbs = "" if no_ibscbs else (
            f'<IBSCBS><CST>{cst}</CST><cClassTrib>000001</cClassTrib>'
            f'<gIBSCBS><vBC>1000.00</vBC>'
            f'<gIBSUF><pIBSUF>0</pIBSUF><vIBSUF>0.00</vIBSUF></gIBSUF>'
            f'<gIBSMun><pIBSMun>0</pIBSMun><vIBSMun>0.00</vIBSMun></gIBSMun>'
            f'<vIBS>{vibs}</vIBS><gCBS><pCBS>0</pCBS><vCBS>{vcbs}</vCBS></gCBS>'
            f'</gIBSCBS></IBSCBS>'
        )
        dh_xml = f"<dhEmi>{dh}</dhEmi>" if dh else ""
        return (
            f'<nfeProc><NFe><infNFe><ide><mod>55</mod>{dh_xml}</ide>'
            f'<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            f'<det nItem="1"><prod><CFOP>{cfop}</CFOP><NCM>84713012</NCM><CEST>2104900</CEST>'
            f'<vProd>1000.00</vProd>{di_xml}</prod><imposto>{ibscbs}</imposto></det>'
            f'<total><IBSCBSTot><vIBS>{vibs}</vIBS><vCBS>{vcbs}</vCBS></IBSCBSTot></total>'
            f'</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml):
        r = validate_xml(xml, "NFE")
        return [f for f in r.findings if f.rule_id == "IMPORT_IBSCBS_REQUIRED"]

    def test_cfop_3xxx_zerado_fora_da_janela_fatal(self):
        f = self._find(self._nfe(cfop="3102", dh="2026-09-10T10:00:00-03:00"))
        assert f and f[0].severity == "FATAL"
        assert "Decreto 12.955/2026" in f[0].recommendation

    def test_deteccao_via_di_com_cfop_interno(self):
        f = self._find(self._nfe(cfop="1102", di=True, dh="2026-09-10T10:00:00-03:00"))
        assert f and f[0].severity == "FATAL"

    def test_importacao_tributada_sem_finding(self):
        assert self._find(self._nfe(cfop="3102", vcbs="9.00", vibs="1.00")) == []

    def test_cst_070_imunidade_sem_finding(self):
        assert self._find(self._nfe(cfop="3102", cst="070")) == []

    def test_cst_200_diferimento_sem_finding(self):
        assert self._find(self._nfe(cfop="3102", cst="200")) == []

    def test_interna_5102_sem_finding(self):
        assert self._find(self._nfe(cfop="5102")) == []

    def test_exportacao_7101_sem_finding(self):
        assert self._find(self._nfe(cfop="7101")) == []

    def test_dentro_da_janela_warning(self):
        f = self._find(self._nfe(cfop="3102", dh="2026-05-10T10:00:00-03:00"))
        assert f and f[0].severity == "WARNING"

    def test_sem_grupo_ibscbs_nao_dispara(self):
        assert self._find(self._nfe(cfop="3102", no_ibscbs=True)) == []
