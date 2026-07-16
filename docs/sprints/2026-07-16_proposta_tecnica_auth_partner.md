# Proposta técnica definitiva — autenticação do Partner (Programa de Parceiros, Fase 1)

Data: 2026-07-16
Escopo: **como** estender a infraestrutura de autenticação existente para um novo ator (`Partner`), sem criar Tenant artificial e sem alterar a semântica do domínio (RFC-0026, `tribultz-brain`, decide o **porquê**; este documento decide o **como** — ADR-0010).

> **Não implementado ainda.** Aguardando aprovação antes de qualquer código.

## Por que não dá pra reaproveitar sem mudança nenhuma

Investigação no código real (`backend/app/api/deps.py`, `backend/app/routers/auth.py`, `backend/app/schemas/auth.py`):

- `get_current_user` (dependência usada por todos os routers) decodifica o JWT e busca o `User` por `id` — **não olha `tenant_id` nesta camada**. Ou seja, o mecanismo central de sessão já é agnóstico de tenant.
- `TokenPayload.tenant_id` é `str` **obrigatório** (não `Optional`) no schema Pydantic do payload do JWT. É o único ponto que **hoje** impede um usuário sem tenant de logar — a validação do payload rejeitaria o token.
- `User.tenant_id` é `nullable=False` no banco — segundo ponto que precisa mudar.
- O `/login` busca o usuário **só por e-mail**, sem filtrar por tenant (`select(User).where(User.email == login_data.email)`) — já é compatível com um ator sem tenant, zero mudança necessária aqui.
- `role` já é um campo livre (`String(50)`, hoje com valores como `admin`/`contador`/`user`) — adicionar o valor `"partner"` é extensão natural de um padrão que já existe, não um conceito novo.

## O que muda (mínimo necessário)

1. **Migration**: `users.tenant_id` → nullable. Novo campo `users.partner_id` (UUID, nullable, FK `partners.id`, `ondelete=CASCADE`). Novo índice único parcial para e-mail entre parceiros (`UNIQUE (email) WHERE partner_id IS NOT NULL`) — a constraint atual `(tenant_id, email)` não pega duplicidade quando `tenant_id` é `NULL` (regra de SQL: `NULL != NULL`), então precisa de uma constraint própria pro caso de parceiro.
2. **`TokenPayload.tenant_id`**: `str` → `Optional[str] = None`.
3. **`auth.py` (login/registro):** branch explícito — se `user.partner_id` estiver setado (ator é parceiro), o JWT carrega `tenant_id: None`, `partner_id: <id>`, `role: "partner"`; caso contrário, comportamento **inalterado**.
4. **Nova dependência** `get_current_partner` (mesmo padrão de `get_current_user`, só que também exige `role == "partner"` e `partner_id` não nulo) — usada exclusivamente pelas rotas novas da área do parceiro.
5. **Fluxo de criação da conta**: reaproveita convite + primeiro acesso (link assinado → OTP → senha) já existentes — só muda o "o quê" está sendo criado (`User` com `partner_id`, sem `tenant_id`), não o "como" do fluxo.

## O que **não** muda

- Nenhum dos ~17 routers hoje tenant-scoped (`jobs`, `tasks`, `sped`, `compliance`, `audit`, `reports`, etc.) precisa de alteração de código. Auditei os usos de `current_user.tenant_id` neles: nenhum faz cast direto pra UUID sem tratamento (`cast(UUID, ...)`) que quebraria com `None` — todos usam `str(current_user.tenant_id)` (vira a string `"None"`, inofensivo) ou comparações de filtro (`WHERE tenant_id = None` retorna vazio, nunca vaza dado de outro tenant). Um ator parceiro batendo por engano nessas rotas recebe lista vazia, nunca dado de terceiro.
- `Tenant` continua significando exclusivamente empresa-cliente. Nenhuma linha nova em `tenants` para representar um Partner.
- `get_current_user`, `/login`, `/register` (fluxo de tenant) — zero mudança de comportamento para usuários existentes.

## Reforço de defesa em profundidade (recomendado, não bloqueante)

Como melhoria de robustez (não estritamente necessária pra correção, já que não há vazamento de dado possível): adicionar uma dependência `require_tenant_user` que os routers tenant-scoped podem adotar aos poucos, retornando 403 explícito em vez de lista vazia se um ator parceiro tentar acessá-los. Proponho tratar isso como item de follow-up, não bloqueador desta entrega.

## Modelo de dados resultante

```
users
  id              uuid PK
  tenant_id       uuid FK tenants.id, NULLABLE  (era NOT NULL)
  partner_id      uuid FK partners.id, NULLABLE (novo)
  role            varchar(50)  -- ganha o valor "partner"
  email, password_hash, full_name, is_active, ... (inalterados)

  CHECK: exatamente um de (tenant_id, partner_id) deve ser não-nulo
         (um User é de um Tenant OU de um Partner, nunca dos dois, nunca de nenhum)
```

O `CHECK constraint` acima é a garantia estrutural de que a separação de domínio (Partner não é Tenant) fica **impossível de violar por acidente**, não só por convenção de código.

## Critério de aceite desta proposta

Aprovada quando: (1) a migration acima fizer sentido; (2) o `CHECK constraint` for aceito como guardrail estrutural; (3) o item "defesa em profundidade" for aceito como follow-up, não bloqueador. Após aprovação, sigo com TDD (testes de isolamento partner↔tenant, testes de login/primeiro acesso reutilizando os fluxos existentes) antes da implementação em si.
