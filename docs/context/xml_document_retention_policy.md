# Política de retenção de documentos (XMLs) — Escopo 4.3, go-live de billing

Referência técnica interna. Versão pública (customer-facing): `/privacy` seção 5 e `/refund-policy`.

## Retenção

- **Prazo**: 12 meses a partir do upload (`Document.created_at`).
- **Mecanismo**: task Celery `documents.purge_expired`
  (`backend/app/tasks/task_j_retention.py`), rodando mensalmente (dia 1,
  02:30 BRT, via `beat_schedule` em `celery_app.py`).
- **O que é apagado**: o objeto no S3/MinIO (`storage_key`) + a linha em
  `documents`. Falha ao apagar do S3 mantém a linha no banco para nova
  tentativa no próximo ciclo — não perde o registro silenciosamente, mas
  também não deixa "órfão" (linha sem o objeto correspondente) fora de um
  cenário de erro temporário.
- **Por quê 12 meses**: cobre um ciclo fiscal completo (a maioria das
  obrigações acessórias e prazos de fiscalização operam em base anual),
  sem reter indefinidamente XML de terceiros que a Tribultz processa mas
  não é parte do negócio manter — minimização de dado (LGPD art. 6º, III).

## Criptografia em repouso

- `backend/app/tools/s3_tool.py` `put_object()` passa
  `ServerSideEncryption: "AES256"` explicitamente em toda gravação.
- Motivo de ser explícito no código, não implícito na infra: a
  documentação oficial da Magalu Object Storage (verificada em
  docs.magalu.cloud, 28/07/2026) menciona "criptografia avançada" de
  forma genérica, sem confirmar SSE em repouso especificamente para
  Object Storage — não dá pra tratar como garantido por padrão.
- MinIO (dev local) e provedores S3-compatíveis en geral suportam
  SSE-S3/AES256 nativamente — sem dependência de KMS externo.

## O que NÃO está coberto por este documento

- Retenção de `AdminAuditLog` (log de billing, Escopo 5.3) — regra
  oposta: retenção MÍNIMA de 12 meses (não há job de descarte associado
  a esse prazo; é um piso de auditoria, não um teto de privacidade).
- Dados de billing (`payments`, `subscriptions`) — não têm job de
  descarte; ficam sujeitos à retenção fiscal/contábil padrão da empresa,
  fora do escopo desta política específica de XML.
