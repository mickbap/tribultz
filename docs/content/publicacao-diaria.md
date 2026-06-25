# Runbook — Publicação diária de conteúdo (Soro → Blog + Social)

Fluxo de publicação com **gate de revisão fiscal** e **corretor automático** (#349/#350).
Princípio: nada que cite alíquota/código/prazo vai ao ar sem revisão. O corretor por código
(`contentLint`) reduz o trabalho — auto-corrige o determinístico e sinaliza o resto.

## Visão geral dos canais

| Canal | Como publica | Gate |
|-------|--------------|------|
| **Blog** (tribultz.com.br/blog) | GitHub Action lê o RSS do Soro → abre **PR `needs-review`** (com auto-fixes aplicados) | PR review + merge |
| **Instagram / Facebook** | **Publish manual no Soro** (autoshare **DESLIGADO**) | revisão do draft no Soro |
| **LinkedIn** | (pendente #351) RSS do blog → agendador | herda o gate do blog |

## Rotina diária (≈10 min)

1. **Soro — revisar o draft**
   - Abrir o Soro → ler o artigo do dia.
   - Checklist fiscal (o que o `Topics to Avoid` cobre):
     - [ ] Alíquota cita a **fase**? (2026 = CBS 0,9% / IBS 0,1%; pleno = 8,8% / 17,7%)
     - [ ] Sem código/rejeição/artigo/prazo **inventado**.
     - [ ] Sem **promessa** ("garante", "100%", "zero rejeição", "sem multa").
   - Corrigir no editor do Soro o que precisar (principalmente a linha da alíquota).

2. **Soro — publicar** (com autoshare OFF) → posta no **IG/FB** a versão revisada e
   coloca o item no feed RSS.

3. **Blog — revisar o PR** (a Action abre sozinha, diária; ou rode `workflow_dispatch`)
   - O PR já vem com **auto-fixes** do `contentLint` (ex.: nota de vigência da alíquota).
   - No PR: ler o **preview da Vercel**, conferir `frontend-build` verde.
   - Preencher `tags`, ajustar `category` e **`legalRefs`** (base legal).
   - **Merge** → Vercel publica no blog.

## Corretor de conteúdo (mecanismo por código)

- **Automático:** roda na geração (pipeline Soro) e aplica auto-fixes seguros.
- **Sob demanda / posts existentes:**
  ```bash
  cd frontend
  npm run content:lint        # checa e reporta (falha se houver correção fiscal pendente)
  npm run content:lint:fix    # aplica os auto-fixes nos .mdx
  ```
- Regras: `ALIQUOTA_PLENA_SEM_CONTEXTO` (auto-fix), `PROMESSA` (warn), `LEGALREFS_VAZIO`/`TAGS_VAZIO` (warn).

## Não fazer
- ❌ **Habilitar autoshare IG/FB** — conteúdo fiscal iria ao ar sem revisão.
- ❌ **Mergear PR de blog** sem ler o conteúdo e conferir o build.
- ❌ Publicar no Soro um draft com alíquota sem contexto de fase.

## Ativação (uma vez)
- Secret **`SORO_RSS_URL`** no repo (feed habilitado no Soro). `?include=drafts` permite revisar antes do social.
- Autoshare IG/FB **desligado** no Soro.
