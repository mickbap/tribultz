# Sprint 2 Walkthrough — Login + Auth Guard + Chat Stub + Tenant Scoping (DoD: NOT MET)

## Evidence
- **Feature Commit**: `5f46171` (login, auth guard, chat stub, tenant scoping)
- **Docs Commit**: `4a29e29` (closeout report), `71d81f8` (report correction)
- **Branch**: `wip/antigravity-fixes`

---

## What Shipped

### A) Frontend: Login + Auth Guard + Token Injection ✅

| File | Change |
|------|--------|
| [auth.ts](file:///c:/Tribultz/frontend/src/auth/auth.ts) | `getToken`/`setToken`/`clearToken` via `sessionStorage` (`TRIBULTZ_TOKEN` key, XSS warning) |
| [AuthGuard.tsx](file:///c:/Tribultz/frontend/src/auth/AuthGuard.tsx) | Client-side route guard → redirects to `/login` when token is missing |
| [login/page.tsx](file:///c:/Tribultz/frontend/src/app/login/page.tsx) | Email + password + tenant_slug login form → `POST /api/v1/auth/login` |
| [api.ts](file:///c:/Tribultz/frontend/src/services/api.ts) | `Authorization: Bearer <token>` injected on all `apiGet` calls |
| [jobs/page.tsx](file:///c:/Tribultz/frontend/src/app/jobs/page.tsx) | Converted to `"use client"` + AuthGuard |
| [jobs/[id]/page.tsx](file:///c:/Tribultz/frontend/src/app/jobs/%5Bid%5D/page.tsx) | Converted to `"use client"` + AuthGuard |
| [audit/page.tsx](file:///c:/Tribultz/frontend/src/app/audit/page.tsx) | Converted to `"use client"` + AuthGuard |

### B) Chat Stub (Feature-Flagged) ✅

| File | Change |
|------|--------|
| [chat/page.tsx](file:///c:/Tribultz/frontend/src/app/chat/page.tsx) | "Coming Soon" stub; redirects to `/jobs` when `NEXT_PUBLIC_CHAT_ENABLED !== "true"` |
| [NavBar.tsx](file:///c:/Tribultz/frontend/src/app/NavBar.tsx) | Nav bar with Jobs, Audit, Chat (conditional), Logout |
| [layout.tsx](file:///c:/Tribultz/frontend/src/app/layout.tsx) | Updated title to "Tribultz Console", added NavBar |

### C) Backend: Tenant-Scoped Jobs List (Partial) ⚠️

| File | Change |
|------|--------|
| [jobs.py](file:///c:/Tribultz/backend/app/routers/jobs.py) | `list_jobs` uses `Depends(get_current_user)`; scopes by `tenant_id` |

---

## DoD Gaps (NOT MET)
1. **Task Trigger via UI**: Not implemented (deferred).
2. **Alembic Configuration**: Not implemented.
3. **Tenant Scoping**: Partial (only list endpoint).

---

## Verification Results

| Check | Result |
|-------|--------|
| `ruff check app tests` | ✅ Clean |
| `pyright` | ✅ Clean |
| `pytest -q` | ✅ 6 passed, 3 warnings |
| `npm run build` | ✅ All 6 routes compiled |
