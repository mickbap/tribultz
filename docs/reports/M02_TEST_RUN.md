# M02 Test Run

## Objetivo
Validar localmente o fluxo assíncrono do M02:

1. a API responde `202 Accepted` sem bloquear a thread;
2. o `task_id` retornado existe na tabela `jobs`;
3. o polling em `GET /api/v1/tasks/{task_id}` lê apenas o Postgres.

## Subir a stack

```bash
docker compose -f infra/docker-compose.yml up -d db redis minio api worker beat
```

Verificações rápidas:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
docker compose -f infra/docker-compose.yml ps
```

## Obter um token JWT

Use uma conta já cadastrada e com email verificado.

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "SEU_EMAIL",
    "password": "SUA_SENHA",
    "tenant_slug": "default",
    "captcha_token": ""
  }'
```

Copie o campo `access_token` da resposta.

Exemplo de export para shell:

```bash
export TOKEN="COLE_O_ACCESS_TOKEN_AQUI"
```

No PowerShell:

```powershell
$env:TOKEN="COLE_O_ACCESS_TOKEN_AQUI"
```

## Disparar uma tarefa assíncrona

Exemplo com `POST /api/v1/tasks/validate`:

```bash
curl -i -X POST http://localhost:8000/api/v1/tasks/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_number": "INV-M02-001",
    "issue_date": "2026-03-28",
    "declared_cbs": "1.00",
    "declared_ibs": "0.50",
    "items": [
      {
        "sku": "SKU-1",
        "description": "Item de teste M02",
        "base_amount": "100.00",
        "cbs_rule_code": "STD_CBS",
        "ibs_rule_code": "STD_IBS"
      }
    ]
  }'
```

Resposta esperada:

```json
{
  "task_id": "UUID_DO_JOB",
  "job_id": "UUID_DO_JOB",
  "status": "QUEUED"
}
```

O status HTTP esperado e `202 Accepted`.

## Polling do status

Substitua `UUID_DO_JOB` pelo valor retornado no passo anterior.

```bash
curl -s http://localhost:8000/api/v1/tasks/UUID_DO_JOB \
  -H "Authorization: Bearer $TOKEN"
```

Resposta esperada enquanto o worker ainda nao concluiu:

```json
{
  "task_id": "UUID_DO_JOB",
  "job_id": "UUID_DO_JOB",
  "job_type": "task_a_validate_cbs_ibs",
  "status": "QUEUED",
  "payload": {
    "invoice_number": "INV-M02-001"
  },
  "result": null,
  "error_message": null,
  "created_at": "2026-03-28T00:00:00+00:00",
  "updated_at": "2026-03-28T00:00:00+00:00"
}
```

Quando o worker iniciar, o status deve transicionar para `RUNNING`. Ao final, deve virar `SUCCESS` ou `FAILED`.

## Loop de polling

```bash
while true; do
  curl -s http://localhost:8000/api/v1/tasks/UUID_DO_JOB \
    -H "Authorization: Bearer $TOKEN"
  echo
  sleep 2
done
```

No PowerShell:

```powershell
while ($true) {
  Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/tasks/UUID_DO_JOB" `
    -Headers @{ Authorization = "Bearer $env:TOKEN" }
  Start-Sleep -Seconds 2
}
```

## Swagger

Alternativa manual:

1. abrir `http://localhost:8000/docs`;
2. executar `POST /api/v1/auth/login`;
3. clicar em `Authorize` e colar o bearer token;
4. executar `POST /api/v1/tasks/validate`;
5. executar `GET /api/v1/tasks/{task_id}`.

## Resultado esperado

- `api` responde imediatamente com `202`;
- `worker` consome a tarefa via Redis;
- `jobs.status` evolui em Postgres;
- `GET /api/v1/tasks/{task_id}` retorna `404` se o job nao existir para o tenant autenticado.
