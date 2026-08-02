-- Consumo do plano contratado por período (proxy de engajamento no v1;
-- detalhe por rota/feature fica pra v2).
SELECT period,
       SUM(validations_used)  AS validacoes,
       SUM(ai_messages_used)  AS mensagens_ia
FROM usage_tracking
GROUP BY period
ORDER BY period;
