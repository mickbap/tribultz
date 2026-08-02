-- Retenção por coorte de criação — NÃO é conversão trial→pago de verdade.
-- subscriptions.status é uma máquina de estado de uma coluna só, sem
-- histórico de transição, e trial_days=3 faz "trial" tender a 0 pra
-- qualquer coorte com mais de poucos dias. Isto mostra o status ATUAL de
-- cada coorte de cadastro — conversão trial→pago real vem do funil
-- comercial (Rumy), não do banco.
SELECT date_trunc('month', created_at)::date AS coorte,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE status = 'trial') AS trial,
       COUNT(*) FILTER (WHERE status = 'active') AS active,
       COUNT(*) FILTER (WHERE status IN ('pending','past_due')) AS pagamento_pendente,
       COUNT(*) FILTER (WHERE status IN ('cancelled','expired')) AS encerrado,
       ROUND(COUNT(*) FILTER (WHERE status = 'active')::numeric / NULLIF(COUNT(*), 0), 4) AS taxa_retencao
FROM subscriptions
GROUP BY 1
ORDER BY 1;
