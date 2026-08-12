"""Round 4 F2-prep: validação do contrato HandoffEvent v1.1 (sem DB).

Payloads 100% sintéticos e claramente identificados — nenhum dado real
(Edgard/Rödl fora de qualquer teste, gate do Round 4).
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.services.handoff.contract import (
    CompanyIdentityPayload,
    HandoffEvent,
    MaybeStr,
    PersonIdentityPayload,
)

ULID = "01J8ZM7WVX2Q9RKTHB3F6D5A1C"


def _event(**overrides):
    base = dict(
        event_id=ULID,
        occurred_at=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
        external_lead_id="lead-sintetico-001",
        person=PersonIdentityPayload(
            full_name="Pessoa Sintética [QA]",
            email=MaybeStr.known("pessoa.sintetica@example.test"),
        ),
        company=CompanyIdentityPayload(name=MaybeStr.known("Empresa Sintética QA Ltda")),
        reason="positive_reply",
    )
    base.update(overrides)
    return HandoffEvent(**base)


def test_known_exige_valor_nao_vazio():
    with pytest.raises(ValidationError):
        MaybeStr(status="known")
    with pytest.raises(ValidationError):
        MaybeStr(status="known", value="   ")


def test_absent_proibe_valor():
    with pytest.raises(ValidationError):
        MaybeStr(status="absent", value="x@example.test")


def test_ausencia_explicita_nao_vira_placeholder():
    ev = _event()
    assert ev.person.linkedin_url.status == "absent"
    assert ev.person.linkedin_url.value is None
    assert ev.owner.status == "absent"


def test_event_id_deve_ser_ulid():
    with pytest.raises(ValidationError):
        _event(event_id="nao-e-ulid")
    with pytest.raises(ValidationError):
        _event(event_id=ULID.lower())  # ULID canônico é maiúsculo


def test_occurred_at_naive_rejeitado():
    with pytest.raises(ValidationError):
        _event(occurred_at=datetime(2026, 8, 12, 12, 0))


def test_occurred_at_normalizado_para_utc():
    from zoneinfo import ZoneInfo

    ev = _event(occurred_at=datetime(2026, 8, 12, 9, 0, tzinfo=ZoneInfo("America/Sao_Paulo")))
    assert ev.occurred_at.tzinfo == timezone.utc
    assert ev.occurred_at.hour == 12


def test_minimo_identidade():
    assert _event().has_identity_minimum is True

    sem_chaves = _event(person=PersonIdentityPayload(full_name="Só Nome [QA]"))
    assert sem_chaves.has_identity_minimum is False

    sem_empresa = _event(company=CompanyIdentityPayload())
    assert sem_empresa.has_identity_minimum is False

    so_linkedin = _event(
        person=PersonIdentityPayload(
            full_name="Pessoa Sintética [QA]",
            linkedin_url=MaybeStr.known("linkedin.com/in/pessoa-sintetica-qa"),
        )
    )
    assert so_linkedin.has_identity_minimum is True


def test_external_lead_id_vazio_rejeitado():
    with pytest.raises(ValidationError):
        _event(external_lead_id="  ")
