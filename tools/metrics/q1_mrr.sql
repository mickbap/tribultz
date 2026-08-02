-- MRR real por plano — exclui tenants com Early Grant ativo (Founding
-- Partners/early adopters não geram receita, mesmo com subscription
-- "active" apontando pra um plano pago). Sem isso, MRR fica inflado
-- exatamente na métrica que sustenta o cálculo de payback do CAC.
SELECT p.slug AS plano,
       COUNT(s.id) FILTER (WHERE eg.id IS NULL) AS assinantes_pagantes,
       COUNT(s.id) FILTER (WHERE eg.id IS NOT NULL) AS assinantes_via_grant,
       p.price_cents / 100.0 AS preco_reais,
       COALESCE(SUM(p.price_cents) FILTER (WHERE eg.id IS NULL), 0) / 100.0 AS mrr_reais
FROM subscriptions s
JOIN plans p ON s.plan_id = p.id
LEFT JOIN early_grants eg
       ON eg.tenant_id = s.tenant_id
      AND eg.status = 'active'
      AND now() BETWEEN eg.starts_at AND eg.ends_at
WHERE s.status = 'active'
GROUP BY p.slug, p.price_cents
ORDER BY mrr_reais DESC;
