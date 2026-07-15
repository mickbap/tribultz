---
name: feedback_sqlalchemy_cast_syntax
description: Nunca usar ::type cast do PostgreSQL ao lado de :param em sqlalchemy.text() — conflito de parser quebra queries silenciosamente em prod
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 04cdcbf6-aacd-4e03-83e6-c6800b214cc8
---

**Regra:** Dentro de `sqlalchemy.text()`, nunca combinar parâmetros nomeados (`:param`) com o operador de cast do PostgreSQL (`::type`). O parser do SQLAlchemy interpreta `:start:` (de `:start::date`) como nome de parâmetro malformado → `psycopg2.errors.SyntaxError` em runtime.

**Why:** Bug descoberto em produção em 30/05/2026 durante o primeiro teste de pagamento real. O dashboard inteiro retornava 500 para qualquer usuário logado. O erro é silencioso no desenvolvimento (sem banco real), explode só em prod.

**How to apply:** Sempre substituir:
```sql
-- ❌ Errado
AND created_at >= :start::date

-- ✅ Correto
AND created_at >= CAST(:start AS date)
```
Ao revisar ou escrever queries com `sqlalchemy.text()`, verificar ativamente se há `::` precedido de `:param`. Vale para qualquer cast: `::uuid`, `::date`, `::text`, `::int`, etc.

**Arquivos corrigidos:** `app/routers/compliance.py`, `app/tasks/task_i_compliance.py`  
**Issue:** #272  
**Relacionado a:** [[feedback_bash_vs_native_tools]]
