"""Registry temporal de parametros fiscais dinamicos.

O registry e deliberadamente somente-leitura em runtime: atualizacoes passam
por artefato versionado, review e CI, como os demais dados regulatorios
canonicos do produto. Ele nao contem regras fiscais; apenas oferece o contrato
para que consumidores futuros resolvam um valor oficial por data de referencia.

Ausencia, fonte nao validada ou conflito de vigencia nunca selecionam um valor
anterior/futuro. O resultado e explicito e carrega evidencia serializavel para
o audit trail do consumidor.
"""

from __future__ import annotations

import datetime as dt
import functools
import json
import pathlib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from app.data.provenance import ArtifactProvenance, ProvenanceError, fingerprint_payload


_REGISTRY_FILE = pathlib.Path(__file__).parents[1] / "data" / "fiscal_parameters.json"
_IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_]{2,99}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class FiscalParameterError(ValueError):
    """Registry malformado; configuracao invalida nao pode degradar silenciosamente."""


class SourceStatus(StrEnum):
    OFFICIAL_VALIDATED = "OFFICIAL_VALIDATED"
    OFFICIAL_PENDING_VALIDATION = "OFFICIAL_PENDING_VALIDATION"
    OFFICIAL_UNVERIFIABLE = "OFFICIAL_UNVERIFIABLE"
    OFFICIAL_ABSENT = "OFFICIAL_ABSENT"
    REVOKED = "REVOKED"


class FallbackPolicy(StrEnum):
    # V1 aceita somente o comportamento seguro. Novas politicas exigem mudanca
    # explicita de codigo, review juridico e testes; nao entram como dado livre.
    BLOCK = "BLOCK"


class ResolutionStatus(StrEnum):
    DETERMINED = "DETERMINADO"
    INDETERMINATE = "INDETERMINADO"
    BLOCKED = "BLOQUEADO"


class ResolutionReason(StrEnum):
    OFFICIAL_VALUE_RESOLVED = "OFFICIAL_VALUE_RESOLVED"
    PARAMETER_NOT_REGISTERED = "PARAMETER_NOT_REGISTERED"
    NO_VERSION_FOR_REFERENCE_DATE = "NO_VERSION_FOR_REFERENCE_DATE"
    SOURCE_NOT_VALIDATED = "SOURCE_NOT_VALIDATED"
    OVERLAPPING_VERSIONS = "OVERLAPPING_VERSIONS"


def _required_string(raw: dict[str, Any], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FiscalParameterError(f"{field} deve ser string nao vazia")
    return value


def _parse_record_version(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FiscalParameterError("record_version deve ser inteiro")
    return value


def _parse_datetime(value: Any) -> dt.datetime:
    if not isinstance(value, str):
        raise FiscalParameterError("updated_at deve ser ISO-8601")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise FiscalParameterError("updated_at deve ser ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FiscalParameterError("updated_at deve conter timezone")
    return parsed


def _parse_date(value: str | None, field: str) -> dt.date | None:
    if value is None:
        return None
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise FiscalParameterError(f"{field} deve ser uma data ISO-8601") from exc


def _parse_value(value: Any) -> Decimal | None:
    if value is None:
        return None
    # Strings evitam introduzir aproximacao binaria em valor fiscal canonico.
    if not isinstance(value, str):
        raise FiscalParameterError("value deve ser string decimal ou null")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise FiscalParameterError("value nao e decimal valido") from exc
    if not parsed.is_finite():
        raise FiscalParameterError("value deve ser finito")
    return parsed


@dataclass(frozen=True)
class FiscalParameterVersion:
    record_version: int
    value: Decimal | None
    official_source: str
    source_url: str
    reference_act: str
    effective_from: dt.date
    effective_to: dt.date | None
    updated_at: dt.datetime
    source_status: SourceStatus
    source_fingerprint: str

    def __post_init__(self) -> None:
        if self.record_version < 1:
            raise FiscalParameterError("record_version deve ser positivo")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise FiscalParameterError("effective_to nao pode anteceder effective_from")
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise FiscalParameterError("updated_at deve conter timezone")
        if self.value is not None and not self.value.is_finite():
            raise FiscalParameterError("value deve ser finito")
        if not _SHA256.fullmatch(self.source_fingerprint):
            raise FiscalParameterError("source_fingerprint deve ser SHA-256 hexadecimal")
        if self.source_status is SourceStatus.OFFICIAL_VALIDATED and self.value is None:
            raise FiscalParameterError("fonte validada exige value")
        # Reusa a allowlist institucional de autoridades oficiais.
        ArtifactProvenance(
            artefato=self.reference_act,
            versao=None,
            fonte=self.official_source,
            source_url=self.source_url,
            observado_em=self.updated_at.date(),
            fingerprint=self.source_fingerprint,
        )

    def applies_at(self, reference_date: dt.date) -> bool:
        return self.effective_from <= reference_date and (
            self.effective_to is None or reference_date <= self.effective_to
        )

    def audit_dict(
        self,
        *,
        identifier: str,
        fallback: FallbackPolicy,
    ) -> dict[str, Any]:
        evidence = {
            "identifier": identifier,
            "fallback": fallback.value,
            "record_version": self.record_version,
            "value": str(self.value) if self.value is not None else None,
            "official_source": self.official_source,
            "source_url": self.source_url,
            "reference_act": self.reference_act,
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "updated_at": self.updated_at.isoformat(),
            "source_status": self.source_status.value,
            "source_fingerprint": self.source_fingerprint,
        }
        return {**evidence, "record_fingerprint": fingerprint_payload(evidence)}


@dataclass(frozen=True)
class FiscalParameterDefinition:
    identifier: str
    fallback: FallbackPolicy
    versions: tuple[FiscalParameterVersion, ...]

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.identifier):
            raise FiscalParameterError("identifier deve usar A-Z, 0-9 e underscore")
        record_versions = [item.record_version for item in self.versions]
        if len(record_versions) != len(set(record_versions)):
            raise FiscalParameterError(f"record_version duplicada em {self.identifier}")


@dataclass(frozen=True)
class FiscalParameterResolution:
    registry_schema_version: str
    identifier: str
    reference_date: dt.date
    resolved_at: dt.datetime
    status: ResolutionStatus
    reason: ResolutionReason
    fallback: FallbackPolicy
    value: Decimal | None
    selected_record_version: int | None
    evidence: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_schema_version": self.registry_schema_version,
            "identifier": self.identifier,
            "reference_date": self.reference_date.isoformat(),
            "resolved_at": self.resolved_at.isoformat(),
            "status": self.status.value,
            "reason": self.reason.value,
            "fallback": self.fallback.value,
            "value": str(self.value) if self.value is not None else None,
            "selected_record_version": self.selected_record_version,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class FiscalParameterRegistry:
    schema_version: str
    parameters: tuple[FiscalParameterDefinition, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise FiscalParameterError("schema_version nao suportada")
        identifiers = [item.identifier for item in self.parameters]
        if len(identifiers) != len(set(identifiers)):
            raise FiscalParameterError("identifier duplicado no registry")

    def get(self, identifier: str) -> FiscalParameterDefinition | None:
        return next((item for item in self.parameters if item.identifier == identifier), None)

    def resolve(
        self,
        identifier: str,
        reference_date: dt.date,
        *,
        resolved_at: dt.datetime | None = None,
    ) -> FiscalParameterResolution:
        if not _IDENTIFIER.fullmatch(identifier):
            raise FiscalParameterError("identifier deve usar A-Z, 0-9 e underscore")
        evaluated_at = resolved_at or dt.datetime.now(dt.timezone.utc)
        if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
            raise FiscalParameterError("resolved_at deve conter timezone")

        definition = self.get(identifier)
        if definition is None:
            return FiscalParameterResolution(
                registry_schema_version=self.schema_version,
                identifier=identifier,
                reference_date=reference_date,
                resolved_at=evaluated_at,
                status=ResolutionStatus.INDETERMINATE,
                reason=ResolutionReason.PARAMETER_NOT_REGISTERED,
                fallback=FallbackPolicy.BLOCK,
                value=None,
                selected_record_version=None,
                evidence=(),
            )

        applicable = tuple(item for item in definition.versions if item.applies_at(reference_date))
        evidence = tuple(
            item.audit_dict(identifier=definition.identifier, fallback=definition.fallback)
            for item in applicable
        )
        if not applicable:
            return FiscalParameterResolution(
                registry_schema_version=self.schema_version,
                identifier=identifier,
                reference_date=reference_date,
                resolved_at=evaluated_at,
                status=ResolutionStatus.INDETERMINATE,
                reason=ResolutionReason.NO_VERSION_FOR_REFERENCE_DATE,
                fallback=definition.fallback,
                value=None,
                selected_record_version=None,
                evidence=tuple(
                    item.audit_dict(identifier=definition.identifier, fallback=definition.fallback)
                    for item in definition.versions
                ),
            )
        if len(applicable) > 1:
            return FiscalParameterResolution(
                registry_schema_version=self.schema_version,
                identifier=identifier,
                reference_date=reference_date,
                resolved_at=evaluated_at,
                status=ResolutionStatus.BLOCKED,
                reason=ResolutionReason.OVERLAPPING_VERSIONS,
                fallback=definition.fallback,
                value=None,
                selected_record_version=None,
                evidence=evidence,
            )

        selected = next(iter(applicable))
        if selected.source_status is not SourceStatus.OFFICIAL_VALIDATED or selected.value is None:
            return FiscalParameterResolution(
                registry_schema_version=self.schema_version,
                identifier=identifier,
                reference_date=reference_date,
                resolved_at=evaluated_at,
                status=ResolutionStatus.BLOCKED,
                reason=ResolutionReason.SOURCE_NOT_VALIDATED,
                fallback=definition.fallback,
                value=None,
                selected_record_version=selected.record_version,
                evidence=evidence,
            )
        return FiscalParameterResolution(
            registry_schema_version=self.schema_version,
            identifier=identifier,
            reference_date=reference_date,
            resolved_at=evaluated_at,
            status=ResolutionStatus.DETERMINED,
            reason=ResolutionReason.OFFICIAL_VALUE_RESOLVED,
            fallback=definition.fallback,
            value=selected.value,
            selected_record_version=selected.record_version,
            evidence=evidence,
        )

    @classmethod
    def from_payload(cls, payload: Any) -> "FiscalParameterRegistry":
        if not isinstance(payload, dict):
            raise FiscalParameterError("registry deve ser objeto JSON")
        raw_parameters = payload.get("parameters")
        if not isinstance(raw_parameters, list):
            raise FiscalParameterError("parameters deve ser lista")
        definitions: list[FiscalParameterDefinition] = []
        for raw_definition in raw_parameters:
            if not isinstance(raw_definition, dict):
                raise FiscalParameterError("parameter deve ser objeto")
            raw_versions = raw_definition.get("versions")
            if not isinstance(raw_versions, list):
                raise FiscalParameterError("versions deve ser lista")
            versions: list[FiscalParameterVersion] = []
            for raw in raw_versions:
                if not isinstance(raw, dict):
                    raise FiscalParameterError("version deve ser objeto")
                effective_from = _parse_date(raw.get("effective_from"), "effective_from")
                if effective_from is None:
                    raise FiscalParameterError("effective_from e obrigatorio")
                try:
                    versions.append(FiscalParameterVersion(
                        record_version=_parse_record_version(raw.get("record_version")),
                        value=_parse_value(raw.get("value")),
                        official_source=_required_string(raw, "official_source"),
                        source_url=_required_string(raw, "source_url"),
                        reference_act=_required_string(raw, "reference_act"),
                        effective_from=effective_from,
                        effective_to=_parse_date(raw.get("effective_to"), "effective_to"),
                        updated_at=_parse_datetime(raw.get("updated_at")),
                        source_status=SourceStatus(_required_string(raw, "source_status")),
                        source_fingerprint=_required_string(raw, "source_fingerprint"),
                    ))
                except ProvenanceError as exc:
                    raise FiscalParameterError(str(exc)) from exc
                except (KeyError, TypeError, ValueError) as exc:
                    if isinstance(exc, FiscalParameterError):
                        raise
                    raise FiscalParameterError("version possui campo ausente ou invalido") from exc
            try:
                definitions.append(FiscalParameterDefinition(
                    identifier=_required_string(raw_definition, "identifier"),
                    fallback=FallbackPolicy(_required_string(raw_definition, "fallback")),
                    versions=tuple(versions),
                ))
            except (KeyError, TypeError, ValueError) as exc:
                if isinstance(exc, FiscalParameterError):
                    raise
                raise FiscalParameterError("parameter possui campo ausente ou invalido") from exc
        schema_version = payload.get("schema_version")
        if not isinstance(schema_version, str):
            raise FiscalParameterError("schema_version deve ser string")
        return cls(schema_version=schema_version, parameters=tuple(definitions))

    @classmethod
    def from_file(cls, path: pathlib.Path = _REGISTRY_FILE) -> "FiscalParameterRegistry":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FiscalParameterError("nao foi possivel carregar o registry") from exc
        return cls.from_payload(payload)


@functools.lru_cache(maxsize=1)
def embedded_registry() -> FiscalParameterRegistry:
    return FiscalParameterRegistry.from_file()


def resolve_fiscal_parameter(
    identifier: str,
    reference_date: dt.date,
    *,
    resolved_at: dt.datetime | None = None,
) -> FiscalParameterResolution:
    """Resolve no registry embarcado, sem fallback numerico ou temporal implicito."""
    return embedded_registry().resolve(identifier, reference_date, resolved_at=resolved_at)
