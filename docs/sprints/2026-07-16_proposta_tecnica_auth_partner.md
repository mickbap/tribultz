# Proposta técnica definitiva — Autenticação de Atores (Programa de Parceiros, Fase 1)

Data: 2026-07-16 · v2 (revisão pedida: generalizar para "ator", `tenant_id` vira contexto, não identidade)
Escopo: **como** a autenticação passa a suportar múltiplos atores (`Tenant User`, `Partner`, futuros institucionais) sem exceção por ator e sem regressão. RFC-0026 (`tribultz-brain`) decide o **porquê**; este documento decide o **como** (ADR-0010).

> **Não implementado ainda.** Aguardando aprovação antes de qualquer código.

## Achado que sustenta a proposta

`get_current_user` (`backend/app/api/deps.py`) decodifica o JWT e resolve **apenas** `sub` (id do `User`) — não usa `tenant_id`/`role` do payload para nada além de validar a forma. A autorização real de cada router vem do **objeto `User` carregado do banco**, não do JWT. Isso significa: a identidade principal do sistema **já é o `User`**, não o `Tenant` — só faltava o modelo deixar isso explícito.

## 1. Modelo final do JWT

```json
{
  "sub": "<user.id>",
  "actor_type": "tenant" | "partner",
  "role": "<user.role>",
  "tenant_id": "<tenant.id> | null",
  "partner_id": "<partner.id> | null",
  "exp": 0,
  "iat": 0
}
```

- `sub` continua a âncora de identidade — inalterado para todo usuário existente.
- `actor_type` é novo: declara **que tipo** de ator está autenticado. Não substitui `role` (que continua sendo o papel dentro do contexto do ator — `admin`/`contador`/`user` para tenant, futuramente algo para partner se necessário); `actor_type` é ortogonal — declara o **domínio**, `role` declara a **permissão**.
- `tenant_id`/`partner_id` são **contextuais**: exatamente um dos dois é preenchido, conforme `actor_type`. Futuro ator institucional adicionaria seu próprio campo contextual (ex.: `institution_id`) sem tocar nos demais.
- `TokenPayload` (Pydantic) generaliza: `actor_type` obrigatório; `tenant_id`/`partner_id` opcionais (`Optional[str] = None`).

## 2. Modelo final do contexto autenticado

```
get_current_actor(token, db) -> User
    # nível mais baixo: decodifica JWT, valida TokenPayload genérico,
    # busca User por sub, checa is_active/deleted_at.
    # É o que get_current_user faz HOJE — só generaliza o schema validado.

get_current_user(actor: User = Depends(get_current_actor)) -> User
    # MANTÉM nome, assinatura e tipo de retorno atuais.
    # Ganha uma checagem nova: actor.actor_type == "tenant" (equivalente a
    # actor.tenant_id is not None), senão 403 explícito.
    # Todo router existente que já usa Depends(get_current_user) continua
    # funcionando sem NENHUMA mudança de código — só fica mais estrito:
    # um ator partner batendo aqui agora recebe 403 em vez de lista vazia
    # (é uma correção de robustez, não uma regressão).

get_current_partner(actor: User = Depends(get_current_actor)) -> User
    # nova, simétrica: exige actor.actor_type == "partner", senão 403.
    # Usada só pelas rotas novas da área do parceiro.
```

`actor_type` é uma **propriedade computada** no model `User` (`"partner" if partner_id else "tenant"`) — não é uma coluna redundante no banco, evita divergência entre coluna e realidade.

Nenhuma duplicação de infraestrutura: `get_current_user` e `get_current_partner` são as duas finas camadas sobre o mesmo `get_current_actor` — um único mecanismo de sessão, dois filtros de contexto.

## 3. Impacto nos routers existentes

**Zero mudança de código** nos ~17 routers hoje tenant-scoped (`jobs`, `tasks`, `sped`, `compliance`, `audit`, `reports`, `documents`, `exceptions`, `feedback`, `credits`, `support`, `validate`, `validation`, `validate_xml`, `split_payment`, `public_api`, `auth`) — todos continuam com `Depends(get_current_user)`, mesma assinatura, mesmo tipo de retorno (`User`). O único efeito observável: um ator `partner` que tentasse acessá-los recebe **403 explícito** em vez do comportamento anterior (lista vazia, pela ausência de `tenant_id` — já auditado antes: nenhum desses routers faz cast direto que quebraria, então isso é estritamente uma melhoria, não uma regressão).

**Regressão para usuários existentes:** nenhuma. Todo `User` hoje já tem `tenant_id` preenchido → `actor_type` computado é sempre `"tenant"` → `get_current_user` continua aceitando exatamente como hoje.

## 4. Estratégia de migração

1. **Migration**: `users.tenant_id` → nullable. Novo `users.partner_id` (UUID, nullable, FK `partners.id`, `ondelete=CASCADE`). `CHECK` constraint: exatamente um de (`tenant_id`, `partner_id`) não-nulo — garante estruturalmente que todo `User` tem exatamente um domínio, nunca os dois, nunca nenhum. Índice único parcial `UNIQUE (email) WHERE partner_id IS NOT NULL` (a constraint atual `(tenant_id, email)` não previne duplicidade quando `tenant_id` é `NULL`, por semântica de SQL).
2. **`User` model**: propriedade computada `actor_type`.
3. **`schemas/auth.py`**: generalizar `TokenPayload` (`actor_type` obrigatório, `tenant_id`/`partner_id` opcionais).
4. **`api/deps.py`**: introduzir `get_current_actor`; redefinir `get_current_user` como camada fina sobre ele (compat); adicionar `get_current_partner`.
5. **`routers/auth.py`**: login/criação de conta passam a montar o JWT com `actor_type` + o campo contextual certo. Fluxo de criação de conta do Partner reaproveita convite/primeiro acesso/OTP/senha já existentes.
6. **Nenhuma mudança** nos demais routers.
7. **Testes (antes da implementação, TDD):**
   - Regressão: usuário tenant existente loga e acessa tudo exatamente como hoje.
   - Ator partner recebe 403 explícito em rota tenant-scoped.
   - Ator tenant recebe 403 explícito em rota partner-scoped (`get_current_partner`).
   - `CHECK constraint` rejeita `User` com os dois campos ou nenhum preenchido.
   - Fluxo completo do Partner: convite → primeiro acesso → OTP → senha → login → dashboard só-leitura.

## Critério de aceite desta proposta

Aprovada quando: (1) o modelo de JWT/contexto acima fizer sentido; (2) a estratégia de compatibilidade (`get_current_user` inalterado por fora, mais estrito por dentro) for aceita; (3) a migration/CHECK constraint forem aceitas. Após aprovação, sigo com TDD antes da implementação em si.
