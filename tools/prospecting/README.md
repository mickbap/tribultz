# Pipeline de Prospecção CNPJ — Fase 1

Ferramenta interna (PO-2026-07-SALES-001): transforma o dump bruto de Dados
Abertos do CNPJ (Receita Federal) em uma lista comercial priorizada de
escritórios contábeis para prospecção ativa. Sem CRM, sem disparo de e-mail —
esta entrega termina na geração da lista classificada (Top 2.000).

Não é um serviço de produto: são scripts standalone, executados manualmente
pelo operador, reaproveitando o `backend/.venv` (mesmo padrão de
`tools/architecture_audit.py` e `tools/qa_gates/run_gates.py`).

## Pré-requisito: baixar os arquivos oficiais

1. Baixe os arquivos em `https://arquivos.receitafederal.gov.br/` (Dados
   Abertos do CNPJ) — as tabelas **Empresas**, **Estabelecimentos**,
   **Simples** e **Sócios** vêm divididas em várias partes numeradas (ex.:
   `Estabelecimentos0.zip`..`Estabelecimentos9.zip`); baixe também
   **Municípios** (tabela de domínio, um único arquivo pequeno).
2. Extraia tudo em um único diretório, ex.: `~/dados-rf/2026-07/`. Os nomes
   dos arquivos extraídos devem começar com o nome da tabela (o parser
   localiza por `glob("Estabelecimentos*")` etc. — não precisa remover o
   sufixo numérico nem a extensão).
3. Layout oficial vigente:
   `gov.br/receitafederal/dados/cnpj-metadados.pdf` — os scripts abaixo já
   implementam esse layout; revalide-o se a Receita publicar um novo formato.

## Sequência de execução

```bash
cd backend && source .venv/bin/activate

# 1) Parser -> Normalização -> Consolidação -> upsert em prospect_orgs
python ../tools/prospecting/ingest_cnpj_dump.py \
    --dump-dir ~/dados-rf/2026-07 --dump-reference 2026-07

# 2) Dedup por domínio de e-mail nominal entre CNPJ básicos distintos
python ../tools/prospecting/dedup_prospects.py

# 3) Supressão -> Pré-score -> Top-N -> arquivo de saída
python ../tools/prospecting/score_and_select.py \
    --rubric-version v1 --dump-reference 2026-07 --top-n 2000 \
    --output ../reports/prospecting/top_2000_v1_2026-07.csv
```

Cada script tem `--help` com todas as opções. `--dry-run` está disponível em
`ingest_cnpj_dump.py` e `score_and_select.py` (roda tudo, mas não escreve no
banco/arquivo) — útil para conferir contagens antes de uma execução real.

## Idempotência

- `ingest_cnpj_dump.py`: `ON CONFLICT (cnpj_basico) DO UPDATE` — seguro
  reexecutar após uma falha ou com um dump mensal atualizado.
- `dedup_prospects.py`: reseta e recalcula os grupos do zero a cada execução.
- `score_and_select.py`: **não** é idempotente por design — cada execução real
  insere uma linha nova em `prospect_scoring_runs` (histórico append-only, é
  o que permite comparar rubricas diferentes no futuro). `pre_score`/
  `pre_score_tier` em `prospect_orgs` são um cache mutável (a "leitura atual"),
  sobrescritos a cada execução.

## Runtime esperado

Os arquivos da RF somam múltiplos GB (dezenas de milhões de linhas em
Estabelecimentos/Empresas/Sócios). `ingest_cnpj_dump.py` faz no máximo 4-5
passadas completas em streaming (nunca carrega um arquivo inteiro em
memória) — espere minutos, não segundos, na primeira execução contra o dump
completo. `dedup_prospects.py` e `score_and_select.py` operam só sobre os
~80 mil registros já consolidados em `prospect_orgs`, muito mais rápidos.

## Fora desta entrega (Fase 1 termina no Top 2.000)

Agente de enriquecimento externo, reclassificação, exportação para o CRM
comercial (**Excel, mantido pelo Economista** — o Attio foi descomissionado em
29/08/2026, ROUND 18-A; a fase seguinte NÃO exporta
para o HubSpot, que fica isolado no pós-venda), telemetria e scripts de
feedback loop são fases seguintes — ver o plano da Fase 1 para o desenho
completo.

Este pipeline é **outra origem de aquisição** dentro da arquitetura
comercial (Receita Federal → Pipeline Prospecting → Excel), não um CRM
paralelo — decisão de Produto/Vendas, 07/08/2026.
