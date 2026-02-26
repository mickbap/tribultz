# TRIBULTZ Console v2 (Sprint 6)

Frontend Next.js (App Router + TypeScript + Tailwind) com Mock Mode ON por padrao e integracao opcional com API FastAPI.

## Requisitos
- Node 20+
- npm 10+

## Instalacao
```bash
npm install
```

## Rodar local (Mock Mode)
```bash
npm run dev
```
Acesse `http://localhost:3000/login` e clique em **Entrar (Demo)**.

## Build
```bash
npm run build
```

## Testes unitarios (regras XML)
```bash
npm run test:rules
```

## Modos de execucao

### Mock Mode (default ON)
- Funciona sem backend.
- Simula chat, jobs, audit e excecoes de forma deterministica.
- Simula transicao de job `RUNNING -> SUCCESS`.

### API Mode
1. Configure `NEXT_PUBLIC_API_BASE_URL` no `.env.local`:
```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```
2. Em `/login`, use **Entrar (API)** com `email`, `password` e tenant.
3. O login usa `POST /api/v1/auth/login` e salva `access_token` no storage.
4. Em `/settings`, voce tambem pode ajustar tenant/token manualmente.

Toda request em API Mode envia:
- `Authorization: Bearer <token>`
- `X-Tenant-Id: <tenant>`

## Fluxo principal de demo
`Login -> Dashboard -> Chat -> Validar CBS/IBS -> Job -> Audit`

## Sprint 6 (P0): Validacao XML + Excecoes
- Nova rota: `/validate-xml` (NFS-e primeiro; NF-e suportado).
- Contrato Findings + Evidence v1.1:
  - Schema: `src/lib/validation/findings-evidence-v1.1.schema.json`
  - Exemplo: `src/lib/validation/fixtures/findings-evidence-v1.1.example.json`
- Regras MVP:
  - FATAL: `CST` 3 digitos, `cClassTrib` 6 digitos, `CodigoServico` 6 digitos.
  - ALERT: revisao de NCM e beneficios/creditos (placeholder explicativo).
- Workflow de excecao:
  - Operador abre excecao no finding (justificativa obrigatoria).
  - Coordenador decide em `/exceptions` (aprovar/reprovar + comentario).
  - Eventos de excecao sao registrados no audit.

### Exemplo de payload v1.1
```json
{
  "job": { "id": "job_xml_a12f0b31", "created_at": "2026-02-25T00:00:00.000Z", "tenant_id": "tenant-a" },
  "audit": { "id": "audit_xml_a12f0b31", "job_id": "job_xml_a12f0b31", "events": [] },
  "findings": [
    {
      "id": "F_CST_LEN",
      "severity": "FATAL",
      "rule_id": "CST_3_DIGITS",
      "title": "CST inválido (esperado 3 dígitos)",
      "where": { "field": "CST", "xpath": "/NFS-e/infNfse//CST", "snippet": "<CST>12</CST>" },
      "recommendation": "Corrigir no ERP e reemitir (com justificativa se necessário).",
      "evidence_ids": ["E_XML_CST_LEN"]
    }
  ],
  "evidences": [
    { "id": "E_XML_CST_LEN", "type": "xml", "label": "Trecho XML — CST", "xpath": "/NFS-e/infNfse//CST", "snippet": "<CST>12</CST>" }
  ]
}
```

## Legado
- `/validate` redireciona para `/validate-xml`.
- `/report` redireciona para `/jobs`.

## Estrutura principal
- `src/app/login`
- `src/app/dashboard`
- `src/app/chat`
- `src/app/validate-xml`
- `src/app/jobs`
- `src/app/jobs/[id]`
- `src/app/audit`
- `src/app/exceptions`
- `src/app/settings`
- `src/components/*`
- `src/lib/api.ts`
- `src/lib/mock.ts`
- `src/lib/types.ts`
- `src/lib/storage.ts`
- `src/lib/validation/*`

## Governanca de repositorio
- Repositorio canonical do produto: `mickbap/tribultz`.
- `mickbap/tribultz-console-navigator` e apenas referencia/export do Lovable.
