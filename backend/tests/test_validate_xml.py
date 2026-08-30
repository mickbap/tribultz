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
          <gIBSUF><pIBSUF>0.0500</pIBSUF><vIBSUF>0.05</vIBSUF></gIBSUF>
          <gIBSMun><pIBSMun>0.0500</pIBSMun><vIBSMun>0.05</vIBSMun></gIBSMun>
          <vIBS>0.10</vIBS>
          <gCBS><pCBS>0.9000</pCBS><vCBS>0.90</vCBS></gCBS>
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
        # NT 2025.002 v1.51 (04/08/2026): IBSCBS_MISSING (Rejeição 1115/UB12-10) deixou
        # de ser FATAL — implementação em produção da rejeição está suspensa, sem data.
        rules = [f.rule_id for f in result.findings if f.severity == "WARNING"]
        assert "IBSCBS_MISSING" in rules


class TestNfseNt007:
    """NT 007/2026 (SE/CGNFS-e): indZFMALC + vPis/vCofins devidos (#406).

    3 fixtures conforme DoD: serviço comum (caminho feliz), locação de imóvel
    (nova operação documentável — só prova que o parser não quebra) e operação
    ZFM (indZFMALC).
    """

    # Fixture 1 — serviço comum, sem benefício ZFM/ALC.
    _SERVICO_COMUM = """<NFS-e><infNfse>
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

    # Fixture 2 — locação de imóvel (perfil de operação novo via NT 007/2026).
    _LOCACAO_IMOVEL = """<NFS-e><infNfse>
      <PrestadorServico><RazaoSocial>Imobiliária Z</RazaoSocial></PrestadorServico>
      <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
      <PrestacaoServico>
        <Servico>
          <TipoOperacao>LOCACAO_IMOVEL</TipoOperacao>
          <CodigoServico>310101</CodigoServico>
          <cClassTrib>654321</cClassTrib>
          <CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST>
        </Servico>
        <Valores>
          <BaseCalculo>5000.00</BaseCalculo>
          <AliquotaCBS>0.0010</AliquotaCBS><ValorCBS>5.00</ValorCBS>
          <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>45.00</ValorIBS>
          <ValorPis>1.65</ValorPis><ValorCofins>7.60</ValorCofins>
        </Valores>
      </PrestacaoServico>
    </infNfse></NFS-e>"""

    # Fixture 3 — operação ZFM (indZFMALC), com o parâmetro de CBS declarado.
    def _operacao_zfm(self, valor_cbs: str) -> str:
        return f"""<NFS-e><infNfse>
          <PrestadorServico><RazaoSocial>Distribuidora ZFM</RazaoSocial></PrestadorServico>
          <TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>
          <PrestacaoServico>
            <Servico>
              <CodigoServico>123456</CodigoServico>
              <cClassTrib>654321</cClassTrib>
              <CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST>
            </Servico>
            <Valores>
              <IndZFMALC>1</IndZFMALC>
              <BaseCalculo>10000.00</BaseCalculo>
              <AliquotaCBS>0.0000</AliquotaCBS><ValorCBS>{valor_cbs}</ValorCBS>
              <AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>90.00</ValorIBS>
            </Valores>
          </PrestacaoServico>
        </infNfse></NFS-e>"""

    def test_servico_comum_caminho_feliz_sem_findings_novos(self):
        result = validate_xml(self._SERVICO_COMUM)
        rules = {f.rule_id for f in result.findings}
        assert "INDZFMALC_CBS_ZERO" not in rules
        assert "PIS_COFINS_DEVIDO_NEGATIVO" not in rules

    def test_locacao_imovel_nao_quebra_o_parser(self):
        # Nova operação documentável (NT 007/2026) — só precisa não quebrar
        # nem virar FATAL espúrio; vPis/vCofins positivos não disparam a regra.
        result = validate_xml(self._LOCACAO_IMOVEL)
        fatals = [f for f in result.findings if f.severity == "FATAL"]
        assert fatals == [], f"Inesperado: {[f.rule_id for f in fatals]}"
        assert "PIS_COFINS_DEVIDO_NEGATIVO" not in {f.rule_id for f in result.findings}

    def test_zfm_com_cbs_zero_sem_finding(self):
        result = validate_xml(self._operacao_zfm(valor_cbs="0.00"))
        assert "INDZFMALC_CBS_ZERO" not in {f.rule_id for f in result.findings}

    def test_zfm_com_cbs_maior_que_zero_warning(self):
        result = validate_xml(self._operacao_zfm(valor_cbs="10.00"))
        f = [x for x in result.findings if x.rule_id == "INDZFMALC_CBS_ZERO"]
        assert any(x.id == "F_INDZFMALC_CBS_ZERO" and x.severity == "WARNING" for x in f)

    def test_pis_negativo_warning(self):
        xml = self._SERVICO_COMUM.replace("</Valores>", "<ValorPis>-5.00</ValorPis></Valores>")
        result = validate_xml(xml)
        f = [x for x in result.findings if x.rule_id == "PIS_COFINS_DEVIDO_NEGATIVO"]
        assert any(x.id == "F_PIS_COFINS_DEVIDO_NEGATIVO_PIS" and x.severity == "WARNING" for x in f)

    def test_cofins_negativo_warning(self):
        xml = self._SERVICO_COMUM.replace("</Valores>", "<ValorCofins>-3.00</ValorCofins></Valores>")
        result = validate_xml(xml)
        f = [x for x in result.findings if x.rule_id == "PIS_COFINS_DEVIDO_NEGATIVO"]
        assert any(x.id == "F_PIS_COFINS_DEVIDO_NEGATIVO_COFINS" and x.severity == "WARNING" for x in f)

    def test_pis_cofins_positivos_sem_finding(self):
        result = validate_xml(self._LOCACAO_IMOVEL)
        assert "PIS_COFINS_DEVIDO_NEGATIVO" not in {f.rule_id for f in result.findings}


class TestPisCofinsDevidoCalc:
    """PIS_COFINS_DEVIDO_CALC (#480): vPis/vCofins = base × alíquota.

    Fixture com os valores do exemplo oficial (manual de integração NFS-e
    pós-NT007/2026): vBCPisCofins=988.33, pAliqPis=1.65%, pAliqCofins=7.60%
    → vPis=16.31, vCofins=75.11 (bate exato, arredondamento bancário).
    """

    _BASE = """<NFS-e><infNfse>
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
          <vBCPisCofins>988.33</vBCPisCofins>
          <pAliqPis>1.65</pAliqPis><pAliqCofins>7.60</pAliqCofins>
          <vPis>{v_pis}</vPis><vCofins>{v_cofins}</vCofins>
        </Valores>
      </PrestacaoServico>
    </infNfse></NFS-e>"""

    def test_valores_corretos_sem_finding(self):
        xml = self._BASE.format(v_pis="16.31", v_cofins="75.11")
        result = validate_xml(xml)
        assert "PIS_COFINS_DEVIDO_CALC" not in {f.rule_id for f in result.findings}

    def test_vpis_divergente_warning(self):
        xml = self._BASE.format(v_pis="20.00", v_cofins="75.11")
        result = validate_xml(xml)
        f = [x for x in result.findings if x.rule_id == "PIS_COFINS_DEVIDO_CALC"]
        assert any(x.id == "F_PIS_COFINS_DEVIDO_CALC_PIS" and x.severity == "WARNING" for x in f)

    def test_vcofins_divergente_warning(self):
        xml = self._BASE.format(v_pis="16.31", v_cofins="80.00")
        result = validate_xml(xml)
        f = [x for x in result.findings if x.rule_id == "PIS_COFINS_DEVIDO_CALC"]
        assert any(x.id == "F_PIS_COFINS_DEVIDO_CALC_COFINS" and x.severity == "WARNING" for x in f)

    def test_sem_base_ou_aliquota_nao_dispara(self):
        # Campos opcionais — sem vBCPisCofins/pAliqPis/pAliqCofins, a regra não
        # deve tentar calcular nada (degradação graciosa, mesmo padrão do IBSCBS_CALC).
        xml = """<NFS-e><infNfse>
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
              <ValorPis>1.65</ValorPis><ValorCofins>7.60</ValorCofins>
            </Valores>
          </PrestacaoServico>
        </infNfse></NFS-e>"""
        result = validate_xml(xml)
        assert "PIS_COFINS_DEVIDO_CALC" not in {f.rule_id for f in result.findings}


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

    def test_ibscbs_missing_regime_normal_crt3_is_warning(self):
        """Regime Normal (CRT 3) sem IBS/CBS → WARNING (NT 2025.002 v1.51: rejeição
        1115/UB12-10 com implementação em produção suspensa, sem data; a obrigação
        legal desde 03/08/2026 e a multa por obrigação acessória desde 01/08/2026
        seguem valendo, mas não bloqueiam mais a emissão)."""
        result = validate_xml(self._NFE_SEM_IBSCBS.format(crt="3"), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBS_MISSING"]
        assert missing, "IBSCBS_MISSING esperado"
        assert all(f.severity == "WARNING" for f in missing), \
            f"CRT 3 (Regime Normal) deve ser WARNING (v1.51): {[f.severity for f in missing]}"


# ── NFC-e validation ─────────────────────────────────────────────────────────


class TestNfceValidation:
    def test_ok_no_fatals(self):
        result = validate_xml(NFCE_OK)
        fatals = [f for f in result.findings if f.severity == "FATAL"]
        assert len(fatals) == 0, f"Unexpected: {[f.rule_id for f in fatals]}"
        assert result.document_type == "NFCE"


# ── Router registration ─────────────────────────────────────────────────────


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


class TestRouterRegistered:
    def test_validate_xml_route_exists(self):
        from app.main import app
        paths = _all_registered_paths(app.routes)
        assert "/api/v1/validate/xml" in paths


# ── Item 1: janela sem penalidades — Ato Conjunto RFB/CGIBS nº 1/2025 art. 3º ──


class TestNoPenaltyWindow:
    """Multas por obrigação acessória suspensas para fatos geradores até 31/07/2026.
    A partir de 01/08/2026 a penalidade volta a ser FATAL. pedagogical_mode (LC 227)
    permanece como override manual independente da data.

    Veículo: IBSCBSTOT_MISSING (Rejeição 1119/W34-20), não IBSCBS_MISSING — desde a
    NT 2025.002 v1.51 (04/08/2026), IBSCBS_MISSING (Rejeição 1115/UB12-10) é WARNING
    incondicional (implementação em produção da rejeição suspensa, sem data; ver
    TestIbscbsMissingV151 abaixo) e não participa mais deste mecanismo de janela/
    pedagogical_mode. IBSCBSTOT_MISSING permanece com o comportamento antigo,
    inalterado (mapa NT v1.51 §2/§6b), por isso segue como veículo certo pra testar
    a janela sem penalidades em si. Usa `_nfe_w03` (definido mais abaixo, #403)."""

    def test_dentro_da_janela_downgrade_para_warning(self):
        result = validate_xml(_nfe_w03(dh_emi="2026-07-31T10:00:00-03:00", tot=False), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBSTOT_MISSING"]
        assert missing, "IBSCBSTOT_MISSING esperado"
        assert all(f.severity == "WARNING" for f in missing)
        assert any("Ato Conjunto RFB/CGIBS" in (f.recommendation or "") for f in missing)

    def test_limite_01_08_2026_volta_a_fatal(self):
        result = validate_xml(_nfe_w03(dh_emi="2026-08-01T10:00:00-03:00", tot=False), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBSTOT_MISSING"]
        assert missing and all(f.severity == "FATAL" for f in missing)

    def test_fora_da_janela_fatal(self):
        result = validate_xml(_nfe_w03(dh_emi="2026-08-15T10:00:00-03:00", tot=False), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBSTOT_MISSING"]
        assert missing and all(f.severity == "FATAL" for f in missing)

    def test_pedagogical_mode_fora_da_janela_warning(self):
        result = validate_xml(
            _nfe_w03(dh_emi="2026-09-10T10:00:00-03:00", tot=False), "NFE", pedagogical_mode=True,
        )
        missing = [f for f in result.findings if f.rule_id == "IBSCBSTOT_MISSING"]
        assert missing and all(f.severity == "WARNING" for f in missing)
        assert any("LC 227/2026" in (f.recommendation or "") for f in missing)


class TestIbscbsMissingV151:
    """NT 2025.002 v1.51 (04/08/2026): IBSCBS_MISSING sempre WARNING. Rejeição
    1115/UB12-10 com implementação em produção suspensa (sem data) — diferente de
    IBSCBSTOT_MISSING (TestNoPenaltyWindow acima), não depende mais de CRT, janela
    do Ato Conjunto 1/25 nem de pedagogical_mode."""

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

    def test_pos_01_08_2026_sem_pedagogical_mode_ainda_warning(self):
        result = validate_xml(self._nfe("2026-08-15T10:00:00-03:00"), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBS_MISSING"]
        assert missing, "IBSCBS_MISSING esperado"
        assert all(f.severity == "WARNING" for f in missing)
        assert any("implementação em produção SUSPENSA" in (f.recommendation or "") for f in missing)
        assert any(
            "multa por obrigação acessória segue aplicável desde 01/08/2026" in (f.recommendation or "")
            for f in missing
        )

    def test_sem_dhemi_ainda_warning(self):
        result = validate_xml(self._nfe(), "NFE")
        missing = [f for f in result.findings if f.rule_id == "IBSCBS_MISSING"]
        assert missing and all(f.severity == "WARNING" for f in missing)

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


# ── Item 3: PF_CONTRIB_CNPJ — PF contribuinte deve ter CNPJ (Decreto 13.075/2026) ──


class TestPfContribCnpj:
    """Gatilho documental: emit/CPF presente, emit/CNPJ ausente, emissão ≥ 01/01/2027.

    O ENQUADRAMENTO não é verificável do XML — nem como contribuinte, nem como
    nanoempreendedor, nem como optante pelo regime regular. Por isso ALERT, nunca
    FATAL. O Ato Conjunto RFB/CGIBS nº 6/2026 dispensa o nanoempreendedor não
    optante, com efeitos até 31/12/2028, e a orientação tem de dizer isso."""

    def _nfe(self, ident, dh=None, cclass="000001"):
        dh_xml = f"<dhEmi>{dh}</dhEmi>" if dh else ""
        return (
            f'<nfeProc><NFe><infNFe><ide><mod>55</mod>{dh_xml}</ide>'
            f'<emit>{ident}<CRT>1</CRT></emit><dest><CPF>11122233344</CPF></dest>'
            f'<det nItem="1"><prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>100.00</vProd></prod>'
            f'<imposto><IBSCBS><CST>410</CST><cClassTrib>{cclass}</cClassTrib></IBSCBS></imposto></det>'
            f'<total></total></infNFe></NFe></nfeProc>'
        ) if cclass != "000001" else (
            f'<nfeProc><NFe><infNFe><ide><mod>55</mod>{dh_xml}</ide>'
            f'<emit>{ident}<CRT>1</CRT></emit><dest><CPF>11122233344</CPF></dest>'
            f'<det nItem="1"><prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>100.00</vProd></prod>'
            f'<imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib></IBSCBS></imposto></det>'
            f'<total></total></infNFe></NFe></nfeProc>'
        )

    def _find(self, xml, doc="NFE"):
        return [f for f in validate_xml(xml, doc).findings if f.rule_id == "PF_CONTRIB_CNPJ"]

    def test_emit_cpf_apos_01_01_2027_alert(self):
        f = self._find(self._nfe("<CPF>12345678909</CPF>", "2027-01-01T10:00:00-03:00"))
        assert f and f[0].severity == "ALERT"
        assert "Ato Conjunto RFB/CGIBS nº 6/2026" in f[0].recommendation

    def test_emit_cpf_antes_de_01_01_2027_sem_finding(self):
        assert self._find(self._nfe("<CPF>12345678909</CPF>", "2026-12-31T10:00:00-03:00")) == []

    def test_emit_cpf_em_01_07_2026_prazo_antigo_adiado_sem_finding(self):
        # Prazo original (Comunicado Conjunto 01/2025) — adiado pelo Decreto 13.075/2026.
        assert self._find(self._nfe("<CPF>12345678909</CPF>", "2026-07-01T10:00:00-03:00")) == []

    def test_emit_cnpj_sem_finding(self):
        assert self._find(self._nfe("<CNPJ>12345678000195</CNPJ>", "2026-08-10T10:00:00-03:00")) == []

    def test_emit_cpf_sem_data_sem_finding(self):
        assert self._find(self._nfe("<CPF>12345678909</CPF>")) == []

    def test_dest_cpf_emit_cnpj_sem_finding(self):
        # destinatário é CPF mas emitente é CNPJ → só o emitente importa
        assert self._find(self._nfe("<CNPJ>12345678000195</CNPJ>", "2026-09-01T10:00:00-03:00")) == []

    def test_nfse_prestador_cpf_alert(self):
        xml = (
            '<NFS-e><infNfse><DataEmissao>2027-02-01T10:00:00</DataEmissao>'
            '<PrestadorServico><RazaoSocial>X</RazaoSocial><CPF>98765432100</CPF></PrestadorServico>'
            '<TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>'
            '<PrestacaoServico><Servico><CodigoServico>123456</CodigoServico><cClassTrib>654321</cClassTrib>'
            '<CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST></Servico>'
            '<Valores><BaseCalculo>1000.00</BaseCalculo><AliquotaCBS>0.0010</AliquotaCBS><ValorCBS>1.00</ValorCBS>'
            '<AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>9.00</ValorIBS></Valores></PrestacaoServico>'
            '</infNfse></NFS-e>'
        )
        f = self._find(xml, "NFSE")
        assert f and f[0].severity == "ALERT"


# ── Item #311: códigos de rejeição da NT v1.40 (1115, 1106, 960) ─────────────


class TestRejectionCodesV140:
    """Anota o código oficial SEFAZ na recomendação das detecções (NF-e/NFC-e)."""

    _NFE_NO_CLASSTRIB = (
        '<nfeProc><NFe><infNFe><ide><mod>55</mod><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide>'
        '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
        '<det nItem="1"><prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>'
        '<imposto><IBSCBS><CST>000</CST></IBSCBS></imposto></det><total></total></infNFe></NFe></nfeProc>'
    )
    _NFE_NO_IBSCBS = (
        '<nfeProc><NFe><infNFe><ide><mod>55</mod><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide>'
        '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
        '<det nItem="1"><prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>'
        '<imposto><ICMS><ICMSSN101><CST>101</CST></ICMSSN101></ICMS></imposto></det><total></total>'
        '</infNFe></NFe></nfeProc>'
    )

    def test_ibscbs_missing_cita_1115(self):
        r = validate_xml(self._NFE_NO_IBSCBS, "NFE")
        f = [x for x in r.findings if x.rule_id == "IBSCBS_MISSING"]
        assert f and "Rejeição 1115" in f[0].recommendation

    def test_cclasstrib_cita_1106_e_960(self):
        r = validate_xml(self._NFE_NO_CLASSTRIB, "NFE")
        f = [x for x in r.findings if x.rule_id == "CCLASSTRIB_6_DIGITS"]
        assert f and "1106" in f[0].recommendation and "960" in f[0].recommendation

    def test_nfse_nao_recebe_codigo_nfe(self):
        xml = (
            '<NFS-e><infNfse><PrestadorServico><RazaoSocial>X</RazaoSocial></PrestadorServico>'
            '<TomadorServico><RazaoSocial>Y</RazaoSocial></TomadorServico>'
            '<PrestacaoServico><Servico><CodigoServico>123456</CodigoServico>'
            '<CST>090</CST><NCM>84713012</NCM><CEST>2104900</CEST></Servico>'
            '<Valores><BaseCalculo>1000.00</BaseCalculo><AliquotaCBS>0.0010</AliquotaCBS><ValorCBS>1.00</ValorCBS>'
            '<AliquotaIBS>0.0090</AliquotaIBS><ValorIBS>9.00</ValorIBS></Valores></PrestacaoServico>'
            '</infNfse></NFS-e>'
        )
        r = validate_xml(xml, "NFSE")
        f = [x for x in r.findings if x.rule_id == "CCLASSTRIB_6_DIGITS"]
        assert f and "1106" not in f[0].recommendation


# ── Item #278: ALIQUOTA_CLASSTRIB — slice alíquota-zero ──────────────────────


class TestAliquotaClasstrib:
    """cClassTrib isento/imune (CST 400/410) ou redução ≥100% deve ter IBS/CBS = 0.
    pCBS/pIBS > 0 nesse caso → FATAL. Independente das alíquotas de referência."""

    def _nfe(self, code, pcbs="0", pibsuf="0", pibsmun="0"):
        return (
            '<nfeProc><NFe><infNFe><ide><mod>55</mod></ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            '<det nItem="1"><prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>'
            f'<imposto><IBSCBS><CST>000</CST><cClassTrib>{code}</cClassTrib>'
            '<gIBSCBS><vBC>1000.00</vBC>'
            f'<gIBSUF><pIBSUF>{pibsuf}</pIBSUF><vIBSUF>0.00</vIBSUF></gIBSUF>'
            f'<gIBSMun><pIBSMun>{pibsmun}</pIBSMun><vIBSMun>0.00</vIBSMun></gIBSMun>'
            f'<vIBS>0.00</vIBS><gCBS><pCBS>{pcbs}</pCBS><vCBS>0.00</vCBS></gCBS>'
            '</gIBSCBS></IBSCBS></imposto></det>'
            '<total><IBSCBSTot><vIBS>0.00</vIBS><vCBS>0.00</vCBS></IBSCBSTot></total>'
            '</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml):
        return [f for f in validate_xml(xml, "NFE").findings if f.rule_id == "ALIQUOTA_CLASSTRIB"]

    def test_isento_400_com_cbs_declarado_fatal(self):
        f = self._find(self._nfe("400001", pcbs="0.9"))
        assert any(x.id == "F_ALIQUOTA_CLASSTRIB_CBS" for x in f)
        assert all(x.severity == "FATAL" for x in f)

    def test_isento_zerado_sem_finding(self):
        assert self._find(self._nfe("400001")) == []

    def test_tributado_000_com_cbs_sem_finding(self):
        assert self._find(self._nfe("000001", pcbs="0.9")) == []

    def test_imune_410_com_ibs_declarado_fatal(self):
        f = self._find(self._nfe("410001", pibsuf="0.05"))
        assert any(x.id == "F_ALIQUOTA_CLASSTRIB_IBS" for x in f)

    def test_reducao_100_com_cbs_fatal(self):
        f = self._find(self._nfe("200001", pcbs="0.9"))
        assert any(x.id == "F_ALIQUOTA_CLASSTRIB_CBS" for x in f)

    def test_codigo_desconhecido_sem_finding(self):
        assert self._find(self._nfe("999999", pcbs="0.9")) == []


class TestAliquotaAbsoluta:
    """#278 fase 2 — pCBS/pIBS declarados vs referência 2026 × (1−redução). ALERT advisory
    (não FATAL): regimes monofásico/específico não derivam ad-valorem. Só emissão 2026."""

    def _nfe(self, code, pcbs="0", pibsuf="0", pibsmun="0", dhemi="2026-06-15"):
        return (
            '<nfeProc><NFe><infNFe><ide><mod>55</mod>'
            f'<dhEmi>{dhemi}T10:00:00-03:00</dhEmi></ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            '<det nItem="1"><prod><NCM>84713012</NCM><vProd>1000.00</vProd></prod>'
            f'<imposto><IBSCBS><CST>000</CST><cClassTrib>{code}</cClassTrib>'
            '<gIBSCBS><vBC>1000.00</vBC>'
            f'<gIBSUF><pIBSUF>{pibsuf}</pIBSUF><vIBSUF>0.00</vIBSUF></gIBSUF>'
            f'<gIBSMun><pIBSMun>{pibsmun}</pIBSMun><vIBSMun>0.00</vIBSMun></gIBSMun>'
            f'<vIBS>0.00</vIBS><gCBS><pCBS>{pcbs}</pCBS><vCBS>0.00</vCBS></gCBS>'
            '</gIBSCBS></IBSCBS></imposto></det>'
            '</infNFe></NFe></nfeProc>'
        )

    def _abs(self, xml):
        return [f for f in validate_xml(xml, "NFE").findings
                if f.rule_id == "ALIQUOTA_CLASSTRIB" and "ABS" in f.id]

    def test_aliquotas_corretas_sem_alerta(self):
        # 000001 (sem redução): CBS 0,9% / IBS total 0,1%
        assert self._abs(self._nfe("000001", pcbs="0.9", pibsuf="0.05", pibsmun="0.05")) == []

    def test_cbs_divergente_alerta(self):
        # exemplo da issue: padrão 0,9% declarado como 0,1%
        f = self._abs(self._nfe("000001", pcbs="0.1", pibsuf="0.05", pibsmun="0.05"))
        assert any(x.id == "F_ALIQUOTA_CLASSTRIB_ABS_CBS" and x.severity == "ALERT" for x in f)

    def test_ibs_divergente_alerta(self):
        f = self._abs(self._nfe("000001", pcbs="0.9", pibsuf="0", pibsmun="0"))
        assert any(x.id == "F_ALIQUOTA_CLASSTRIB_ABS_IBS" and x.severity == "ALERT" for x in f)

    def test_reducao_60_correta_sem_alerta(self):
        # 011001 (redução 60%): CBS 0,36% / IBS total 0,04%
        assert self._abs(self._nfe("011001", pcbs="0.36", pibsuf="0.02", pibsmun="0.02")) == []

    def test_reducao_60_ignorada_alerta(self):
        # declarou a alíquota cheia ignorando a redução → diverge
        f = self._abs(self._nfe("011001", pcbs="0.9", pibsuf="0.02", pibsmun="0.02"))
        assert any(x.id == "F_ALIQUOTA_CLASSTRIB_ABS_CBS" for x in f)

    def test_fora_de_2026_nao_dispara(self):
        assert self._abs(self._nfe("000001", pcbs="0.1", pibsuf="0", pibsmun="0", dhemi="2027-01-15")) == []

    def test_zero_rate_nao_emite_absoluto(self):
        # 400001 (isento) é tratado pela fase 1 (zero), não pela comparação absoluta
        assert self._abs(self._nfe("400001", pcbs="0.9", pibsuf="0.05", pibsmun="0.05")) == []


class TestAliquotaUnidadePercentual:
    """#617 — pCBS/pIBSUF/pIBSMun são PONTOS PERCENTUAIS, não fração.

    Leiaute 3v2-4 da NT 2025.002-RTC: `pCBS=0.9000` é 0,9%, logo vBC=1000,00 →
    vCBS=9,00. O motor cobrava `base × alíquota` e reprovava com FATAL toda nota
    corretamente preenchida — "esperado R$ 900,00" para um vCBS legítimo de
    R$ 9,00. Estes casos falham se a divisão por 100 for removida.
    """

    def _nfe(self, pcbs="0.9000", vcbs="9.00", pibsuf="0.1000", vibsuf="1.00"):
        return (
            '<nfeProc><NFe><infNFe><ide><mod>55</mod>'
            '<dhEmi>2026-06-15T10:00:00-03:00</dhEmi></ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            '<det nItem="1"><prod><NCM>84713012</NCM><CEST>2104900</CEST>'
            '<vProd>1000.00</vProd></prod>'
            '<imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib>'
            '<gIBSCBS><vBC>1000.00</vBC>'
            f'<gIBSUF><pIBSUF>{pibsuf}</pIBSUF><vIBSUF>{vibsuf}</vIBSUF></gIBSUF>'
            '<gIBSMun><pIBSMun>0.0000</pIBSMun><vIBSMun>0.00</vIBSMun></gIBSMun>'
            f'<vIBS>{vibsuf}</vIBS><gCBS><pCBS>{pcbs}</pCBS><vCBS>{vcbs}</vCBS></gCBS>'
            '</gIBSCBS></IBSCBS></imposto></det>'
            f'<total><IBSCBSTot><vIBS>{vibsuf}</vIBS><vCBS>{vcbs}</vCBS></IBSCBSTot></total>'
            '</infNFe></NFe></nfeProc>'
        )

    def _calc(self, xml):
        return [f for f in validate_xml(xml, "NFE").findings
                if f.rule_id in ("IBSCBS_CALC", "IBSCBS_UF_CALC", "IBSCBS_MUN_CALC")]

    def test_nota_da_nt_nao_gera_finding(self):
        # Exemplo de referência do leiaute: 1000,00 a 0,9% → 9,00; a 0,1% → 1,00.
        assert self._calc(self._nfe()) == []

    def test_aliquota_como_fracao_e_reprovada(self):
        # Convenção antiga (0.0090 = 0,009%) com vCBS de 0,9% → incoerente.
        f = self._calc(self._nfe(pcbs="0.0090", pibsuf="0.0010"))
        assert any(x.id == "F_IBSCBS_CALC_CBS" and x.severity == "FATAL" for x in f)

    def test_valor_calculado_pela_formula_antiga_e_reprovado(self):
        # vCBS=900,00 era o "esperado" do motor antigo para vBC=1000,00 a 0,9%.
        f = self._calc(self._nfe(vcbs="900.00"))
        assert any(x.id == "F_IBSCBS_CALC_CBS" for x in f)
        assert any("9.00" in x.title for x in f)


class TestCredPres:
    """#339 — crédito presumido (cCredPres) coerente com o cClassTrib (fonte SVRS).
    Só alguns cClassTrib admitem (IndPermiteCredPres): 000003/000004/410014/410016."""

    def _nfe(self, code, ccredpres=None):
        ccp = f"<cCredPres>{ccredpres}</cCredPres>" if ccredpres is not None else ""
        return (
            '<nfeProc><NFe><infNFe><ide><mod>55</mod></ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            '<det nItem="1"><prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>'
            f'<imposto><IBSCBS><CST>000</CST><cClassTrib>{code}</cClassTrib>{ccp}'
            '<gIBSCBS><vBC>1000.00</vBC>'
            '<gIBSUF><pIBSUF>0</pIBSUF><vIBSUF>0.00</vIBSUF></gIBSUF>'
            '<gIBSMun><pIBSMun>0</pIBSMun><vIBSMun>0.00</vIBSMun></gIBSMun>'
            '<vIBS>0.00</vIBS><gCBS><pCBS>0</pCBS><vCBS>0.00</vCBS></gCBS>'
            '</gIBSCBS></IBSCBS></imposto></det>'
            '<total><IBSCBSTot><vIBS>0.00</vIBS><vCBS>0.00</vCBS></IBSCBSTot></total>'
            '</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml):
        return [f for f in validate_xml(xml, "NFE").findings if f.rule_id == "CRED_PRES"]

    def test_permite_sem_ccredpres_warning(self):
        # 000003 admite crédito presumido; sem cCredPres → WARNING (risco de perda do crédito)
        f = self._find(self._nfe("000003"))
        assert any(x.id == "F_CREDPRES_MISSING" and x.severity == "WARNING" for x in f)

    def test_permite_com_ccredpres_sem_finding(self):
        assert self._find(self._nfe("000003", "100001")) == []

    def test_ccredpres_formato_invalido_alert(self):
        f = self._find(self._nfe("000003", "12"))
        assert any(x.id == "F_CREDPRES_INVALID" and x.severity == "ALERT" for x in f)

    def test_ccredpres_em_classtrib_que_nao_permite_alert(self):
        # 000001 não admite crédito presumido; cCredPres informado → ALERT (inconsistência)
        f = self._find(self._nfe("000001", "100001"))
        assert any(x.id == "F_CREDPRES_INCONSISTENT" and x.severity == "ALERT" for x in f)

    def test_nao_permite_sem_ccredpres_sem_finding(self):
        assert self._find(self._nfe("000001")) == []

    def test_classtrib_desconhecido_sem_finding(self):
        assert self._find(self._nfe("999999")) == []


class TestClassTribDocType:
    """#311 — cClassTrib deve ser aplicável ao modelo do documento (fonte SVRS dfe_allowed).
    Usar um cClassTrib fora dos seus modelos publicados tende à rejeição (família 1106/960)."""

    def _nfe(self, code, mod="55"):
        return (
            f'<nfeProc><NFe><infNFe><ide><mod>{mod}</mod></ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            '<det nItem="1"><prod><NCM>84713012</NCM><vProd>1000.00</vProd></prod>'
            f'<imposto><IBSCBS><CST>000</CST><cClassTrib>{code}</cClassTrib>'
            '<gIBSCBS><vBC>1000.00</vBC>'
            '<gIBSUF><pIBSUF>0</pIBSUF><vIBSUF>0.00</vIBSUF></gIBSUF>'
            '<gIBSMun><pIBSMun>0</pIBSMun><vIBSMun>0.00</vIBSMun></gIBSMun>'
            '<vIBS>0.00</vIBS><gCBS><pCBS>0</pCBS><vCBS>0.00</vCBS></gCBS>'
            '</gIBSCBS></IBSCBS></imposto></det>'
            '<total><IBSCBSTot><vIBS>0.00</vIBS><vCBS>0.00</vCBS></IBSCBSTot></total>'
            '</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml, dt):
        return [f for f in validate_xml(xml, dt).findings if f.rule_id == "CLASSTRIB_DOC_TYPE"]

    def test_classtrib_de_outro_modelo_em_nfe_warning(self):
        # 000002 só vale p/ NFSVIA → em NF-e gera WARNING
        f = self._find(self._nfe("000002"), "NFE")
        assert any(x.id == "F_CLASSTRIB_DOC_TYPE" and x.severity == "WARNING" for x in f)

    def test_classtrib_universal_em_nfe_sem_finding(self):
        # 000001 vale p/ NFE e NFCE → sem finding
        assert self._find(self._nfe("000001"), "NFE") == []

    def test_classtrib_nfe_only_em_nfce_warning(self):
        # 000003 só vale p/ NFE → em NFC-e gera WARNING
        assert any(x.id == "F_CLASSTRIB_DOC_TYPE" for x in self._find(self._nfe("000003", mod="65"), "NFCE"))

    def test_classtrib_nfe_only_em_nfe_sem_finding(self):
        assert self._find(self._nfe("000003"), "NFE") == []

    def test_desconhecido_sem_finding(self):
        assert self._find(self._nfe("999999"), "NFE") == []

    # ── #680 — código publicado para NENHUM DFe ───────────────────────────────
    # A fonte SVRS traz, nesses códigos, as 14 chaves IndNfe/IndNfce/IndNfse/…
    # todas PRESENTES e todas false. É declaração explícita de inaplicabilidade,
    # não ausência de informação — verificado contra a fonte em 26/08/2026.

    def test_classtrib_sem_nenhum_dfe_em_nfe_warning(self):
        """410037 tem dfe_allowed=[] — antes passava calado em qualquer modelo."""
        f = self._find(self._nfe("410037"), "NFE")
        assert any(x.id == "F_CLASSTRIB_DOC_TYPE" and x.severity == "WARNING" for x in f)
        assert "sem nenhum modelo de DF-e habilitado" in f[0].title
        assert "válido para: " not in f[0].title, "lista vazia não pode virar texto quebrado"

    def test_texto_nao_atribui_fluxo_que_a_fonte_nao_declara(self):
        """A tabela diz que nenhum indicador está habilitado — não diz o destino.

        Atribuir esses códigos a "importação/DUIMP" seria inferência: dos 10, há
        planos de saúde, resseguro e ouro como ativo financeiro. O texto tem de
        parar onde a evidência para.
        """
        f = self._find(self._nfe("410037"), "NFE")
        texto = f"{f[0].title} {f[0].recommendation}"
        for termo in ("DUIMP", "importação", "importacao"):
            assert termo not in texto, f"texto atribui fluxo não declarado pela fonte: {termo}"
        assert "indicadores de modelo de DF-e avaliados desabilitados" in f[0].recommendation

    def test_classtrib_sem_nenhum_dfe_tambem_em_nfce(self):
        """Não é específico da NF-e: nenhum modelo aceita."""
        assert any(x.id == "F_CLASSTRIB_DOC_TYPE"
                   for x in self._find(self._nfe("011002", mod="65"), "NFCE"))

    def test_positivo_conhecido_segue_silencioso(self):
        """Guard contra excesso de zelo: o caso válido não pode passar a alertar."""
        assert self._find(self._nfe("000001"), "NFE") == []

    def test_desconhecido_continua_sem_finding_apos_680(self):
        """`None` (desconhecido) e `[]` (nenhum DFe) não podem voltar a colapsar."""
        assert self._find(self._nfe("999999"), "NFE") == []


class TestDevolucaoDFeRef:
    """#312 — NF-e de devolução (finNFe=4) referencia a nota original por item via
    DFeReferenciado. WARNING até 31/08/2026; FATAL a partir de 01/09/2026 (Rej. 321)."""

    def _nfe(self, fin="4", dhemi="2026-09-15", n_items=1, n_ref=0):
        dets = "".join(
            f'<det nItem="{i + 1}"><prod><NCM>84713012</NCM><vProd>10.00</vProd></prod></det>'
            for i in range(n_items)
        )
        refs = "".join(
            '<DFeReferenciado><refNFe>35260612345678000195550010000000011000000017</refNFe></DFeReferenciado>'
            for _ in range(n_ref)
        )
        return (
            f'<nfeProc><NFe><infNFe><ide><mod>55</mod><finNFe>{fin}</finNFe>'
            f'<dhEmi>{dhemi}T10:00:00-03:00</dhEmi></ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            f'{refs}{dets}'
            '</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml, **kw):
        return [f for f in validate_xml(xml, "NFE", **kw).findings if f.rule_id == "DEVOLUCAO_DFEREF"]

    def test_sem_ref_apos_vigencia_fatal(self):
        f = self._find(self._nfe(dhemi="2026-09-15", n_ref=0))
        assert any(x.id == "F_DEVOLUCAO_DFEREF" and x.severity == "FATAL" for x in f)

    def test_sem_ref_antes_vigencia_warning(self):
        f = self._find(self._nfe(dhemi="2026-08-15", n_ref=0))
        assert f and all(x.severity == "WARNING" for x in f)

    def test_com_ref_por_item_sem_finding(self):
        assert self._find(self._nfe(n_items=2, n_ref=2)) == []

    def test_ref_parcial_gera_finding(self):
        f = self._find(self._nfe(n_items=2, n_ref=1))
        assert any(x.id == "F_DEVOLUCAO_DFEREF" for x in f)

    def test_nao_devolucao_sem_finding(self):
        assert self._find(self._nfe(fin="1", n_ref=0)) == []

    def test_pedagogical_mantem_warning(self):
        f = self._find(self._nfe(dhemi="2026-09-15", n_ref=0), pedagogical_mode=True)
        assert f and all(x.severity == "WARNING" for x in f)


class TestImpostoSeletivo:
    """#314 — Imposto Seletivo: coerência do grupo IS (IS_CALC) + advertência de NCM
    sujeito sem grupo IS (IS_EXPECTED, cap. 22 bebidas / 24 fumo, vigência 2027)."""

    def _nfe(self, ncm="22030000", vbcis=None, pis=None, vis=None, pespec=None, qtrib=None):
        is_grp = ""
        if vis is not None:
            fields = ""
            if vbcis is not None:
                fields += f"<vBCIS>{vbcis}</vBCIS>"
            if pis is not None:
                fields += f"<pIS>{pis}</pIS>"
            if pespec is not None:
                fields += f"<pISEspec>{pespec}</pISEspec>"
            if qtrib is not None:
                fields += f"<qTrib>{qtrib}</qTrib>"
            fields += f"<vIS>{vis}</vIS>"
            is_grp = f"<IS><CSTIS>01</CSTIS><cClassTribIS>000001</cClassTribIS><gIS>{fields}</gIS></IS>"
        return (
            '<nfeProc><NFe><infNFe><ide><mod>55</mod></ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            f'<det nItem="1"><prod><NCM>{ncm}</NCM><vProd>1000.00</vProd></prod>'
            f'<imposto>{is_grp}</imposto></det>'
            '</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml, rule):
        return [f for f in validate_xml(xml, "NFE").findings if f.rule_id == rule]

    def test_is_advalorem_coerente_sem_finding(self):
        assert self._find(self._nfe(vbcis="1000.00", pis="0.1000", vis="100.00"), "IS_CALC") == []

    def test_is_advalorem_incoerente_fatal(self):
        f = self._find(self._nfe(vbcis="1000.00", pis="0.1000", vis="50.00"), "IS_CALC")
        assert any(x.id == "F_IS_CALC" and x.severity == "FATAL" for x in f)

    def test_is_especifico_coerente_sem_finding(self):
        # vIS = qTrib × pISEspec = 100 × 0,50 = 50,00
        assert self._find(self._nfe(qtrib="100", pespec="0.50", vis="50.00"), "IS_CALC") == []

    def test_ncm_bebida_sem_is_alerta(self):
        f = self._find(self._nfe(ncm="22030000"), "IS_EXPECTED")
        assert any(x.id == "F_IS_EXPECTED" and x.severity == "ALERT" for x in f)

    def test_ncm_fumo_sem_is_alerta(self):
        assert any(x.id == "F_IS_EXPECTED" for x in self._find(self._nfe(ncm="24022000"), "IS_EXPECTED"))

    def test_ncm_nao_sujeito_sem_finding(self):
        assert self._find(self._nfe(ncm="84713012"), "IS_EXPECTED") == []

    def test_ncm_sujeito_com_is_nao_alerta(self):
        # grupo IS presente → IS_EXPECTED não dispara
        assert self._find(self._nfe(ncm="22030000", vbcis="1000.00", pis="0.1000", vis="100.00"), "IS_EXPECTED") == []


class TestSuframaAlczfm:
    """#311 — SUFRAMA_DV (C22-20: DV da Inscrição SUFRAMA do emitente) +
    ALCZFM_NPROC (UB66c-10: grupo gALCZFMCBS exige nProcSuframa)."""

    def _nfe(self, isuf=None, alczfm=None):
        emit_extra = f"<ISUFemit>{isuf}</ISUFemit>" if isuf is not None else ""
        imp = alczfm if alczfm is not None else ""
        return (
            '<nfeProc><NFe><infNFe><ide><mod>55</mod></ide>'
            f'<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT>{emit_extra}</emit>'
            '<det nItem="1"><prod><NCM>84713012</NCM><vProd>1000.00</vProd></prod>'
            f'<imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib>{imp}</IBSCBS></imposto></det>'
            '</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml, rule):
        return [f for f in validate_xml(xml, "NFE").findings if f.rule_id == rule]

    def test_suframa_dv_valido_sem_finding(self):
        assert self._find(self._nfe(isuf="100123457"), "SUFRAMA_DV") == []

    def test_suframa_dv_invalido_warning(self):
        f = self._find(self._nfe(isuf="100123450"), "SUFRAMA_DV")
        assert any(x.id == "F_SUFRAMA_DV" and x.severity == "WARNING" for x in f)

    def test_suframa_malformado_warning(self):
        assert any(x.id == "F_SUFRAMA_DV" for x in self._find(self._nfe(isuf="12345"), "SUFRAMA_DV"))

    def test_sem_suframa_sem_finding(self):
        assert self._find(self._nfe(), "SUFRAMA_DV") == []

    def test_alczfm_com_nproc_sem_finding(self):
        xml = self._nfe(alczfm="<gALCZFMCBS><nProcSuframa>1234567890</nProcSuframa></gALCZFMCBS>")
        assert self._find(xml, "ALCZFM_NPROC") == []

    def test_alczfm_sem_nproc_warning(self):
        xml = self._nfe(alczfm="<gALCZFMCBS><vCBS>0.00</vCBS></gALCZFMCBS>")
        f = self._find(xml, "ALCZFM_NPROC")
        assert any(x.id == "F_ALCZFM_NPROC" and x.severity == "WARNING" for x in f)

    def test_sem_grupo_alczfm_sem_finding(self):
        assert self._find(self._nfe(), "ALCZFM_NPROC") == []


class TestCindopNfce:
    """#311 — B25d: cIndOp (Código Indicador do Local da Operação) não é permitido em NFC-e."""

    def _doc(self, mod, with_cindop):
        c = "<cIndOp>010104</cIndOp>" if with_cindop else ""
        return (
            f'<nfeProc><NFe><infNFe><ide><mod>{mod}</mod></ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            f'<det nItem="1"><prod><NCM>84713012</NCM>{c}<vProd>10.00</vProd></prod>'
            '<imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib></IBSCBS></imposto></det>'
            '</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml, dt):
        return [f for f in validate_xml(xml, dt).findings if f.rule_id == "CINDOP_NFCE"]

    def test_cindop_em_nfce_warning(self):
        f = self._find(self._doc("65", True), "NFCE")
        assert any(x.id == "F_CINDOP_NFCE" and x.severity == "WARNING" for x in f)

    def test_cindop_em_nfe_sem_finding(self):
        assert self._find(self._doc("55", True), "NFE") == []

    def test_nfce_sem_cindop_sem_finding(self):
        assert self._find(self._doc("65", False), "NFCE") == []


class TestB25d30Ub66e:
    """#311 — B25d-30 (Rej. 1110: cIndOp 010104/010105 exige Local de Retirada) +
    UB66e-10 (Rej. 1218: vTribRegCBS = vBC × pAliqEfetRegCBS/100 na operação ALC/ZFM)."""

    def _nfe(self, cindop=None, retirada=False, alc="", vbc="1000.00"):
        cind = f"<cIndOp>{cindop}</cIndOp>" if cindop else ""
        ret = "<retirada><xLgr>Rua X</xLgr></retirada>" if retirada else ""
        return (
            '<nfeProc><NFe><infNFe><ide><mod>55</mod></ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            f'{cind}{ret}'
            '<det nItem="1"><prod><NCM>84713012</NCM><vProd>1000.00</vProd></prod>'
            f'<imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib>'
            f'<gIBSCBS><vBC>{vbc}</vBC></gIBSCBS>{alc}</IBSCBS></imposto></det>'
            '</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml, rule):
        return [f for f in validate_xml(xml, "NFE").findings if f.rule_id == rule]

    # B25d-30
    def test_cindop_sem_retirada_warning(self):
        f = self._find(self._nfe(cindop="010104", retirada=False), "RETIRADA_CINDOP")
        assert any(x.id == "F_RETIRADA_CINDOP" and x.severity == "WARNING" for x in f)

    def test_cindop_com_retirada_sem_finding(self):
        assert self._find(self._nfe(cindop="010105", retirada=True), "RETIRADA_CINDOP") == []

    def test_cindop_outro_valor_sem_finding(self):
        assert self._find(self._nfe(cindop="000000", retirada=False), "RETIRADA_CINDOP") == []

    # UB66e-10
    _ALC = "<gALCZFMCBS><tpALCZFMCBS>2</tpALCZFMCBS><nProcSuframa>1234567890</nProcSuframa><pAliqEfetRegCBS>8.80</pAliqEfetRegCBS><vTribRegCBS>{v}</vTribRegCBS></gALCZFMCBS>"

    def test_alczfm_cbs_coerente_sem_finding(self):
        # 1000 × 8.80/100 = 88.00
        xml = self._nfe(alc=self._ALC.format(v="88.00"))
        assert self._find(xml, "ALCZFM_CBS_CALC") == []

    def test_alczfm_cbs_incoerente_warning(self):
        xml = self._nfe(alc=self._ALC.format(v="50.00"))
        f = self._find(xml, "ALCZFM_CBS_CALC")
        assert any(x.id == "F_ALCZFM_CBS_CALC" and x.severity == "WARNING" for x in f)


class TestClasstribCstCompat:
    """Rejeição 1024 (UB14-20): cClassTrib incompatível com o CST declarado.
    Carro-chefe — cada cClassTrib é registrado sob um CST oficial (SVRS)."""

    def _nfe(self, code, cst):
        return (
            '<nfeProc><NFe><infNFe><ide><mod>55</mod></ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            '<det nItem="1"><prod><NCM>84713012</NCM><vProd>1000.00</vProd></prod>'
            f'<imposto><IBSCBS><CST>{cst}</CST><cClassTrib>{code}</cClassTrib>'
            '<gIBSCBS><vBC>1000.00</vBC></gIBSCBS></IBSCBS></imposto></det>'
            '</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml):
        return [f for f in validate_xml(xml, "NFE").findings if f.rule_id == "CLASSTRIB_CST_COMPAT"]

    def test_cst_compativel_sem_finding(self):
        # 000001 é registrado sob CST 000
        assert self._find(self._nfe("000001", "000")) == []

    def test_cst_incompativel_fatal(self):
        f = self._find(self._nfe("000001", "200"))
        assert any(x.id == "F_CLASSTRIB_CST_COMPAT" and x.severity == "FATAL" for x in f)

    def test_outro_classtrib_compativel_sem_finding(self):
        assert self._find(self._nfe("200001", "200")) == []

    def test_classtrib_desconhecido_sem_finding(self):
        assert self._find(self._nfe("999999", "000")) == []


class TestMonofasicoGrupoUB:
    """Grupo UB84 (gIBSCBSMono) — subgrupos exigidos pelo cClassTrib, NT 2025.002 v1.50 (#404).

    Códigos reais confirmados ao vivo na fonte SVRS (2026-07-18): 620004 exige
    gMonoRet (mono_retido_anteriormente), 620003 exige gMonoDif (mono_diferimento);
    620001 não exige nenhum subgrupo (caso "padrão", fora de escopo desta entrega).
    Vigência: FATAL a partir de 04/01/2027; antes disso, WARNING (antecipação).
    """

    def _nfe(self, code, cst="620", grupo_extra="", dh_emi="2026-06-01T10:00:00-03:00"):
        return (
            f'<nfeProc><NFe><infNFe><ide><mod>55</mod><dhEmi>{dh_emi}</dhEmi></ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            '<det nItem="1"><prod><NCM>27101259</NCM><vProd>1000.00</vProd></prod>'
            f'<imposto><IBSCBS><CST>{cst}</CST><cClassTrib>{code}</cClassTrib>'
            f'<gIBSCBS><vBC>1000.00</vBC></gIBSCBS>{grupo_extra}</IBSCBS></imposto></det>'
            '</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml):
        return [f for f in validate_xml(xml, "NFE").findings if f.rule_id == "MONOFASICO_GRUPO_UB"]

    def test_caminho_feliz_gmonoret_presente_sem_finding(self):
        xml = self._nfe("620004", grupo_extra="<gMonoRet><qBCMonoRet>500.00</qBCMonoRet></gMonoRet>")
        assert self._find(xml) == []

    def test_erro_gmonoret_ausente_warning_antes_da_vigencia(self):
        xml = self._nfe("620004")  # exige gMonoRet, não presente
        f = self._find(xml)
        assert any(x.id == "F_MONOFASICO_GRUPO_UB_GMONORET" and x.severity == "WARNING" for x in f)

    def test_erro_gmonodif_ausente_warning_antes_da_vigencia(self):
        xml = self._nfe("620003")  # exige gMonoDif, não presente
        f = self._find(xml)
        assert any(x.id == "F_MONOFASICO_GRUPO_UB_GMONODIF" and x.severity == "WARNING" for x in f)

    def test_codigo_sem_exigencia_de_subgrupo_sem_finding(self):
        # 620001 (própria) não ativa nenhum indicador mono_* — nenhum grupo exigido.
        assert self._find(self._nfe("620001")) == []

    def test_apos_vigencia_severidade_fatal(self):
        xml = self._nfe("620004", dh_emi="2027-02-01T10:00:00-03:00")
        f = self._find(xml)
        assert any(x.id == "F_MONOFASICO_GRUPO_UB_GMONORET" and x.severity == "FATAL" for x in f)

    def test_classtrib_desconhecido_sem_finding(self):
        assert self._find(self._nfe("999999")) == []


class TestDanfeSimplificadoTipo2:
    """DANFE Simplificado Tipo 2 (tpImp=6) — NT 2026.002 v1.00, fase 2 (#405).

    Modelo 55 (NF-e) apenas — Ajuste SINIEF 13/2026. Restrito a saída (tpNF≠0),
    operação interna (idDest=1), sem NFref e finalidade Normal (finNFe=1).
    Vigência produção 03/08/2026: WARNING antes, FATAL depois (pedagogical_mode
    mantém WARNING). Códigos de rejeição confirmados por múltiplas fontes
    independentes (tecnospeed, contabeis.com.br, lopesmachado — 2026-07-18):
    706 (B11-10), 707 (B11a-10), 708 (BA01-10), 715 (B25-20).

    5ª restrição — allowlist de CFOP (DANFE_SIMPLIFICADO_CFOP, #482, 2026-07-20):
    725 (I08-150), mesmo código de "CFOP inválido" já usado pela Rejeição 725
    de NFC-e, reaproveitado para NF-e+tpImp=6.
    """

    def _nfe(self, tp_imp="6", tp_nf="1", id_dest="1", fin_nfe="1", nfref=False, dh_emi="2026-06-01T10:00:00-03:00", mod="55", cfop="5102"):
        ref = '<NFref><refNFe>35260612345678000195550010000000011000000017</refNFe></NFref>' if nfref else ""
        return (
            f'<nfeProc><NFe><infNFe><ide><mod>{mod}</mod><tpImp>{tp_imp}</tpImp><tpNF>{tp_nf}</tpNF>'
            f'<idDest>{id_dest}</idDest><finNFe>{fin_nfe}</finNFe><dhEmi>{dh_emi}</dhEmi>{ref}</ide>'
            '<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>'
            f'<det nItem="1"><prod><CFOP>{cfop}</CFOP><NCM>84713012</NCM><vProd>10.00</vProd></prod></det>'
            '</infNFe></NFe></nfeProc>'
        )

    def _find(self, xml, dt="NFE", **kw):
        return [f for f in validate_xml(xml, dt, **kw).findings if f.rule_id == "DANFE_SIMPLIFICADO_RESTRICAO"]

    def _find_cfop(self, xml, dt="NFE", **kw):
        return [f for f in validate_xml(xml, dt, **kw).findings if f.rule_id == "DANFE_SIMPLIFICADO_CFOP"]

    def test_compliant_saida_interna_sem_finding(self):
        assert self._find(self._nfe()) == []

    def test_compliant_nao_presencial_sem_finding(self):
        # indPres não é checado por esta regra — só as 4 restrições estruturais.
        assert self._find(self._nfe(tp_nf="1", id_dest="1", fin_nfe="1")) == []

    def test_entrada_rejeitada(self):
        f = self._find(self._nfe(tp_nf="0"))
        assert any(x.id == "F_DANFE_T2_ENTRADA" and "706" in x.recommendation for x in f)

    def test_interestadual_rejeitada(self):
        f = self._find(self._nfe(id_dest="2"))
        assert any(x.id == "F_DANFE_T2_INTERESTADUAL" and "707" in x.recommendation for x in f)

    def test_nfref_rejeitada(self):
        f = self._find(self._nfe(nfref=True))
        assert any(x.id == "F_DANFE_T2_NFREF" and "708" in x.recommendation for x in f)

    def test_finalidade_nao_normal_rejeitada(self):
        f = self._find(self._nfe(fin_nfe="2"))
        assert any(x.id == "F_DANFE_T2_FINALIDADE" and "715" in x.recommendation for x in f)

    def test_tpimp_diferente_de_6_sem_finding(self):
        assert self._find(self._nfe(tp_imp="1", tp_nf="0", id_dest="2", nfref=True, fin_nfe="2")) == []

    def test_nfce_nao_se_aplica(self):
        # DANFE Simplificado Tipo 2 é exclusivo do modelo 55 — NFC-e (modelo 65) fora de escopo.
        assert self._find(self._nfe(tp_nf="0", mod="65"), dt="NFCE") == []

    def test_antes_da_vigencia_warning(self):
        f = self._find(self._nfe(tp_nf="0", dh_emi="2026-07-15T10:00:00-03:00"))
        assert f and all(x.severity == "WARNING" for x in f)

    def test_apos_vigencia_fatal(self):
        f = self._find(self._nfe(tp_nf="0", dh_emi="2026-08-10T10:00:00-03:00"))
        assert any(x.id == "F_DANFE_T2_ENTRADA" and x.severity == "FATAL" for x in f)

    def test_pedagogical_mantem_warning(self):
        f = self._find(self._nfe(tp_nf="0", dh_emi="2026-08-10T10:00:00-03:00"), pedagogical_mode=True)
        assert f and all(x.severity == "WARNING" for x in f)

    def test_multiplas_violacoes_geram_multiplos_findings(self):
        f = self._find(self._nfe(tp_nf="0", id_dest="2", nfref=True, fin_nfe="4"))
        ids = {x.id for x in f}
        assert ids == {"F_DANFE_T2_ENTRADA", "F_DANFE_T2_INTERESTADUAL", "F_DANFE_T2_NFREF", "F_DANFE_T2_FINALIDADE"}

    # ── DANFE_SIMPLIFICADO_CFOP — allowlist de CFOP (NT 2026.002 v1.00, #482) ──
    # Regra I08-150 — Rejeição 725 (mesmo código já usado pela SEFAZ para "NFC-e com
    # CFOP inválido", reaproveitado para NF-e+tpImp=6). Confirmado via fórum SPED
    # Brasil + doc. Senior (2026-07-20).

    def test_cfop_permitido_sem_finding(self):
        assert self._find_cfop(self._nfe(cfop="5102")) == []

    def test_cfop_fora_do_allowlist_rejeitado(self):
        f = self._find_cfop(self._nfe(cfop="5949"))
        assert any(x.id == "F_DANFE_T2_CFOP" and "725" in x.recommendation and "5949" in x.title for x in f)

    def test_cfop_5910_permitido(self):
        # 5910 é o único CFOP extra do allowlist do DANFE T2 em relação ao allowlist
        # pré-existente da Rejeição 725 de NFC-e.
        assert self._find_cfop(self._nfe(cfop="5910")) == []

    def test_cfop_tpimp_diferente_de_6_sem_finding(self):
        assert self._find_cfop(self._nfe(tp_imp="1", cfop="5949")) == []

    def test_cfop_antes_da_vigencia_warning(self):
        f = self._find_cfop(self._nfe(cfop="5949", dh_emi="2026-07-15T10:00:00-03:00"))
        assert f and all(x.severity == "WARNING" for x in f)

    def test_cfop_apos_vigencia_fatal(self):
        f = self._find_cfop(self._nfe(cfop="5949", dh_emi="2026-08-10T10:00:00-03:00"))
        assert any(x.id == "F_DANFE_T2_CFOP" and x.severity == "FATAL" for x in f)


# ── #403: Grupo W03 (IBSCBSTot) — NT 2025.002-RTC v1.40, W34-10/W34-20 ────────
# W34-20 → Rejeição 1119 (IBSCBSTot ausente com item IBS/CBS);
# W34-10 → Rejeição 1118 (IBSCBSTot sem nenhum item IBS/CBS);
# W56-10 → 1091 / W47-10 → 1085 (totais ≠ soma dos itens).

_W03_ITEM = """<det nItem="1">
    <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
    <imposto>
      <IBSCBS>
        <CST>000</CST>
        <cClassTrib>654321</cClassTrib>
        <gIBSCBS>
          <vBC>1000.00</vBC>
          <gIBSUF><pIBSUF>0.0500</pIBSUF><vIBSUF>0.50</vIBSUF></gIBSUF>
          <gIBSMun><pIBSMun>0.0500</pIBSMun><vIBSMun>0.50</vIBSMun></gIBSMun>
          <vIBS>1.00</vIBS>
          <gCBS><pCBS>0.9000</pCBS><vCBS>9.00</vCBS></gCBS>
        </gIBSCBS>
      </IBSCBS>
    </imposto>
  </det>"""

_W03_ITEM_SEM_IBSCBS = """<det nItem="1">
    <prod><NCM>84713012</NCM><CEST>2104900</CEST><vProd>1000.00</vProd></prod>
    <imposto><ICMS><ICMS00><CST>00</CST></ICMS00></ICMS></imposto>
  </det>"""

_W03_TOT = "<IBSCBSTot><vBCIBSCBS>1000.00</vBCIBSCBS><vIBS>1.00</vIBS><vCBS>9.00</vCBS></IBSCBSTot>"


def _nfe_w03(crt="3", dh_emi="2026-08-10T10:00:00-03:00", item=True, tot=True, tot_xml=None):
    det = _W03_ITEM if item else _W03_ITEM_SEM_IBSCBS
    total = tot_xml if tot_xml is not None else (_W03_TOT if tot else "")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod><dhEmi>{dh_emi}</dhEmi></ide>
  <emit><CNPJ>12345678000195</CNPJ><CRT>{crt}</CRT></emit>
  {det}
  <total>{total}</total>
</infNFe></NFe></nfeProc>"""


class TestW03Totals:
    def test_ibscbstot_missing_crt3_fatal_cita_1119(self):
        result = validate_xml(_nfe_w03(tot=False))
        f = [x for x in result.findings if x.rule_id == "IBSCBSTOT_MISSING"]
        assert f, "IBSCBSTOT_MISSING esperado"
        assert f[0].severity == "FATAL"
        assert "1119" in (f[0].recommendation or "")
        assert "W34-20" in (f[0].recommendation or "")

    def test_ibscbstot_missing_simples_warning(self):
        result = validate_xml(_nfe_w03(crt="1", tot=False))
        f = [x for x in result.findings if x.rule_id == "IBSCBSTOT_MISSING"]
        assert f, "IBSCBSTOT_MISSING esperado"
        assert f[0].severity == "WARNING"

    def test_ibscbstot_missing_janela_sem_penalidades_warning(self):
        result = validate_xml(_nfe_w03(dh_emi="2026-07-10T10:00:00-03:00", tot=False))
        f = [x for x in result.findings if x.rule_id == "IBSCBSTOT_MISSING"]
        assert f, "IBSCBSTOT_MISSING esperado"
        assert f[0].severity == "WARNING"
        assert "Ato Conjunto" in (f[0].recommendation or "")

    def test_ibscbstot_undue_fatal_cita_1118(self):
        result = validate_xml(_nfe_w03(item=False, tot=True))
        f = [x for x in result.findings if x.rule_id == "IBSCBSTOT_UNDUE"]
        assert f, "IBSCBSTOT_UNDUE esperado"
        assert f[0].severity == "FATAL"
        assert "1118" in (f[0].recommendation or "")

    def test_w03_coerente_sem_findings(self):
        result = validate_xml(_nfe_w03())
        rules = [x.rule_id for x in result.findings]
        assert "IBSCBSTOT_MISSING" not in rules
        assert "IBSCBSTOT_UNDUE" not in rules
        assert "IBSCBS_TOTAL" not in rules

    def test_total_cbs_divergente_fatal_cita_1091(self):
        tot = "<IBSCBSTot><vBCIBSCBS>1000.00</vBCIBSCBS><vIBS>1.00</vIBS><vCBS>99.00</vCBS></IBSCBSTot>"
        result = validate_xml(_nfe_w03(tot_xml=tot))
        f = [x for x in result.findings if x.rule_id == "IBSCBS_TOTAL"]
        assert f, "IBSCBS_TOTAL esperado (total CBS divergente da soma dos itens)"
        assert f[0].severity == "FATAL"
        assert "1091" in (f[0].recommendation or "")

    def test_total_ibs_divergente_fatal_cita_1085(self):
        tot = "<IBSCBSTot><vBCIBSCBS>1000.00</vBCIBSCBS><vIBS>5.00</vIBS><vCBS>9.00</vCBS></IBSCBSTot>"
        result = validate_xml(_nfe_w03(tot_xml=tot))
        f = [x for x in result.findings if x.rule_id == "IBSCBS_TOTAL"]
        assert f, "IBSCBS_TOTAL esperado (total IBS divergente da soma dos itens)"
        assert f[0].severity == "FATAL"
        assert "1085" in (f[0].recommendation or "")


from app.data import cfop_table as _ct  # noqa: E402

_CFOP_NEGADO = sorted(c for c in _ct.all_cfops() if _ct.ind_exc_ibscbs(c) == "0")[0]
_CFOP_PERMITIDO = sorted(_ct.cfops_permitidos_contribuinte_exclusivo())[0]


class TestI08191Integracao:
    """RV I08-191 ligada ao motor (#615, NT 2026.007 v1.00).

    O contrato da avaliação está em test_rules_i08_191. Aqui provamos só a
    fiação: o motor lê emit/IE, CFOP, finNFe e tpNFCredito do XML e produz o
    achado com a severidade correta.
    """

    NEGADO = _CFOP_NEGADO
    PERMITIDO = _CFOP_PERMITIDO

    @staticmethod
    def _nfe(cfop: str, *, ie: str = "", fin: str = "1", tp_cred: str | None = None,
             dh: str = "2026-12-01") -> str:
        ie_tag = f"<IE>{ie}</IE>" if ie else ""
        cred = f"<tpNFCredito>{tp_cred}</tpNFCredito>" if tp_cred else ""
        return (
            "<nfeProc><NFe><infNFe>"
            f"<ide><mod>55</mod><finNFe>{fin}</finNFe>{cred}<dhEmi>{dh}T10:00:00-03:00</dhEmi></ide>"
            f"<emit><CNPJ>12345678000195</CNPJ>{ie_tag}</emit>"
            f"<det nItem=\"1\"><prod><CFOP>{cfop}</CFOP><NCM>84713012</NCM></prod></det>"
            "</infNFe></NFe></nfeProc>"
        )

    def _find(self, xml: str):
        return [f for f in validate_xml(xml, "NFE").findings
                if f.rule_id == "I08_191_CFOP_EXCLUSIVO_IBSCBS"]

    def test_ie_ausente_com_cfop_negado_gera_achado_nao_fatal(self):
        """Sem autorizador comprovado o achado existe, mas NUNCA é FATAL."""
        f = self._find(self._nfe(self.NEGADO))
        assert len(f) == 1
        assert f[0].severity == "WARNING"
        assert f[0].severity != "FATAL"
        assert "APLICABILIDADE_SVRS_NAO_DETERMINADA" in f[0].title
        assert "autorizador aplicável não foi determinado" in f[0].recommendation

    def test_ie_informada_nao_gera_achado(self):
        assert self._find(self._nfe(self.NEGADO, ie="123456789")) == []

    def test_cfop_permitido_nao_gera_achado(self):
        assert self._find(self._nfe(self.PERMITIDO)) == []

    def test_excecao_devolucao_finNFe_4(self):
        assert self._find(self._nfe(self.NEGADO, fin="4")) == []

    def test_excecao_tpNFCredito_03(self):
        assert self._find(self._nfe(self.NEGADO, tp_cred="03")) == []

    def test_cfop_fora_do_dominio_oficial_nao_gera_achado(self):
        assert self._find(self._nfe("9999")) == []


# ── Ato Conjunto RFB/CGIBS nº 6/2026 — dispensa do nanoempreendedor ──────────
class TestPfContribCnpjAto6:
    """Contratos do ROUND FISCAL 29/08-K.

    A orientação passou a contemplar o Ato nº 6. O que NÃO mudou: gatilho e
    severidade. O que não pode nascer: classificação de nanoempreendedor,
    supressão do ALERT por cClassTrib, ou obrigação automática em 2029.
    """

    IDEIAS_OBRIGATORIAS = (
        ("enquadramento", "obrigação depende do enquadramento aplicável"),
        ("Ato Conjunto RFB/CGIBS nº 6/2026", "existe a dispensa do Ato nº 6"),
        ("regime regular", "a opção pelo regime regular exclui a dispensa"),
        ("31/12/2028", "a dispensa produz efeitos até 31/12/2028"),
        ("isoladamente", "o XML sozinho não determina o enquadramento"),
        ("nanoempreendedor", "a dispensa é do nanoempreendedor"),
    )

    def _nfe(self, dh, cclass="000001"):
        return (
            f'<nfeProc><NFe><infNFe><ide><mod>55</mod><dhEmi>{dh}</dhEmi></ide>'
            f'<emit><CPF>12345678909</CPF><CRT>1</CRT></emit><dest><CPF>11122233344</CPF></dest>'
            f'<det nItem="1"><prod><NCM>84713012</NCM><vProd>100.00</vProd></prod>'
            f'<imposto><IBSCBS><CST>410</CST><cClassTrib>{cclass}</cClassTrib></IBSCBS></imposto></det>'
            f'<total></total></infNFe></NFe></nfeProc>'
        )

    def _find(self, xml):
        return [f for f in validate_xml(xml, "NFE").findings if f.rule_id == "PF_CONTRIB_CNPJ"]

    def test_31_12_2026_sem_finding(self):
        assert self._find(self._nfe("2026-12-31T10:00:00-03:00")) == []

    def test_01_01_2027_alert(self):
        f = self._find(self._nfe("2027-01-01T10:00:00-03:00"))
        assert len(f) == 1 and f[0].severity == "ALERT"

    def test_31_12_2028_alert_com_orientacao_do_ato_6(self):
        f = self._find(self._nfe("2028-12-31T10:00:00-03:00"))
        assert len(f) == 1 and f[0].severity == "ALERT"
        for trecho, porque in self.IDEIAS_OBRIGATORIAS:
            assert trecho in f[0].recommendation, porque

    def test_01_01_2029_permanece_verificacao_sem_conclusao_automatica(self):
        """A expiração do Ato nº 6 não autoriza afirmar obrigação em 2029.

        O guard é ESTRUTURAL, não lista de frases: a redação aprovada não fala
        de 2029 em lugar nenhum, então QUALQUER menção a 2029 na orientação é,
        por construção, inferência que não podemos fazer. Um guard por frase
        proibida falharia em passar — a primeira versão dele checava "está
        obrigado" e deixou passar "está obrigada".
        """
        f = self._find(self._nfe("2029-01-01T10:00:00-03:00"))
        assert len(f) == 1
        assert f[0].severity == "ALERT"
        assert "Verifique o enquadramento" in f[0].recommendation
        assert "2029" not in f[0].recommendation, (
            "a orientação passou a afirmar algo sobre 2029; a expiração do Ato nº 6 "
            "não autoriza concluir obrigação — depende da legislação então vigente"
        )
        assert "2029" not in f[0].title

    def test_cclasstrib_410035_nao_suprime_o_alert(self):
        """410035 é DECLARAÇÃO do emitente compatível com nanoempreendedor.
        Não é prova de enquadramento nem de não-opção pelo regime regular."""
        f = self._find(self._nfe("2027-06-01T10:00:00-03:00", cclass="410035"))
        assert len(f) == 1 and f[0].severity == "ALERT"

    def test_severidade_nunca_e_fatal(self):
        for dh in ("2027-01-01", "2028-12-31", "2029-01-01", "2030-06-01"):
            for f in self._find(self._nfe(f"{dh}T10:00:00-03:00")):
                assert f.severity == "ALERT"
                assert f.severity != "FATAL"

    def test_ausencia_de_cnpj_nao_e_afirmada_como_irregularidade(self):
        f = self._find(self._nfe("2027-06-01T10:00:00-03:00"))[0]
        assert "verificar" in f.title.lower()
        for proibido in ("irregular", "inválido", "proibido", "vedado"):
            assert proibido not in f.recommendation.lower()

    def test_artefato_do_ato_6_esta_canonizado(self):
        import hashlib
        import pathlib as _pl

        from app.data import regulatory_acts as ra

        chave = ra.ATO_CONJUNTO_RFB_CGIBS_6_2026
        a = ra.get(chave)
        assert a is not None
        assert a["ato_date"] == "2026-08-28"
        assert a["effective_from"] == "2026-08-29"
        assert a["effective_from_semantics"] == "INTERPRETACAO_SEGURA"
        assert a["effective_until"] == "2028-12-31"
        assert a["effective_until_inclusive"] is True

        prov = ra.provenance(chave)
        assert "cgibs.gov.br" in prov.source_url
        bruto = _pl.Path(ra.__file__).parent / a["arquivo_bruto"]
        assert hashlib.sha256(bruto.read_bytes()).hexdigest() == prov.fingerprint

    def test_janela_do_ato_nao_liga_nem_desliga_comportamento(self):
        """A regra dispara igual dentro e fora da janela de efeitos do Ato."""
        from app.data import regulatory_acts as ra

        ini, fim, _ = ra.janela_de_efeitos(ra.ATO_CONJUNTO_RFB_CGIBS_6_2026)
        assert ini.isoformat() == "2026-08-29" and fim.isoformat() == "2028-12-31"
        dentro = self._find(self._nfe("2028-12-31T10:00:00-03:00"))
        fora = self._find(self._nfe("2029-01-02T10:00:00-03:00"))
        assert len(dentro) == len(fora) == 1
        assert dentro[0].severity == fora[0].severity == "ALERT"

def test_dfe_allowed_cobre_todos_os_indicadores_da_fonte():
    """#680 — `dfe_allowed` vazio só pode significar "nenhum modelo", nunca
    "modelo que o nosso mapa esqueceu".

    O mapa tinha 14 indicadores; a fonte publica 17. DERE, DIR e DUIMP ficavam
    de fora, e 6 códigos publicados para DeRE saíam com lista vazia — do ponto
    de vista do consumidor, indistinguíveis de "não vale para DFe nenhum".
    """
    from app.data.classtrib_source import DFE_INDICATORS
    from app.data.classtrib_table import CLASSTRIB_BY_CODE

    assert {"IndDere", "IndDir", "IndDuimp"} <= set(DFE_INDICATORS), (
        "indicador de modelo removido do mapa — código publicado só para ele voltaria a sair vazio"
    )

    vazios = {c for c, r in CLASSTRIB_BY_CODE.items() if r.get("dfe_allowed") == []}
    dere = {"011001", "011002", "011004", "011005", "200018", "410034"}
    assert not (dere & vazios), (
        f"códigos publicados para DeRE voltaram a ficar vazios: {sorted(dere & vazios)}"
    )
    for code in sorted(dere):
        assert "DERE" in CLASSTRIB_BY_CODE[code]["dfe_allowed"], code
