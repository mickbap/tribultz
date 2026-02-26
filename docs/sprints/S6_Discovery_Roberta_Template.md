# Sprint 6 — Discovery com Roberta (Template)

Objetivo: consolidar Top 10 validações fiscais para NFS-e (prioridade) e NF-e (suporte), com severidade, evidência mínima (fonte) e UI esperada no Tribultz.

## Como preencher (Roberta)
- Para cada regra: descreva a condição, quando vira FATAL vs ALERTA, e qual evidência mínima é aceitável em auditoria.
- Sempre que possível, indique “onde está” no documento: nome do campo + xpath (ou caminho lógico) e um snippet.
- Para exemplos: enviar 3 casos anonimizados com “gabarito” (quais findings deveriam aparecer).

## 1) Top 10 validações (preencher)

Colunas:
- rule_id (slug)
- Documento (NFSE|NFE)
- Severidade (FATAL|ALERT)
- Campo / Onde está (campo + xpath/caminho + snippet)
- Regra (descrição objetiva)
- Evidência mínima (xml/link/print + o que precisa constar)
- UI esperada (mensagem curta + recomendação)

| # | rule_id | Doc | Sev | Campo / Onde está | Regra | Evidência mínima | UI esperada |
|---|---------|-----|-----|-------------------|-------|------------------|-------------|
| 1 |         |     |     |                   |       |                  |             |
| 2 |         |     |     |                   |       |                  |             |
| 3 |         |     |     |                   |       |                  |             |
| 4 |         |     |     |                   |       |                  |             |
| 5 |         |     |     |                   |       |                  |             |
| 6 |         |     |     |                   |       |                  |             |
| 7 |         |     |     |                   |       |                  |             |
| 8 |         |     |     |                   |       |                  |             |
| 9 |         |     |     |                   |       |                  |             |
| 10|         |     |     |                   |       |                  |             |

## 2) Paths/variações comuns (onde achar campos críticos)

Preencher com nomes e variações observadas em NFS-e (Portal Nacional e/ou provedores):

### CST
- Campo/Tag(s):
- XPath/caminho(s) comum(ns):
- Variações / exceções:

### cClassTrib (6 dígitos)
- Campo/Tag(s):
- XPath/caminho(s) comum(ns):
- Variações / exceções:

### Código de Serviço (6 dígitos)
- Campo/Tag(s):
- XPath/caminho(s) comum(ns):
- Variações / exceções:

### NCM (normalmente ALERTA)
- Quando ALERTA:
- Quando (se existir) vira FATAL:
- Evidência mínima preferida:

## 3) Exemplos anonimizados (3) + gabarito

Para cada exemplo, anexar/linkar o documento e descrever o gabarito (findings esperados).

### Exemplo A
- Fonte: (XML/link/print)
- Contexto:
- Gabarito (findings esperados):

### Exemplo B
- Fonte:
- Contexto:
- Gabarito:

### Exemplo C
- Fonte:
- Contexto:
- Gabarito:

## 4) Runbook rápido (time)
- Onde adicionar regra no código:
- Como garantir evidência (xpath/snippet):
- Como marcar severidade e recomendação:
- Como validar (fixture + teste):

## DoD (#20)
- Template versionado no repo
- Estrutura cobre: Top 10 + paths + exemplos + runbook
- Pronto para Roberta preencher sem precisar “inventar formato”
