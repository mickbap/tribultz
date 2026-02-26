# Sprint 6 P0 - XML Validation + Exception Workflow

## Scope entregue
- Contrato Findings + Evidence v1.1 em TypeScript (`frontend/src/lib/types.ts`) e JSON Schema (`frontend/src/lib/validation/findings-evidence-v1.1.schema.json`).
- Exemplo de payload v1.1 (`frontend/src/lib/validation/fixtures/findings-evidence-v1.1.example.json`).
- Fixtures XML:
  - `frontend/src/lib/validation/fixtures/nfse-ok.xml`
  - `frontend/src/lib/validation/fixtures/nfse-com-erros.xml`
  - `frontend/src/lib/validation/fixtures/nfe-smoke.xml`
- Engine de validação XML (funções puras) em `frontend/src/lib/validation/xmlRules.ts`.
- Testes unitários de regras e determinismo em `frontend/src/lib/validation/xmlRules.test.ts`.
- Tela de validação XML em `frontend/src/app/validate-xml/page.tsx`.
- Workflow de exceção (abertura + fila coordenador + decisão) em `frontend/src/app/exceptions/page.tsx`.
- Integração mock/API adapter para validação XML e exceções em `frontend/src/lib/api.ts` e `frontend/src/lib/mock.ts`.
- Navegação atualizada (`frontend/src/components/layout/Sidebar.tsx`) e detalhes de job/audit atualizados.

## Regras MVP implementadas
- FATAL:
  - `CST` exatamente 3 dígitos.
  - `cClassTrib` exatamente 6 dígitos.
  - `CodigoServico` exatamente 6 dígitos.
- ALERT:
  - Revisão de NCM.
  - Revisão de benefícios/créditos.

Todos os findings geram `where` e `evidence_ids`, com evidência de fonte (`xml`/`print`).

## Workflow de exceção
- Operador abre exceção a partir de um finding com justificativa obrigatória.
- Entidade `ExceptionRequest` com status `OPEN|APPROVED|REJECTED` no mock storage.
- Coordenador decide em `/exceptions` com comentário opcional.
- Eventos registrados no audit (`exception_opened`, `exception_approved`, `exception_rejected`), com retenção contratual MVP (`5y-contractual`).

## Multi-tenant/API Mode
- Adapter mantém headers em todas as requests API Mode:
  - `Authorization: Bearer <token>`
  - `X-Tenant-Id: <tenant>`

## Comandos executados
- `cd frontend && npm install`
- `cd frontend && npm run test:rules` (PASS)
- `cd frontend && npm run build` (PASS)

## Evidências solicitadas (capturas + payload real)
- Screenshot (finding FATAL com snippet/xpath): `docs/sprints/assets/s6_validate_xml_fatal.png`
- Screenshot (modal de exceção): `docs/sprints/assets/s6_exception_modal.png`
- Screenshot (exceção aprovada): `docs/sprints/assets/s6_exception_approved.png`
- Payload real v1.1 (mock): `docs/sprints/S6_payload_v1.1.real.json`

## DoD Sprint 6 P0 checklist
- [x] Colar/upload XML -> validar -> findings com evidências.
- [x] Links/atalhos para Job e Audit no resultado.
- [x] Abrir exceção por finding (justificativa obrigatória).
- [x] Aprovar/reprovar exceção na fila do coordenador.
- [x] Audit registra eventos de exceção.
- [x] Mock determinístico por XML + tipo.
- [x] Testes unitários das regras fatais.
- [x] README atualizado com instruções e payload v1.1.
