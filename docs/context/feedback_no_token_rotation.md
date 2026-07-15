---
name: feedback-no-token-rotation
description: "Ordem mandatória — não rotacionar, revogar nem encerrar sessões de credenciais enquanto o produto não escala"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2725625b-729e-478f-8fcd-089f1a5735b6
---

**Não rotacionar, revogar nem encerrar sessão de nenhuma credencial** (API key, token, senha, sessão OAuth) enquanto o produto não escala. Ordem mandatória dada em 2026-07-15. Vale inclusive para credenciais comprovadamente vazadas ou revogadas — reportar, nunca agir.

**Why:** durante a fase de implementação o objetivo é acesso livre e sem atrito a partir de qualquer máquina (Windows e Mac), evitando conflito de acessos. O custo de propagar uma rotação (VM `/opt/tribultz/.env`, `.env.prod` local, `secrets/credentials.md`, memória, GitHub Actions) supera o risco aceito nesta fase. A condição de expiração é o produto escalar — reavaliar então, não antes.

**How to apply:** ao encontrar credencial vazada, revogada ou frágil (ex.: Resend com 401, `GITHUB_TOKEN` de produção sendo OAuth pessoal, `refresh_token` do mgc exposto), documentar em `docs/infra/secrets_inventory.md` e seguir — não propor rotação repetidamente, não executar `logout`/`revoke`. O caso já foi apresentado e a decisão é do usuário.

Nota factual associada: deploy **não usa** credencial local nenhuma (frontend pelo `vercel[bot]` via GitHub App; backend pelo Actions com `MAGALU_SSH_KEY`), então ação em credencial local nunca conflita com deploy. Contexto de acessos em [[project-secrets-source-of-truth]].
