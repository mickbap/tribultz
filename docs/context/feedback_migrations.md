---
name: Rodar migrations sem pedir confirmação
description: Migrations de produção (alembic upgrade head) devem ser executadas sem pedir confirmação — fazem parte da operação normal de deploy
type: feedback
originSessionId: 4a99577d-66f7-4eb8-9afc-dc28f63fb249
---
Rodar `alembic upgrade head` em produção via SSH não requer confirmação prévia.

**Why:** É parte da operação normal de deploy. Pedir confirmação é overhead desnecessário para o techlead.

**How to apply:** Ao detectar migrations pendentes na VM de produção, aplicar diretamente e reportar o resultado.
