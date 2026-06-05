# Gap Analysis SEO — Tribultz × Tax Radar

**Data:** 2026-06-05
**Autor:** Tribultz Techlead
**Contexto:** após diagnóstico de 05/jun, Tax Radar (taxradar.app) aparece em 2 das 3 buscas operacionais top que perseguimos, **enquanto tribultz.com.br não aparece em nenhuma**. Este documento compara lado a lado e propõe ações concretas.

---

## 1. Métricas comparativas

### Tax Radar — 3 posts que rankeiam

| Métrica | `cclasstrib-como-mapear-…` | `rejeicoes-nfe-ibs-cbs-…` | `como-classificar-ncm-…` | **Média** |
|---|---:|---:|---:|---:|
| Palavras | 2.514 | 2.312 | 3.194 | **2.673** |
| Headings (H1-H3) | 31 | 25 | 27 | **27,7** |
| Tabelas HTML | 8 | 9 | 4 | **7** |
| Imagens | 2 | 2 | 2 | **2** |
| Links internos | 45 | 42 | 59 | **48,7** |
| Perguntas FAQ schema | 5 | 5 | 6 | **5,3** |
| Schemas presentes | `Article`, `BreadcrumbList`, `FAQPage`, `Person`, `Organization`, `WebPage`, `ImageObject`, `ListItem` | idem | idem | — |
| Publicado | 2026-02-08 | 2026-02-11 | 2026-01-18 | jan-fev/2026 |
| Atualizado | 2026-03-02 | 2026-03-02 | 2026-03-01 | mar/2026 |

### Tribultz — 5 páginas equivalentes (probe em prod)

| Métrica | `/` | `/classificacao` | `/diagnostico` | `/calculadora` | `/pricing` |
|---|---:|---:|---:|---:|---:|
| Palavras renderizadas | 502 | **8** ⚠️ | 174 | **70** ⚠️ | 395 |
| Headings | 12 | **0** ⚠️ | 2 | **0** ⚠️ | 9 |
| Tabelas | 0 | 0 | 0 | 0 | 1 |
| Imagens | 0 | 0 | 0 | 0 | 0 |
| Links internos | 31 | 8 | 27 | 27 | 22 |
| Perguntas FAQ | 5 | 0 | 4 | 4 | 4 |
| Schemas | `Org`, `SoftwareApp`, `FAQ` | **nenhum** ⚠️ | `Org`, `WebApp`, `FAQ` | `Org`, `WebApp`, `FAQ` | `Org`, `Product`, `AggregateOffer`, `FAQ` |

> ⚠️ **/classificacao e /calculadora retornam praticamente vazias para o Googlebot.** Ambas são páginas client-rendered (`"use client"`) — o bot pode ver `JsonLd` (server component) mas não o corpo da ferramenta. **Isto é um bug de SEO crítico** que invalida boa parte do trabalho de schema feito no PR #295 para essas duas rotas.

---

## 2. Estrutura recorrente dos posts vencedores

Padrão identificado nos 3 posts do Tax Radar — **todos eles têm**:

1. H1 com keyword exata da query-alvo
2. H2 “O que é …” (definição)
3. H2 “Quem precisa se preocupar / Quem está sujeito”
4. H2 com passo-a-passo numerado (geralmente 3-6 etapas com H3)
5. H2 “Erros comuns / Erros que geram multa” com sub-itens H3
6. H2 “Pontos de atenção operacional” (seção formulaica recorrente — ótimo para reaproveitamento de template)
7. H2 “O que fazer a partir daqui” (CTA + funil)
8. H2 “Perguntas frequentes” (5-6 Q&A, espelhadas em FAQPage schema)
9. H2 “Fundamentação legal” (tabela com LC/Convênio/Decreto → autoridade E-E-A-T)
10. H2 “Artigos Relacionados” (3 posts cross-link → crowd autoridade interna)
11. Bloco “Quantos produtos da sua empresa têm NCM incorreto?” (lead magnet recorrente)

A página tem 2 imagens (provavelmente diagramas), 4-9 tabelas de referência, e 42-59 links internos. **A densidade de tabela é o sinal mais forte de E-E-A-T** que o Google interpreta — referência canônica.

---

## 3. Gaps prioritários

### 🔴 Crítico — bug técnico que invalida SEO já feito

**Gap 1: Páginas-ferramenta client-rendered não entregam conteúdo ao Googlebot.**
- `/classificacao`: 8 palavras renderizadas, 0 headings
- `/calculadora`: 70 palavras, 0 headings
- O `<JsonLd>` aparece (server component), mas o JSON-LD pode ser penalizado se o conteúdo da página não bater com o schema declarado.
- **Ação:** mover o copy explanatório + FAQ visível + headings para Server Component (acima da ferramenta interativa). Cobertura mínima 800-1000 palavras de copy estático antes do componente client.

### 🟠 Estrutural — falta de conteúdo

**Gap 2: Não temos blog.**
- Tax Radar tem 3 posts pilares + relacionados (~10+ posts no eixo NCM/cClassTrib). Cada post tem dateModified atualizado (refresca o sinal de freshness do Google).
- **Ação:** sistema de blog MDX em `/blog/*` com Article schema + BreadcrumbList + Person schema (autor com credenciais).

**Gap 3: Posts pilares ausentes.**
- Não temos artigo para as 3 queries-âncora:
  1. `cClassTrib` (eles têm post de 2.514 palavras)
  2. `Rejeição 1024` / `Rejeição NF-e CBS/IBS` (eles têm 2.312 palavras)
  3. `Como classificar NCM` (eles têm 3.194 palavras)
- **Ação:** escrever os 3 posts pilares espelhando a estrutura recorrente (seção 2 acima).

### 🟡 Schema — incompleto

**Gap 4: Faltam BreadcrumbList, Article e Person schemas.**
- `BreadcrumbList` aparece em 100% dos posts deles. Resulta em breadcrumb visível no SERP.
- `Person` (autor) + credenciais (ex: `jobTitle`, `worksFor`) consolida E-E-A-T — sinal crítico em YMYL (Your Money Your Life), categoria fiscal.
- `Article` schema (não SoftwareApplication) é o esquema certo para post de blog.
- **Ação:** estender `components/seo/schemas.ts` com helpers `articleSchema()`, `breadcrumbsSchema()`, `personSchema()`.

### 🟡 Internal linking — densidade muito baixa

**Gap 5: Cross-linking quase inexistente.**
- Tax Radar tem 42-59 links internos por post. Cada post linka para 3 outros posts + páginas-ferramenta.
- Tribultz tem 8-31 links internos por página, e nenhum link para conteúdo educacional (porque não temos conteúdo).
- **Ação:** padrão de internal linking — toda página-ferramenta linka para post correspondente, todo post linka para 3 outros posts + página-ferramenta + CTA.

### 🟢 Conteúdo recorrente — replicável

**Gap 6: Falta seção "Fundamentação Legal" estilo tabela.**
- Eles têm `<table>` listando LC 214, LC 227, Convênio 142, NTs por artigo. Tabelas em HTML viram sinal de autoridade no Google.
- Já temos `database/lei214_anexos.json` (191KB) — fonte canônica internas. Subutilizada.
- **Ação:** componente `<FundamentacaoLegal />` reutilizável em posts.

---

## 4. Plano de ataque (sequência)

| # | Issue | Tipo | Estimativa | Prerequisite |
|---|---|---|---:|---|
| 1 | **fix(seo)**: server-render copy + headings em `/classificacao` e `/calculadora` | bug | S (1-2d) | — |
| 2 | **feat(blog)**: sistema MDX em `/blog/*` com Article + Breadcrumb + Person schema | feature | M (3-4d) | — |
| 3 | **content**: post pilar — cClassTrib 2026: mapeamento NCM × CBS/IBS | content | M (2-3d) | 2 |
| 4 | **content**: post pilar — Rejeição 1024: causas e como resolver | content | M (2-3d) | 2 |
| 5 | **content**: post pilar — Como classificar NCM corretamente em 2026 | content | M (2-3d) | 2 |
| 6 | **feat(seo)**: helpers de schema (Article/Breadcrumb/Person) + `<FundamentacaoLegal />` | feature | S (1d) | 2 |

Total: ~2-3 sprints para fechar o gap fundamental. ROI esperado: começar a aparecer no top 10 em 60-90 dias após indexação dos 3 posts pilares.
