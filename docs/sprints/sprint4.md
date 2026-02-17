# Sprint 4 — Segurança, QA automático e Experiência de Login (Tribultz Console)

## Contexto
A Sprint 3 entregou o Chat MVP (endpoint + persistência + evidência de Job + UI /chat + gates).  
A Sprint 4 foca em **maturidade**, **segurança**, **padronização de linguagem fiscal/tributária** e **automação de QA**.

---

## Backlog (S4-01..S4-06)

### S4-01 — QA Specialist Agent (gates automáticos)
**Objetivo:** Criar agente CrewAI “QA Specialist” que execute e valide gates finais e contrato do /api/v1/chat/message, gerando relatório Markdown (✅/❌ por gate, falhas com arquivo/linha, risco e recomendação).

**Critérios de aceite:**
- qa_specialist definido em crews/tribultz_chatops/config/agents.yaml
- Task qa_validate_gates em crews/tribultz_chatops/config/tasks.yaml
- Relatório final inclui checagens:
  - 401 unauthorized
  - 404 cross-tenant (conversation de outro tenant -> 404)
  - 422 payload > 4k
  - 429 rate limit
  - evidence tipada (job_id/href/label)
  - uff/pyright/pytest
  - 
pm ci && npm run build (frontend)
- Execução do comando padrão dos gates (ou equivalente via pipeline)

---

### S4-02 — Padrão de respostas tributárias BR (formatação + linguagem)
**Objetivo:** Padronizar saídas do assistente/agentes para boas práticas do mercado tributário brasileiro.

**Critérios de aceite:**
- Template Markdown aplicado ao fluxo “validate”
- Formatação BRL consistente (ex.: R$ 1.234,56)
- Seções mínimas: **Resultado**, **Evidências**, **Observações/Premissas**
- Linguagem PT-BR, com premissas e sem absolutismo
- Evidência sempre tipada e rastreável (link interno do Job)

---

### S4-03 — UX de Login “Cliente” (fluxo robusto e pronto p/ MFA)
**Objetivo:** Melhorar experiência e confiabilidade do login no Console, preparando terreno para MFA/SSO.

**Escopo (Frontend):**
- /login com estados claros: loading, erro, bloqueio temporário
- “Esqueci minha senha” (se existir)
- Persistência segura de sessão (cookie HttpOnly, se aplicável)
- Redirecionamento pós-login com 
ext= + allowlist (evitar open redirect)

**Escopo (Backend):**
- Fluxos existentes: login / refresh (se existir) / logout
- Rate limit por IP + user (defesa básica anti brute force)

**Auditoria/Observabilidade:**
- user_login_succeeded (tenant_id, user_id, ip, user_agent)
- user_login_failed (tenant_id? se detectável, subject/email, ip, reason)
- user_logout (tenant_id, user_id)
- Logs estruturados: equest_id, ip, user_agent, 	enant_id, user_id

**Critérios de aceite:**
- Login funciona com UX mínima e erros visíveis
- Rate limiting aplicado no login
- Auditoria emitida nos 3 eventos
- Sem vazamento: mensagens não revelam se usuário existe

---

### S4-04 — MFA por TOTP + Recovery Codes
**Objetivo:** Habilitar 2FA/MFA por TOTP com recovery codes single-use.

**Escopo (Backend):**
- Tabelas mínimas:
  - user_mfa (user_id, tenant_id, totp_secret_encrypted, enabled_at, last_used_at)
  - user_mfa_recovery_codes (user_id, tenant_id, code_hash, used_at)
- Endpoints sugeridos:
  - POST /mfa/setup/start (secret + provisioning URI)
  - POST /mfa/setup/verify (valida 1º código e ativa)
  - POST /mfa/disable (requer senha + TOTP ou recovery)
  - Login em 2 passos quando MFA enabled:
    - credenciais ok -> mfa_required=true, challenge_id
    - POST /login/mfa com TOTP/recovery -> emite sessão/JWT
- Segurança:
  - secret criptografado
  - recovery codes com hash forte (bcrypt/argon2)
  - proteção básica anti-replay (opcional)

**Escopo (Frontend):**
- Setup MFA: QR + código manual + input 6 dígitos + exibir recovery codes (uma vez)
- Challenge MFA no login: TOTP + fallback recovery

**Auditoria/Observabilidade:**
- mfa_setup_started, mfa_enabled, mfa_challenged, mfa_challenge_succeeded, mfa_challenge_failed,
  mfa_disabled, mfa_recovery_code_used

**Critérios de aceite:**
- Usuário habilita MFA e login passa a exigir desafio
- Recovery codes funcionam (single-use)
- Auditoria completa
- Testes mínimos cobrindo enable + login com MFA

---

### S4-05 — SSO Enterprise: OIDC/SAML (Discovery + MVP)
**Objetivo:** Login via SSO para tenants com IdP (aproveitar MFA do IdP).

**Escopo:**
- Discovery por domínio (ex.: @empresa.com -> método SSO)
- OIDC primeiro; SAML depois (se fizer sentido)
- Mapeamento de claims -> user + tenant scoping
- Auditoria: sso_login_succeeded, sso_login_failed, sso_config_changed

**Critérios de aceite:**
- Para tenants configurados, login via SSO end-to-end
- Provisionamento JIT (se permitido) com regras claras
- Auditoria emitida

**Nota:** Se a Sprint 4 estiver carregada, virar **Discovery + design doc + spikes** e implementação fica para Sprint 5.

---

### S4-06 — Hardening opcional de segurança (se couber)
**Objetivo:** Elevar padrão sem inflar escopo.

**Ideias:**
- “Remember this device” (cookie assinado + revogação)
- Bloqueio progressivo (cooldown) após N falhas
- “Sessões ativas” + revogar
- WebAuthn/Passkeys (piloto)

**Critérios de aceite:**
- Pelo menos 1 melhoria entregue + auditada

---

## Ordem recomendada (para reduzir retrabalho)
1. **S4-01** QA Specialist Agent (gates automáticos)
2. **S4-02** Padrão de respostas tributárias BR
3. **S4-03** UX de Login + rate limit + auditoria
4. **S4-04** MFA TOTP + recovery codes
5. **S4-05** SSO (preferencialmente discovery/spikes)
6. **S4-06** Hardening (somente se houver folga)

---

## Dependências e riscos
- **S4-04 MFA** depende de um login sólido e observável (**S4-03**).
- **S4-05 SSO** tem risco alto de mapeamento de claims + tenant scoping (fazer discovery/spikes primeiro).
- **S4-01** reduz risco geral: todo patch passa por validação automatizada.

---

## DoD (Sprint 4 — macro)
- QA Specialist Agent gera relatório Markdown e executa gates (backend + frontend).
- Respostas “validate” seguem template fiscal/tributário BR (PT-BR + BRL + premissas + evidências).
- Login robusto: UX + rate limit + auditoria (sucesso/falha/logout) sem vazamentos.
- MFA TOTP end-to-end + recovery codes + auditoria + testes mínimos.
- (Opcional) SSO: design doc + spikes (ou MVP se houver folga).

