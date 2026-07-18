from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.crews.tools.parse_nfe_xml_tool import ParseNFeXMLTool
from app.crews.tools.validate_ibscbs_rules_tool import ValidateIBSCBSRulesTool


@dataclass(frozen=True)
class NFeValidationToolsBundle:
    parse_nfe_tool: Any
    validate_ibscbs_tool: Any


class CrewToolFactory:
    def build_nfe_validation_tools(
        self,
        *,
        tenant_id: str,
        transaction_id: str | None,
    ) -> NFeValidationToolsBundle:
        raise NotImplementedError


class DefaultCrewToolFactory(CrewToolFactory):
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
