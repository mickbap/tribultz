---
name: feedback-bash-vs-native-tools
description: Não usar Bash (cat/grep/find/ls/head/tail/wc) quando há Read/Grep/Glob nativos — bypassa o hook do rtk e queima tokens
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 66d28250-4616-49f4-b284-b3dafc9878a4
---

Quando precisar ler arquivos, buscar conteúdo ou listar diretórios, usar SEMPRE as tools dedicadas (Read, Grep, Glob) em vez de chamar `cat`, `grep`, `find`, `ls`, `head`, `tail`, `wc` via Bash.

**Why:** O `rtk discover` em 24 sessões mostrou que esses comandos foram chamados 280+ vezes via Bash (cat 46×, grep 117×, find 51×, ls 59×, wc 7×). O hook do rtk só intercepta Bash, mas mesmo com filtragem o ganho por chamada é baixo (~8-15%) — enquanto as tools nativas evitam o overhead completamente e produzem output mais limpo. Resultado: gastamos tokens à toa e ainda assim o gain agregado do rtk fica diluído (12% global em vez do potencial real).

**How to apply:**
- Ler arquivo conhecido → **Read** (nunca `cat`, `head`, `tail`)
- Buscar conteúdo/regex → **Grep** (nunca `grep`, `rg`, `Select-String`)
- Buscar arquivos por nome/padrão → **Glob** (nunca `find`, `ls -R`, `Get-ChildItem -Recurse`)
- Contar linhas → **Read** + contar, ou aceitar e usar Bash se for one-shot
- Só usar Bash para coisas que são genuinamente shell: git, gh, npm, docker, ssh, curl, pytest, ruff, etc.

Exceção legítima: pipelines complexos onde a combinação shell é mais simples (`gh pr list ... | head`) — aí Bash compensa.
