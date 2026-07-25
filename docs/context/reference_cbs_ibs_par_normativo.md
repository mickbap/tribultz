---
name: cbs-ibs-par-normativo
description: "Padrão metodológico: mudanças que afetam CBS e IBS conjuntamente tendem a vir em par de atos (Decreto federal + Resolução CGIBS) — checar sempre os dois lados"
metadata:
  node_type: memory
  type: reference
---

## O padrão

CBS (federal, Executivo) e IBS (estadual/municipal, CGIBS) são tributos
gêmeos criados pela mesma reforma (LC 214/2025 + LC 227/2026), mas com
autoridades regulatórias e instrumentos legais formalmente **distintos**:

- **CBS** é regulamentado por **Decreto** (competência do Executivo federal).
- **IBS** é regulamentado por **Resolução do CGIBS** (Comitê Gestor do IBS,
  colegiado estadual/municipal).

Quando uma mudança de prazo/regra afeta os dois tributos ao mesmo tempo (o
caso mais comum, já que a maioria das obrigações da reforma nasce desenhada
para os dois juntos), ela normalmente exige **dois atos separados**, um de
cada autoridade — mesmo que a mudança de fato seja uma só.

## Caso confirmado (2026-07-25, fonte primária lida via OCR)

- **Decreto nº 13.075/2026** (21/07/2026) — altera o Decreto nº 12.955/2026
  (regulamento da CBS, art. 239) — adia de 01/07/2026 para **01/01/2027** a
  obrigatoriedade de CNPJ + emissão de documento fiscal por CNPJ para pessoa
  física contribuinte/responsável tributário e produtor rural PF.
- **Resolução CGIBS nº 13/2026** (22/07/2026) — altera o art. 617 do
  Regulamento do IBS (Resolução CGIBS nº 6/2026) — **mesmo adiamento, mesma
  data**, referenciando os arts. 105 e 115 do Regulamento do IBS.

Motor da Tribultz (`PF_CONTRIB_CNPJ`, dual-stack) foi corrigido em #520/PR
#521 usando só a data — o comentário/citação legal no código só mencionava o
Decreto (lado CBS) até ser completado em #524/PR para citar os dois atos.

## Why

Uma checagem de vigência regulatória que monitora só Decretos federais (ou só
Resoluções CGIBS) fica estruturalmente incompleta pela metade para qualquer
mudança que toque tanto CBS quanto IBS — que é a maioria dos casos relevantes
pro motor da Tribultz, já que quase toda regra do produto valida os dois
tributos juntos (grupo `IBSCBS` unificado no XML).

## How to apply

Ao investigar qualquer mudança de prazo/vigência relacionada a CBS ou IBS
(nova data, novo adiamento, nova exceção):

1. Procurar pelo lado que já foi encontrado primeiro (ex. um Decreto).
2. **Sempre procurar também o lado espelhado** — se achou um Decreto,
   procurar a Resolução CGIBS correspondente (e vice-versa) antes de
   considerar a pesquisa de vigência completa.
3. Ao citar base legal em código/comentário/finding, citar **os dois atos**
   quando ambos existirem — não só o primeiro encontrado.

Registrado também em [RFC-0028](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/rfcs/RFC-0028-rtc-sync-engine.md)
§6 (Brain) como novo tipo de fonte a monitorar pelo futuro RTC Sync Engine —
"ato normativo que altera vigência/cronograma".
