"""Contrato fail-closed do registry de parametros fiscais dinamicos."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from app.services.fiscal_parameters import (
    FallbackPolicy,
    FiscalParameterDefinition,
    FiscalParameterError,
    FiscalParameterRegistry,
    FiscalParameterVersion,
    ResolutionReason,
    ResolutionStatus,
    SourceStatus,
    embedded_registry,
)


NOW = dt.datetime(2026, 9, 9, 12, tzinfo=dt.timezone.utc)
SOURCE_URL = "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm"


def _version(
    record_version: int,
    value: str | None,
    effective_from: dt.date,
    effective_to: dt.date | None = None,
    *,
    status: SourceStatus = SourceStatus.OFFICIAL_VALIDATED,
    source: str = "Presidencia da Republica",
    act: str = "Ato oficial de teste",
) -> FiscalParameterVersion:
    return FiscalParameterVersion(
        record_version=record_version,
        value=Decimal(value) if value is not None else None,
        official_source=source,
        source_url=SOURCE_URL,
        reference_act=act,
        effective_from=effective_from,
        effective_to=effective_to,
        updated_at=NOW,
        source_status=status,
        source_fingerprint="a" * 64,
    )


def _registry(*versions: FiscalParameterVersion) -> FiscalParameterRegistry:
    return FiscalParameterRegistry(
        schema_version="1.0",
        parameters=(FiscalParameterDefinition(
            identifier="PARAMETRO_FISCAL_TESTE",
            fallback=FallbackPolicy.BLOCK,
            versions=tuple(versions),
        ),),
    )


def test_registry_embarcado_nao_cadastra_regra_fiscal_nesta_ordem() -> None:
    registry = embedded_registry()
    assert registry.parameters == ()


def test_parametro_nao_cadastrado_e_indeterminado_sem_valor() -> None:
    result = embedded_registry().resolve(
        "PARAMETRO_FISCAL_INEXISTENTE", dt.date(2026, 9, 1), resolved_at=NOW
    )
    assert result.status is ResolutionStatus.INDETERMINATE
    assert result.reason is ResolutionReason.PARAMETER_NOT_REGISTERED
    assert result.value is None
    assert result.fallback is FallbackPolicy.BLOCK
    assert result.to_dict()["evidence"] == []


def test_resolve_valor_fonte_e_ato_vigentes_na_data() -> None:
    version = _version(1, "123.4500", dt.date(2026, 1, 1))
    result = _registry(version).resolve(
        "PARAMETRO_FISCAL_TESTE", dt.date(2026, 9, 1), resolved_at=NOW
    )
    assert result.status is ResolutionStatus.DETERMINED
    assert result.value == Decimal("123.4500")
    assert result.selected_record_version == 1
    assert result.evidence[0]["official_source"] == "Presidencia da Republica"
    assert result.evidence[0]["reference_act"] == "Ato oficial de teste"
    assert result.evidence[0]["identifier"] == "PARAMETRO_FISCAL_TESTE"
    assert result.evidence[0]["fallback"] == "BLOCK"
    assert result.evidence[0]["record_fingerprint"]
    assert result.to_dict()["registry_schema_version"] == "1.0"


def test_historico_e_resolvido_por_data_sem_retroatividade() -> None:
    registry = _registry(
        _version(1, "10", dt.date(2026, 1, 1), dt.date(2026, 6, 30), act="Ato v1"),
        _version(2, "20", dt.date(2026, 7, 1), act="Ato v2"),
    )
    first = registry.resolve("PARAMETRO_FISCAL_TESTE", dt.date(2026, 6, 30), resolved_at=NOW)
    second = registry.resolve("PARAMETRO_FISCAL_TESTE", dt.date(2026, 7, 1), resolved_at=NOW)
    assert (first.value, first.evidence[0]["reference_act"]) == (Decimal("10"), "Ato v1")
    assert (second.value, second.evidence[0]["reference_act"]) == (Decimal("20"), "Ato v2")


def test_versao_futura_nao_e_usada_antes_da_vigencia() -> None:
    result = _registry(_version(1, "99", dt.date(2026, 10, 1))).resolve(
        "PARAMETRO_FISCAL_TESTE", dt.date(2026, 9, 30), resolved_at=NOW
    )
    assert result.status is ResolutionStatus.INDETERMINATE
    assert result.reason is ResolutionReason.NO_VERSION_FOR_REFERENCE_DATE
    assert result.value is None
    assert result.evidence[0]["value"] == "99"


@pytest.mark.parametrize(
    "source_status",
    [
        SourceStatus.OFFICIAL_PENDING_VALIDATION,
        SourceStatus.OFFICIAL_UNVERIFIABLE,
        SourceStatus.OFFICIAL_ABSENT,
        SourceStatus.REVOKED,
    ],
)
def test_fonte_nao_validada_bloqueia_sem_expor_valor(
    source_status: SourceStatus,
) -> None:
    result = _registry(
        _version(1, None, dt.date(2026, 9, 1), status=source_status)
    ).resolve("PARAMETRO_FISCAL_TESTE", dt.date(2026, 9, 1), resolved_at=NOW)
    assert result.status is ResolutionStatus.BLOCKED
    assert result.reason is ResolutionReason.SOURCE_NOT_VALIDATED
    assert result.value is None
    assert result.fallback is FallbackPolicy.BLOCK
    assert result.evidence[0]["source_status"] == source_status.value


def test_vigencias_sobrepostas_bloqueiam_em_vez_de_escolher_mais_recente() -> None:
    result = _registry(
        _version(1, "10", dt.date(2026, 1, 1)),
        _version(2, "20", dt.date(2026, 6, 1)),
    ).resolve("PARAMETRO_FISCAL_TESTE", dt.date(2026, 9, 1), resolved_at=NOW)
    assert result.status is ResolutionStatus.BLOCKED
    assert result.reason is ResolutionReason.OVERLAPPING_VERSIONS
    assert result.value is None
    assert {item["record_version"] for item in result.evidence} == {1, 2}


def test_loader_rejeita_float_fallback_e_host_nao_oficial() -> None:
    base = {
        "schema_version": "1.0",
        "parameters": [{
            "identifier": "PARAMETRO_FISCAL_TESTE",
            "fallback": "BLOCK",
            "versions": [{
                "record_version": 1,
                "value": 1.5,
                "official_source": "Fonte",
                "source_url": SOURCE_URL,
                "reference_act": "Ato",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "updated_at": "2026-09-09T12:00:00+00:00",
                "source_status": "OFFICIAL_VALIDATED",
                "source_fingerprint": "a" * 64,
            }],
        }],
    }
    with pytest.raises(FiscalParameterError, match="string decimal"):
        FiscalParameterRegistry.from_payload(base)

    base["parameters"][0]["versions"][0]["value"] = "1.5"
    base["parameters"][0]["fallback"] = "USE_LAST_VALUE"
    with pytest.raises(FiscalParameterError, match="parameter possui"):
        FiscalParameterRegistry.from_payload(base)

    base["parameters"][0]["fallback"] = "BLOCK"
    base["parameters"][0]["versions"][0]["source_url"] = "https://example.com/ato"
    with pytest.raises(FiscalParameterError, match="host não oficial"):
        FiscalParameterRegistry.from_payload(base)


def test_fonte_validada_sem_valor_e_registry_ambiguo_falham_na_carga() -> None:
    with pytest.raises(FiscalParameterError, match="fonte validada exige value"):
        _version(1, None, dt.date(2026, 1, 1))
    with pytest.raises(FiscalParameterError, match="record_version duplicada"):
        _registry(
            _version(1, "10", dt.date(2026, 1, 1), dt.date(2026, 6, 30)),
            _version(1, "20", dt.date(2026, 7, 1)),
        )


def test_valor_nao_finito_falha_tambem_na_construcao_direta() -> None:
    with pytest.raises(FiscalParameterError, match="value deve ser finito"):
        _version(1, "NaN", dt.date(2026, 1, 1))


@pytest.mark.parametrize("record_version", [True, 1.5, "1"])
def test_loader_rejeita_versao_de_registro_nao_inteira(record_version: object) -> None:
    payload = {
        "schema_version": "1.0",
        "parameters": [{
            "identifier": "PARAMETRO_FISCAL_TESTE",
            "fallback": "BLOCK",
            "versions": [{
                "record_version": record_version,
                "value": "1.5",
                "official_source": "Fonte",
                "source_url": SOURCE_URL,
                "reference_act": "Ato",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "updated_at": "2026-09-09T12:00:00+00:00",
                "source_status": "OFFICIAL_VALIDATED",
                "source_fingerprint": "a" * 64,
            }],
        }],
    }
    with pytest.raises(FiscalParameterError, match="record_version deve ser inteiro"):
        FiscalParameterRegistry.from_payload(payload)
