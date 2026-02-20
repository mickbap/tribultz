# Sprint 4 - Tribultz (Console + Backend Guardianship)

Kickoff: 20/02/2026
North Star: CI verde + QA gates automaticos + padrao fiscal BR + login/UX robusto (base para MFA/SSO).

## P0
- S4-00 CI Stabilization (bloqueador)
- S4-01 QA Specialist Agent (gates automaticos + relatorio)

## P1
- S4-02 Template de respostas tributarias BR (rastreabilidade Job/Audit)
- S4-03 UX Login + rate limit + auditoria de eventos

## Artefatos
- Workflow: .github/workflows/ci.yml
- Runner: tools/qa_gates/run_gates.py
- Report: reports/qa_gates_report.md
- Template fiscal: crews/tribultz_chatops/templates/ptbr_tax_response_template.md