# Tribultz Weekly Snapshot

Retrato semanal do estado da empresa — **produto, infraestrutura, dados, saúde** —
como referência de regressão e linha do tempo operacional. Não é RFC, não é
feature: **é hábito.** Roda toda sexta.

## Uso

```bash
bash tools/operational-baseline/operational_baseline.sh
# → tools/operational-baseline/output/AAAA-MM-DD.md
```

Depois, **preencher à mão o bloco de reflexão** no fim do snapshot gerado.

## O ritual (toda sexta)

1. Rodar o gerador → `output/AAAA/AAAA-MM-DD.md` (**só fatos** — produto mede).
2. **Interpretar no Brain** (não aqui): criar `tribultz-brain` → `knowledge/discovery/weekly/AAAA-Wnn.md`
   com as 6 perguntas da Weekly Review (RFC-0023) — **Brain interpreta**.
3. `diff` contra o snapshot da sexta anterior → "o que mudou?".
4. Commitar o novo `output/AAAA/AAAA-MM-DD.md`.

> **Regra: produto mede, Brain interpreta.** O snapshot nunca contém análise —
> só fatos. Isso impede que o fato (imutável) e a interpretação (revisável) se
> contaminem. Ver RFC-0023 no `tribultz-brain`.

## O que ele mede

Ver [`baseline_config.yml`](baseline_config.yml). Cada métrica declara sua **fonte**:

- **repo** — medido sempre (grep/ls no checkout): regras, cClassTrib, routers, endpoints, páginas, migrations, TODO/FIXME, storage probe, known limitations.
- **gh** — GitHub CLI, se disponível: issues abertas / P2.
- **db** — banco (usuários, empresas, API keys, laudos, XML processados, migrations pendentes): hoje `n/d`; preenchido quando rodado em ambiente com DB (CI/VM). O **slot existe desde a semana 1** — o histórico importa mais que o número.
- **manual** — RFCs abertas (vivem no `tribultz-brain`).

## Princípio

Mede o que dá para medir; declara `n/d` o que não dá. Nunca afirma um estado sem
evidência — o mesmo princípio que a Tribultz aplica ao produto, aplicado a si mesma.
As "known limitations" (Early Adopter / Grant / Effective License / TERA) são
rastreadas por **ausência** (grep = 0); quando passarem de 0, a Fase 1 começou a existir.
