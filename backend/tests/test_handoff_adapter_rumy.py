"""#690 — adapter do contrato público do Rumy (``lead.converted``), Round 16-G.

Cobre o que a matriz do Round 16-F apontou como risco: id externo preservado,
``contact_shared`` sem degradação, ``company=null`` aceito só onde há identidade
externa confiável, ``from=system`` que não vira fala do lead e proveniência de
``api_version``.

Payloads sintéticos no formato documentado. Nenhuma flag habilitada.
"""

import pytest

from app.services.handoff.adapter import (
    REASON_MAP,
    RumyLeadConvertedAdapter,
    UnmappedEvent,
    get_adapter,
)
from app.services.handoff.contract import (
    COMPANY_OPTIONAL_ORIGINS,
    HandoffEvent,
    LastInteraction,
)


def _payload(**over):
    base = {
        "id": "evt_9f1c2d3e-4b5a-6789-abcd-ef0123456789",
        "api_version": "2026-08-01",
        "event_type": "lead.converted",
        "occurred_at": "2026-08-28T13:20:00Z",
        "data": {
            "reason": "cta_positive",
            "lead": {
                "id": "lead_sintetico_690",
                "name": "Fulano Sintético",
                "email": "fulano@exemplo-sintetico.com.br",
                "linkedin_url": "https://www.linkedin.com/in/fulano-sintetico",
            },
            "company": {"name": "Empresa Sintética", "cnpj": None, "domain": None},
            "campaign": {"id": "camp_001"},
            "conversation": [
                {"from": "agent", "text": "oi", "at": "2026-08-27T10:00:00Z"},
                {"from": "lead", "text": "pode sim", "at": "2026-08-28T12:00:00Z", "id": "m2"},
            ],
        },
    }
    base["data"].update(over.pop("data", {}))
    base.update(over)
    return base


A = RumyLeadConvertedAdapter()


def _ev(payload) -> HandoffEvent:
    """Adapta e estreita o tipo: aqui só interessam os casos que viram evento."""
    out = A.to_handoff_event(payload)
    assert isinstance(out, HandoffEvent), f"esperava HandoffEvent, veio {type(out).__name__}"
    return out


class TestSelecaoEEscopo:
    def test_adapter_vigente_e_o_do_contrato_real(self):
        assert isinstance(get_adapter(), RumyLeadConvertedAdapter)
        assert get_adapter().version == "rumy-lead-converted-1.0"

    def test_evento_fora_do_contrato_vira_unmapped(self):
        out = A.to_handoff_event(_payload(event_type="lead.something_else"))
        assert isinstance(out, UnmappedEvent)

    def test_reason_desconhecido_nao_vira_other_em_silencio(self):
        out = A.to_handoff_event(_payload(data={"reason": "motivo_novo_do_fornecedor"}))
        assert isinstance(out, UnmappedEvent), "motivo novo tem de ser auditável, não adivinhado"


class TestMapeamentoDeRazao:
    @pytest.mark.parametrize(
        "rumy,interno",
        [("meeting_ready", "meeting_request"),
         ("cta_positive", "positive_reply"),
         ("contact_shared", "contact_shared")],
    )
    def test_tres_motivos_do_contrato(self, rumy, interno):
        assert _ev(_payload(data={"reason": rumy})).reason == interno

    def test_contact_shared_nao_degrada_para_other(self):
        assert _ev(_payload(data={"reason": "contact_shared"})).reason != "other"

    def test_mapa_cobre_exatamente_os_tres_motivos_publicos(self):
        assert set(REASON_MAP) == {"meeting_ready", "cta_positive", "contact_shared"}


class TestIdentidadeExterna:
    def test_event_id_externo_preservado_byte_a_byte(self):
        assert _ev(_payload()).provider_event_id == "evt_9f1c2d3e-4b5a-6789-abcd-ef0123456789"

    def test_id_interno_e_ulid_e_nao_contamina_o_externo(self):
        ev = _ev(_payload())
        assert len(ev.event_id) == 26 and ev.event_id != ev.provider_event_id

    def test_api_version_preservada_para_proveniencia(self):
        assert _ev(_payload()).api_version == "2026-08-01"

    def test_external_lead_id_preservado(self):
        assert _ev(_payload()).external_lead_id == "lead_sintetico_690"


class TestCompanyNull:
    def test_company_null_vira_absent_sem_fabricar(self):
        ev = _ev(_payload(data={"company": None}))
        assert ev.company.name.status == "absent"
        assert ev.company.name.value is None

    def test_company_null_do_rumy_passa_no_minimo_de_identidade(self):
        """Decisão de Produto 28/08: com id externo confiável, empresa não é requisito."""
        assert _ev(_payload(data={"company": None})).has_identity_minimum is True

    def test_flexibilizacao_nao_vaza_para_outras_origens(self):
        """A política é por origem — outras fontes seguem exigindo empresa."""
        ev = _ev(_payload(data={"company": None}))
        outra = ev.model_copy(update={"source_system": "outra_origem"})
        assert outra.has_identity_minimum is False

    def test_sem_external_lead_id_a_flexibilizacao_nao_vale(self):
        """Origem sozinha não basta: sem id externo não há identidade confiável."""
        ev = _ev(_payload(data={"company": None}))
        sem_id = ev.model_copy(update={"external_lead_id": "x"})
        assert sem_id.company_is_optional is True
        assert "rumy" in COMPANY_OPTIONAL_ORIGINS

    def test_sem_nome_e_sem_contato_continua_quarentena(self):
        ev = _ev(
            _payload(data={"company": None,
                           "lead": {"id": "l1", "name": "Sem Contato",
                                    "email": None, "linkedin_url": None}})
        )
        assert ev.has_identity_minimum is False


class TestConversa:
    def test_from_system_nao_vira_interacao_do_lead(self):
        ev = _ev(
            _payload(data={"conversation": [
                {"from": "lead", "text": "oi", "at": "2026-08-27T10:00:00Z"},
                {"from": "system", "text": "[conversa truncada]", "at": "2026-08-28T09:00:00Z"},
            ]})
        )
        assert ev.last_interaction is not None
        assert ev.last_interaction.kind == "system_marker"

    def test_ultima_fala_do_lead_e_reply(self):
        assert (_ev(_payload()).last_interaction or LastInteraction(channel="x", kind="x")).kind == "reply"

    def test_conversa_ausente_nao_inventa_interacao(self):
        assert _ev(_payload(data={"conversation": None})).last_interaction is None


class TestOwnership:
    def test_nenhum_motivo_produz_human_owned(self):
        """`lead.converted` é sinal do fornecedor; assumir a conversa é ato humano."""
        for r in REASON_MAP:
            ev = _ev(_payload(data={"reason": r}))
            assert ev.event_type == "handoff.requested"
            assert "HUMAN_OWNED" not in ev.model_dump_json()
