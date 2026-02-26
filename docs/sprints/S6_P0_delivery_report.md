# Sprint 6 P0 - XML Validation + Exception Workflow

## Scope entregue
- Contrato Findings + Evidence v1.1 em TypeScript (`frontend/src/lib/types.ts`) e JSON Schema (`frontend/src/lib/validation/findings-evidence-v1.1.schema.json`).
- Exemplo de payload v1.1 (`frontend/src/lib/validation/fixtures/findings-evidence-v1.1.example.json`).
- Fixtures XML:
  - `frontend/src/lib/validation/fixtures/nfse-ok.xml`
  - `frontend/src/lib/validation/fixtures/nfse-com-erros.xml`
  - `frontend/src/lib/validation/fixtures/nfe-smoke.xml`
- Engine de validaÃ§Ã£o XML (funÃ§Ãµes puras) em `frontend/src/lib/validation/xmlRules.ts`.
- Testes unitÃ¡rios de regras e determinismo em `frontend/src/lib/validation/xmlRules.test.ts`.
- Tela de validaÃ§Ã£o XML em `frontend/src/app/validate-xml/page.tsx`.
- Workflow de exceÃ§Ã£o (abertura + fila coordenador + decisÃ£o) em `frontend/src/app/exceptions/page.tsx`.
- IntegraÃ§Ã£o mock/API adapter para validaÃ§Ã£o XML e exceÃ§Ãµes em `frontend/src/lib/api.ts` e `frontend/src/lib/mock.ts`.
- NavegaÃ§Ã£o atualizada (`frontend/src/components/layout/Sidebar.tsx`) e detalhes de job/audit atualizados.

## Regras MVP implementadas
- FATAL:
  - `CST` exatamente 3 dÃ­gitos.
  - `cClassTrib` exatamente 6 dÃ­gitos.
  - `CodigoServico` exatamente 6 dÃ­gitos.
- ALERT:
  - RevisÃ£o de NCM.
  - RevisÃ£o de benefÃ­cios/crÃ©ditos.

Todos os findings geram `where` e `evidence_ids`, com evidÃªncia de fonte (`xml`/`print`).

## Workflow de exceÃ§Ã£o
- Operador abre exceÃ§Ã£o a partir de um finding com justificativa obrigatÃ³ria.
- Entidade `ExceptionRequest` com status `OPEN|APPROVED|REJECTED` no mock storage.
- Coordenador decide em `/exceptions` com comentÃ¡rio opcional.
- Eventos registrados no audit (`exception_opened`, `exception_approved`, `exception_rejected`), com retenÃ§Ã£o contratual MVP (`5y-contractual`).

## Multi-tenant/API Mode
- Adapter mantÃ©m headers em todas as requests API Mode:
  - `Authorization: Bearer <token>`
  - `X-Tenant-Id: <tenant>`

## Comandos executados
- `cd frontend && npm install`
- `cd frontend && npm run test:rules` (PASS)
- `cd frontend && npm run build` (PASS)

## EvidÃªncias solicitadas (capturas + payload real)
- Screenshot (finding FATAL com snippet/xpath): `docs/sprints/assets/s6_validate_xml_fatal.png`
- Screenshot (modal de exceÃ§Ã£o): `docs/sprints/assets/s6_exception_modal.png`
- Screenshot (exceÃ§Ã£o aprovada): `docs/sprints/assets/s6_exception_approved.png`
- Payload real v1.1 (mock): `docs/sprints/S6_payload_v1.1.real.json`
- Payload v1.1 com audit.events de exceção: `docs/sprints/S6_payload_v1.1.with_exception_events.json`

## DoD Sprint 6 P0 checklist
- [x] Colar/upload XML -> validar -> findings com evidÃªncias.
- [x] Links/atalhos para Job e Audit no resultado.
- [x] Abrir exceÃ§Ã£o por finding (justificativa obrigatÃ³ria).
- [x] Aprovar/reprovar exceÃ§Ã£o na fila do coordenador.
- [x] Audit registra eventos de exceÃ§Ã£o.
- [x] Mock determinÃ­stico por XML + tipo.
- [x] Testes unitÃ¡rios das regras fatais.
- [x] README atualizado com instruÃ§Ãµes e payload v1.1.
