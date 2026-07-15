---
name: project-secrets-source-of-truth
description: "A fonte de verdade dos segredos é /opt/tribultz/.env na VM, não o .env.prod local — que sofre drift silencioso"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2725625b-729e-478f-8fcd-089f1a5735b6
---

A fonte de verdade dos segredos de produção é **`/opt/tribultz/.env` na VM Magalu** (root, `0600`) — o arquivo que os containers leem. O `.env.prod` local é apenas um espelho e **sofre drift em silêncio**.

Em 2026-07-15 o `.env.prod` local estava 3 meses defasado (8/abr vs 29/jun na VM) e não tinha `GITHUB_TOKEN`, `NEWS_PUBLISH_TOKEN`, `SENTRY_DSN` e `SENTRY_TRACES_SAMPLE_RATE`, além de ter HubSpot desligado quando a VM tem ligado com token real. Foi sincronizado nessa data.

**Why:** tratar a cópia local como referência (para migrar a um cofre, popular outra máquina ou fazer deploy) apaga silenciosamente tokens que só existem na VM. Foi exatamente o risco que quase se materializou numa tentativa de mover os segredos para um cofre em Docker.

**How to apply:** antes de qualquer operação que trate segredos como fonte, puxar da VM primeiro — `ssh -i ~/.ssh/id_ed25519 ubuntu@201.54.20.18 'sudo cat /opt/tribultz/.env' > .env.prod` (com backup antes). Para detectar drift sem expor valores, comparar o md5 de cada valor chave a chave. Inventário completo, runbook de validação e onboarding de máquina nova (incl. Mac) em `docs/infra/secrets_inventory.md`.

Pendências abertas em 2026-07-15: chave Resend revogada (401) e `GITHUB_TOKEN` de produção sendo o OAuth pessoal do `gh` CLI — detalhes em [[reference-services]]. Infra da VM em [[reference-magalu-cloud]].
