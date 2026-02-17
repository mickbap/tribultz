# Pyright Issues – Backlog

Gerado em: 2026-02-12T03:59:44

Total: 36

| # | Arquivo | Linha | Regra | Mensagem |
|---|--------|------|------|----------|
| 1 | `backend\app\routers\tasks.py` | 69 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "tenant_id" of type "str" in function "task_a_validate_cbs_ibs" |
| 2 | `backend\app\routers\tasks.py` | 69 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "tenant_slug" of type "str" in function "task_a_validate_cbs_ibs" |
| 3 | `backend\app\routers\tasks.py` | 69 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "invoice_number" of type "str" in function "task_a_validate_cbs_ibs" |
| 4 | `backend\app\routers\tasks.py` | 69 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "issue_date" of type "str" in function "task_a_validate_cbs_ibs" |
| 5 | `backend\app\routers\tasks.py` | 69 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "declared_cbs" of type "str" in function "task_a_validate_cbs_ibs" |
| 6 | `backend\app\routers\tasks.py` | 69 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "declared_ibs" of type "str" in function "task_a_validate_cbs_ibs" |
| 7 | `backend\app\routers\tasks.py` | 69 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "items" of type "list[dict]" in function "task_a_validate_cbs_ibs" |
| 8 | `backend\app\routers\tasks.py` | 109 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "tenant_id" of type "str" in function "task_b_compliance_report" |
| 9 | `backend\app\routers\tasks.py` | 109 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "tenant_slug" of type "str" in function "task_b_compliance_report" |
| 10 | `backend\app\routers\tasks.py` | 109 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "company_name" of type "str" in function "task_b_compliance_report" |
| 11 | `backend\app\routers\tasks.py` | 109 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "cnpj" of type "str" in function "task_b_compliance_report" |
| 12 | `backend\app\routers\tasks.py` | 109 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "reference_period" of type "str" in function "task_b_compliance_report" |
| 13 | `backend\app\routers\tasks.py` | 109 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "invoices" of type "list[dict]" in function "task_b_compliance_report" |
| 14 | `backend\app\routers\tasks.py` | 144 | reportArgumentType | Argument of type "str \| list[dict[str, Any]] \| None" cannot be assigned to parameter "tenant_id" of type "str" in function "task_c_whatif_simulation" |
| 15 | `backend\app\routers\tasks.py` | 144 | reportArgumentType | Argument of type "str \| list[dict[str, Any]] \| None" cannot be assigned to parameter "tenant_slug" of type "str" in function "task_c_whatif_simulation" |
| 16 | `backend\app\routers\tasks.py` | 144 | reportArgumentType | Argument of type "str \| list[dict[str, Any]] \| None" cannot be assigned to parameter "simulation_name" of type "str" in function "task_c_whatif_simulation" |
| 17 | `backend\app\routers\tasks.py` | 144 | reportArgumentType | Argument of type "str \| list[dict[str, Any]] \| None" cannot be assigned to parameter "base_amount" of type "str" in function "task_c_whatif_simulation" |
| 18 | `backend\app\routers\tasks.py` | 144 | reportArgumentType | Argument of type "str \| list[dict[str, Any]] \| None" cannot be assigned to parameter "scenarios" of type "list[dict]" in function "task_c_whatif_simulation" |
| 19 | `backend\app\routers\tasks.py` | 144 | reportArgumentType | Argument of type "str \| list[dict[str, Any]] \| None" cannot be assigned to parameter "ref_date" of type "str \| None" in function "task_c_whatif_simulation" |
| 20 | `backend\app\routers\tasks.py` | 176 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "tenant_id" of type "str" in function "task_d_reconciliation" |
| 21 | `backend\app\routers\tasks.py` | 176 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "tenant_slug" of type "str" in function "task_d_reconciliation" |
| 22 | `backend\app\routers\tasks.py` | 176 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "csv_receivables_b64" of type "str" in function "task_d_reconciliation" |
| 23 | `backend\app\routers\tasks.py` | 176 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "invoices" of type "list[dict]" in function "task_d_reconciliation" |
| 24 | `backend\app\routers\tasks.py` | 176 | reportArgumentType | Argument of type "str \| list[dict[str, Any]]" cannot be assigned to parameter "tolerance" of type "str" in function "task_d_reconciliation" |
| 25 | `backend\app\routers\tasks.py` | 209 | reportArgumentType | Argument of type "str \| int \| None" cannot be assigned to parameter "tenant_id" of type "str" in function "task_e_hubspot_sync" |
| 26 | `backend\app\routers\tasks.py` | 209 | reportArgumentType | Argument of type "str \| int \| None" cannot be assigned to parameter "tenant_slug" of type "str" in function "task_e_hubspot_sync" |
| 27 | `backend\app\routers\tasks.py` | 209 | reportArgumentType | Argument of type "str \| int \| None" cannot be assigned to parameter "company_name" of type "str" in function "task_e_hubspot_sync" |
| 28 | `backend\app\routers\tasks.py` | 209 | reportArgumentType | Argument of type "str \| int \| None" cannot be assigned to parameter "cnpj" of type "str" in function "task_e_hubspot_sync" |
| 29 | `backend\app\routers\tasks.py` | 209 | reportArgumentType | Argument of type "str \| int \| None" cannot be assigned to parameter "domain" of type "str \| None" in function "task_e_hubspot_sync" |
| 30 | `backend\app\routers\tasks.py` | 209 | reportArgumentType | Argument of type "str \| int \| None" cannot be assigned to parameter "invoices_validated" of type "int" in function "task_e_hubspot_sync" |
| 31 | `backend\app\routers\tasks.py` | 209 | reportArgumentType | Argument of type "str \| int \| None" cannot be assigned to parameter "exceptions_count" of type "int" in function "task_e_hubspot_sync" |
| 32 | `backend\app\routers\tasks.py` | 209 | reportArgumentType | Argument of type "str \| int \| None" cannot be assigned to parameter "deal_value" of type "str \| None" in function "task_e_hubspot_sync" |
| 33 | `backend\app\tools\erp_connector_tool.py` | 77 | reportAttributeAccessIssue | Cannot assign to attribute "total_amount" for class "ImportedInvoice" — Type "Decimal \| Literal[0]" is not assignable to "Decimal" |
| 34 | `backend\app\tools\validation_tool.py` | 104 | reportAssignmentType | Type "dict[tuple[Unknown, Unknown], Decimal]" is not assignable to declared type "dict[str, Decimal]" |
| 35 | `backend\app\tools\validation_tool.py` | 117 | reportArgumentType | Argument of type "tuple[Unknown, Literal['CBS']]" cannot be assigned to parameter "key" of type "str" in function "get" |
| 36 | `backend\app\tools\validation_tool.py` | 118 | reportArgumentType | Argument of type "tuple[Unknown, Literal['IBS']]" cannot be assigned to parameter "key" of type "str" in function "get" |

---

## Resumo por arquivo

| Arquivo | Erros | Causa raiz |
|---------|-------|------------|
| `routers/tasks.py` | 32 | `**kwargs` unpacking com `dict` genérico — Pyright não consegue inferir tipos individuais |
| `tools/erp_connector_tool.py` | 1 | `Decimal \| Literal[0]` vs `Decimal` |
| `tools/validation_tool.py` | 3 | Dict com key `tuple` declarado como `dict[str, ...]` |

## Estratégia de correção

- **32 erros em `tasks.py`**: Passar argumentos nomeados diretamente em vez de `**kwargs`
- **1 erro em `erp_connector_tool.py`**: Usar `Decimal(0)` em vez de literal `0`
- **3 erros em `validation_tool.py`**: Corrigir type annotation do dict de rates (usar `tuple` como key)
