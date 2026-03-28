# M01-CORE — Final Review

| Arquivo | Alteração Realizada | Impacto (ROI/Risco) |
|---|---|---|
| `backend/.env.example` | Inclusão de `POSTGRES_HOST`, `POSTGRES_PORT`, `DB_URL` e `REDIS_DB` para alinhamento de infraestrutura. | ROI alto: padroniza bootstrap de ambiente; risco baixo. |
| `backend/app/crews/chatops_crew.py` | Injeção de dependências de tools, propagação de `transaction_id`, persistência de handoff e logs estruturados por agente/tarefa. | ROI alto: observabilidade e resiliência; risco médio por fluxo crítico de chat. |
| `backend/app/crews/executor.py` | Geração/propagação de `transaction_id` por execução, enriquecendo logs de timeout/erro/sucesso. | ROI alto: rastreabilidade ponta a ponta; risco baixo. |
| `backend/app/crews/nfe_validation_crew.py` | Inversão de dependência para tools e telemetria de handoff com `transaction_id`. | ROI alto: testabilidade e diagnóstico; risco baixo. |
| `backend/app/crews/tools/parse_nfe_xml_tool.py` | Suporte a `transaction_id` no upload S3 para idempotência e correlação transacional. | ROI médio-alto: evita duplicidade em retries; risco baixo. |
| `backend/app/crews/tools/parse_nfse_xml_tool.py` | Suporte a `transaction_id` no upload S3 para idempotência e correlação transacional. | ROI médio-alto: consistência de artefatos; risco baixo. |
| `backend/app/crews/tools/trigger_task_a_tool.py` | Propagação de `transaction_id` para criação de job, idempotency key e enfileiramento Celery. | ROI alto: elimina reprocessamento duplicado; risco médio. |
| `backend/app/crews/tools/validate_fiscal_rules_tool.py` | Enriquecimento de saída com `transaction_id` para cadeia de auditoria. | ROI médio: melhora rastreabilidade; risco baixo. |
| `backend/app/crews/tools/validate_ibscbs_rules_tool.py` | Enriquecimento de saída com `transaction_id` para cadeia de auditoria. | ROI médio: melhora rastreabilidade; risco baixo. |
| `backend/app/main.py` | Ativação do bootstrap de logging JSON no startup da API. | ROI alto: padronização observável; risco baixo. |
| `backend/app/tasks/task_a_validate.py` | Execução idempotente por `transaction_id`, propagação para job/audit e manutenção de status consistente. | ROI alto: resiliência transacional; risco médio. |
| `backend/app/tools/erp_connector_tool.py` | Suporte opcional a `transaction_id` no metadado de importação CSV/XML. | ROI médio: trilha de origem consistente; risco baixo. |
| `backend/app/tools/hubspot_tool.py` | Suporte opcional a `transaction_id` no retorno de integrações CRM. | ROI médio: correlação entre domínio fiscal e CRM; risco baixo. |
| `backend/app/tools/postgres_tool.py` | Ampliação de assinaturas para `transaction_id` em audit/job/artifacts e payloads persistidos. | ROI alto: governança e auditoria unificada; risco médio. |
| `backend/app/tools/s3_tool.py` | Gravação S3 com proteção idempotente orientada a hash + `transaction_id`. | ROI alto: redução de custo e duplicidade; risco médio-baixo. |
| `backend/app/tools/validation_tool.py` | Idempotência nas validações fiscais (`validate_with_tolerance`, `validate_rule_consistency`, `validate_invoice_items`). | ROI alto: consistência de cálculo em retries; risco médio. |
| `frontend/src/app/calculadora/page.tsx` | Propagação de `X-Transaction-Id` na chamada pública e exibição do `transaction_id` no resultado. | ROI médio: depuração no funil público; risco baixo. |
| `frontend/src/app/diagnostico/page.tsx` | Propagação de `X-Transaction-Id` no upload público e exibição do `transaction_id` no diagnóstico. | ROI médio: observabilidade no onboarding; risco baixo. |
| `frontend/src/app/validate-xml/page.tsx` | Exibição de `transaction_id` no resumo da validação autenticada. | ROI médio: rastreio operacional para suporte; risco baixo. |
| `frontend/src/lib/api.ts` | Geração de `transaction_id`, suporte em headers, ajuste de `validateXml` para `multipart/form-data` e normalização de retorno. | ROI alto: compatibilidade real com backend refatorado; risco médio. |
| `frontend/src/lib/types.ts` | Atualização de tipos para aceitar `transaction_id` em request/response de validação XML. | ROI médio: segurança de tipos e menos regressões; risco baixo. |
| `infra/docker-compose.yml` | Hardening de persistência: variáveis explícitas para DB/Redis, Redis AOF e volume dedicado `redis_data`. | ROI alto: confiabilidade e recuperação; risco baixo. |
