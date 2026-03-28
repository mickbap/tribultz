from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.crews.tools.get_job_status_tool import GetJobStatusTool
from app.crews.tools.parse_nfe_xml_tool import ParseNFeXMLTool
from app.crews.tools.parse_nfse_xml_tool import ParseNFSeXMLTool
from app.crews.tools.trigger_task_a_tool import TriggerTaskATool
from app.crews.tools.validate_fiscal_rules_tool import ValidateFiscalRulesTool
from app.crews.tools.validate_ibscbs_rules_tool import ValidateIBSCBSRulesTool


@dataclass(frozen=True)
class CrewToolsBundle:
    trigger_tool: Any
    status_tool: Any
    parse_nfse_tool: Any
    parse_nfe_tool: Any
    validate_rules_tool: Any
    validate_ibscbs_tool: Any


@dataclass(frozen=True)
class NFeValidationToolsBundle:
    parse_nfe_tool: Any
    validate_ibscbs_tool: Any


class CrewToolFactory:
    def build_chatops_tools(
        self,
        *,
        tenant_id: str,
        user_id: str,
        transaction_id: str | None,
    ) -> CrewToolsBundle:
        raise NotImplementedError

    def build_nfe_validation_tools(
        self,
        *,
        tenant_id: str,
        transaction_id: str | None,
    ) -> NFeValidationToolsBundle:
        raise NotImplementedError


class DefaultCrewToolFactory(CrewToolFactory):
    def build_chatops_tools(
        self,
        *,
        tenant_id: str,
        user_id: str,
        transaction_id: str | None,
    ) -> CrewToolsBundle:
        return CrewToolsBundle(
            trigger_tool=TriggerTaskATool(
                tenant_id=tenant_id,
                user_id=user_id,
                transaction_id=transaction_id,
            ),
            status_tool=GetJobStatusTool(tenant_id=tenant_id),
            parse_nfse_tool=ParseNFSeXMLTool(tenant_id=tenant_id, transaction_id=transaction_id),
            parse_nfe_tool=ParseNFeXMLTool(tenant_id=tenant_id, transaction_id=transaction_id),
            validate_rules_tool=ValidateFiscalRulesTool(transaction_id=transaction_id),
            validate_ibscbs_tool=ValidateIBSCBSRulesTool(transaction_id=transaction_id),
        )

    def build_nfe_validation_tools(
        self,
        *,
        tenant_id: str,
        transaction_id: str | None,
    ) -> NFeValidationToolsBundle:
        return NFeValidationToolsBundle(
            parse_nfe_tool=ParseNFeXMLTool(tenant_id=tenant_id, transaction_id=transaction_id),
            validate_ibscbs_tool=ValidateIBSCBSRulesTool(transaction_id=transaction_id),
        )
