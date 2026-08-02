-- Cancelamentos por mês. Aproximação: sem snapshot histórico de status,
-- não dá pra calcular taxa exata sobre a base ativa no início de cada mês
-- — isto é tendência (contagem absoluta), não taxa precisa por coorte.
SELECT date_trunc('month', cancelled_at)::date AS mes,
       COUNT(*)                                 AS cancelados
FROM subscriptions
WHERE cancelled_at IS NOT NULL
GROUP BY 1
ORDER BY 1;
