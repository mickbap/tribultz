# TRIBULTZ Console v2 (Sprint 5)

Frontend Next.js (App Router + TypeScript + Tailwind) com **Mock Mode ON por padrão** e integração opcional com API FastAPI.

## Requisitos
- Node 20+
- npm 10+

## Instalação
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

## Modos de execução

### Mock Mode (default ON)
- Funciona sem backend.
- Simula chat, jobs e audit de forma determinística.
- Simula transição de job `RUNNING -> SUCCESS`.

### API Mode
1. Configure `NEXT_PUBLIC_API_BASE_URL` no `.env.local`:
```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```
2. Em `/login`, use **Entrar (API)** com `email`, `password` e tenant.
3. O login usa `POST /api/v1/auth/login` e salva `access_token` no storage.
4. Em `/settings`, você também pode ajustar tenant/token manualmente.

Toda request em API Mode envia:
- `Authorization: Bearer <token>`
- `X-Tenant-Id: <tenant>`

## Fluxo principal de demo
`Login -> Dashboard -> Chat -> Validar CBS/IBS -> Job -> Audit`

## Legado
- `/validate` redireciona para `/chat`.
- `/report` redireciona para `/jobs`.

## Estrutura principal
- `src/app/login`
- `src/app/dashboard`
- `src/app/chat`
- `src/app/jobs`
- `src/app/jobs/[id]`
- `src/app/audit`
- `src/app/settings`
- `src/components/*`
- `src/lib/api.ts`
- `src/lib/mock.ts`
- `src/lib/types.ts`
- `src/lib/storage.ts`
