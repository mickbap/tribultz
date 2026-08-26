# Contrato de evidência: vínculo execução ↔ versão regulatória

**Status: PROPOSTA v2 — revisada conforme parecer jurídico de 26/08/2026.**
Nada implementado. Não toca `Job`, `Report`, schema nem payload fiscal.
Não é entrada no Brain: vai ao gate dos pares antes de qualquer canonização.

Origem: Parte B do contraditório de 25/08/2026 sobre a #673.
Revisão v2: Ordem 11 de 26/08/2026.

## O fato apurado

**Hoje não é possível vincular uma execução concreta do motor à versão
regulatória que ela usou.**

Evidência no código, em `origin/main`:

| Onde | O que se verificou |
|---|---|
| `app/data/classtrib_table.py` | `CLASSTRIB_SYNCED_AT` e `CLASSTRIB_CONTENT_SIGNATURE` existem |
| consumidores | **apenas** `app/services/regulatory_freshness.py` |
| `app/routers/validate_xml.py` | usa `classtrib_cst`, `classtrib_expected_zero` etc., mas **não carimba versão** no resultado |
| `app/models/reports.py` | tem `report_hash` — hash do **arquivo**, não da regra |
| `app/models/jobs.py` | `result` é JSONB livre; **não carrega versão** |

Consequência: um laudo emitido hoje **não é reproduzível**. Não há como provar
contra qual tabela ele foi avaliado, nem redecidir o caso com a regra vigente à
época. A #673 tornou o frescor observável **no presente**; não criou memória.

## Contrato mínimo (v2)

Dez campos, registrados **no momento da execução**. Sem reconstrução posterior —
evidência reconstruída não é evidência.

| Campo | O que prova |
|---|---|
| `execution_id` | identidade da execução: sem isso nada mais é referenciável |
| `executed_at` | quando o motor rodou |
| `engine_version` | qual código decidiu — regra e motor versionam separado |
| `regulatory_version_id` | qual versão da tabela oficial foi usada |
| `artifact_fingerprint` | o **conteúdo** do artefato regulatório, não o rótulo: duas tabelas com a mesma data e conteúdo diferente deixam de ser confundíveis |
| `source_id` | **qual fonte** — hoje só SVRS; amanhã pode não ser |
| `source_observed_at` | quando a fonte foi observada, distinto de quando publicou |
| `source_snapshot_fingerprint` | o que a fonte respondeu naquela observação, separado do que estava embarcado |
| `comparison_method_version` | versão de `normalize()` + `data_signature()`; assinatura só é comparável sob o mesmo método |
| `result_fingerprint` | o resultado produzido — fecha a cadeia: entrada, regra, método e saída |

### `effective_at` — **removido na v2**

Estava na v1 como "vigência aplicada na decisão". Retirado por orientação
jurídica. Registro do motivo técnico para não voltar por inércia: um único
`effective_at` por execução é **falso** quando regras de vigências diferentes
decidem itens diferentes do mesmo documento. O campo aparentava precisão que o
domínio não sustenta. Vigência é atributo **da regra aplicada**, não da execução
— e portanto pertence ao nível do achado, se algum dia for necessário.

### `artifact_fingerprint` × `source_snapshot_fingerprint`

Não são redundantes e **não podem ser colapsados**:

- `artifact_fingerprint` — o que o motor **usou** (tabela embarcada na imagem)
- `source_snapshot_fingerprint` — o que a fonte **respondia** naquele instante

Quando divergem, a execução rodou com artefato desatualizado — e isso fica
provado, não inferido. Colapsar os dois recria exatamente a confusão que a #673
desfez entre "versão embarcada" e "estado da fonte".

## Histórico do artefato — série separada

O ciclo de vida do artefato regulatório **não pertence ao registro de execução**:

| Campo | O que descreve |
|---|---|
| `artifact_activated_at` | quando aquele artefato passou a valer no motor |
| `artifact_deactivated_at` | quando deixou de valer (nulo enquanto vigente) |

Série própria, chaveada por `artifact_fingerprint`. A execução aponta para o
artefato; não copia a janela. Assim, uma correção na janela histórica não
reescreve nenhuma execução já registrada.

## Invariantes

1. **Carimbo no ato.** Os dez campos são gravados na mesma transação do
   resultado. Nunca preenchidos depois, nunca inferidos do estado atual.
2. **Ausência é explícita.** Execução sem carimbo é execução **sem evidência
   regulatória** — não se assume a versão corrente. Mesmo princípio do
   `sync_execution="unobservable"` da #673.
3. **Persistência append-only lógica.** Registro de evidência **não é
   atualizado nem removido**. Correção entra como novo registro que referencia o
   anterior; a série do artefato é encerrada por `artifact_deactivated_at`, não
   por `UPDATE` destrutivo. **O schema não está decidido** — se isso vira coluna,
   tabela, tabela particionada ou log, é decisão do desenho, não desta proposta.
   O que está decidido é a **propriedade**: o passado não muda.
4. **`artifact_fingerprint` sai de graça.** Já é calculado no boot
   (`CLASSTRIB_CONTENT_SIGNATURE`). O custo desta proposta está na persistência e
   no contrato, não no cálculo.

## Perguntas que permanecem abertas

1. **Granularidade.** O carimbo pertence ao `Job`, ao `Report`, ou a ambos? Um
   job pode gerar N relatórios; um relatório pode consolidar N documentos.
   `execution_id` resolve a referência, não a granularidade.
2. **Retenção.** Por quanto tempo a evidência precisa sobreviver? Decide entre
   as formas de persistência que a invariante 3 admite.
3. **Laudo já emitido.** Relatórios anteriores ficam declaradamente sem
   evidência, ou marcados como "versão desconhecida"? **Recomendação técnica:
   declarar ausência.** Atribuir retroativamente uma versão que ninguém observou
   seria fabricar prova — e violaria a invariante 1.
4. **Exposição ao cliente.** O carimbo aparece no laudo entregue ou é interno de
   auditoria? Tem efeito sobre a #673, que acabou de **remover** conteúdo
   regulatório do endpoint público.
5. **`engine_version`.** De onde sai: tag de release, SHA do commit, ou versão
   declarada? Precisa ser estável e verificável depois — SHA é reproduzível, tag
   é legível.

## Relação com outras frentes

- **#673** — entregou observabilidade do frescor **no presente**. Esta proposta é
  sobre **memória**, eixo distinto.
- **#674** — heartbeat do coletor. Fornece `source_observed_at` e
  `source_snapshot_fingerprint` de forma confiável; sem ele, ambos dependem da
  probe sob demanda.
- **#672** — permanece P3, Fase 2 não autorizada. Sem relação de dependência.

## O que esta proposta NÃO faz

Não altera regra fiscal, classificação cClassTrib, schema, `Job`, `Report` ou
payload fiscal. Não cria migration. Não define formato de laudo. Não decide
persistência.
