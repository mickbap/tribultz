"""Temporal NCM snapshots introduced by IT 2024.001 v2.40."""

from collections import Counter
from datetime import date

from app.data.ncm_cclasstrib_table import resolve_cclasstrib
from app.data.ncm_codes import (
    NCM_CATALOG_V230,
    NCM_CATALOG_V240,
    VALID_NCM_CODES,
    NcmDiffStatus,
    diff_ncm_catalogs,
    is_valid_ncm,
    resolve_ncm_catalog,
)
from app.data.ncm_rates import resolve_ncm_modifier
from app.routers.validate_xml import validate_xml


FUTURE_NCM = "85181020"


def _nfe(reference_date: str) -> str:
    return f"""<?xml version="1.0"?>
<nfeProc><NFe><infNFe>
  <ide><mod>55</mod><dhEmi>{reference_date}T10:00:00-03:00</dhEmi></ide>
  <det nItem="1"><prod><NCM>{FUTURE_NCM}</NCM><vProd>100.00</vProd></prod></det>
</infNFe></NFe></nfeProc>"""


def test_catalogs_record_version_provenance_validity_and_fingerprints():
    assert NCM_CATALOG_V230.version == "IT 2024.001 v2.30"
    assert NCM_CATALOG_V230.effective_to == date(2026, 9, 30)
    assert NCM_CATALOG_V240.version == "IT 2024.001 v2.40"
    assert NCM_CATALOG_V240.effective_from == date(2026, 10, 1)
    assert NCM_CATALOG_V240.effective_to is None
    assert NCM_CATALOG_V240.scope == "TRIBULTZ_CURATED_SUBSET"

    for catalog in (NCM_CATALOG_V230, NCM_CATALOG_V240):
        assert catalog.source.startswith("Portal Nacional da NF-e")
        assert catalog.source_url.startswith("https://www.nfe.fazenda.gov.br/")
        assert catalog.artifact_url.startswith("https://www.nfe.fazenda.gov.br/")
        assert len(catalog.source_sha256) == 64
        assert len(catalog.artifact_sha256) == 64
        assert len(catalog.fingerprint) == 64
    assert NCM_CATALOG_V230.fingerprint != NCM_CATALOG_V240.fingerprint


def test_v240_diff_is_the_single_official_addition():
    differences = diff_ncm_catalogs()
    counts = Counter(item.status for item in differences)

    assert counts == {
        NcmDiffStatus.ADDED: 1,
        NcmDiffStatus.UNCHANGED: len(VALID_NCM_CODES),
    }
    assert [item.code for item in differences if item.status == NcmDiffStatus.ADDED] == [
        FUTURE_NCM
    ]
    added = next(item for item in differences if item.code == FUTURE_NCM)
    assert added.previous_description is None
    assert added.next_description == "Outros microfones, sem suporte"
    assert counts[NcmDiffStatus.REMOVED] == 0
    assert counts[NcmDiffStatus.DESCRIPTION_CHANGED] == 0


def test_catalog_resolution_does_not_activate_future_version_early():
    assert FUTURE_NCM not in VALID_NCM_CODES
    assert resolve_ncm_catalog(date(2026, 9, 30)) is NCM_CATALOG_V230
    assert resolve_ncm_catalog(date(2026, 10, 1)) is NCM_CATALOG_V240
    assert not is_valid_ncm(FUTURE_NCM, date(2026, 9, 30))
    assert is_valid_ncm(FUTURE_NCM, date(2026, 10, 1))
    assert is_valid_ncm("84713012", date(2026, 9, 30))
    assert is_valid_ncm("84713012", date(2026, 10, 1))


def test_xml_validation_uses_document_reference_date():
    before = validate_xml(_nfe("2026-09-30"), "NFE")
    effective = validate_xml(_nfe("2026-10-01"), "NFE")

    assert [f.rule_id for f in before.findings].count("NCM_VALID") == 1
    assert "NCM_VALID" not in [f.rule_id for f in effective.findings]


def test_new_ncm_does_not_infer_cclasstrib_or_tax_modifier():
    determined, candidates, status = resolve_cclasstrib(FUTURE_NCM)
    modifier = resolve_ncm_modifier(FUTURE_NCM)

    assert determined is None
    assert candidates == []
    assert status == "requer_validacao"
    assert modifier.nao_determinavel
    assert modifier.fontes == ()
