-- Ativação: tempo entre criação do tenant e a primeira validação (validate_xml)
-- concluída com sucesso.
WITH primeira_validacao AS (
  SELECT tenant_id, MIN(created_at) AS primeira_ok
  FROM jobs
  WHERE job_type = 'validate_xml'
    AND status   = 'SUCCESS'
  GROUP BY tenant_id
)
SELECT COUNT(*)                                                          AS tenants_ativados,
       ROUND(AVG(EXTRACT(EPOCH FROM (pv.primeira_ok - t.created_at))
             / 86400.0)::numeric, 1)                                     AS dias_medios_ate_ativar
FROM primeira_validacao pv
JOIN tenants t ON t.id = pv.tenant_id;
