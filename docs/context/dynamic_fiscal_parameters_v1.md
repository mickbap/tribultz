# Parametros fiscais dinamicos — contrato v1

## Escopo

O registry `backend/app/data/fiscal_parameters.json` e a fonte canonica para
parametros numericos cuja aplicacao depende de valor publicado por autoridade
oficial. O arquivo nasce vazio: esta entrega cria a capability, nao cadastra
qualquer regra ou valor fiscal.

Atualizacoes passam por pull request, review e CI. O runtime apenas le o
snapshot aprovado; nao ha endpoint administrativo, inferencia por IA, coleta
automatica ou mutacao silenciosa.

## Modelo e versionamento

Cada identificador possui `fallback` e uma lista append-only de versoes. Cada
versao registra valor decimal literal, fonte e URL oficiais, ato de referencia,
vigencias inicial/final inclusivas, data da atualizacao com timezone, status da
fonte, versao do registro e fingerprints da fonte e do registro normalizado.

Historico nao e sobrescrito. Correcao de valor ou fonte cria nova versao e
fecha a vigencia anterior quando houver base documental para isso. Vigencias
sobrepostas sao conflito e bloqueiam a resolucao; o motor nao escolhe a versao
mais nova por conveniencia.

## Fail-closed

Na v1, a unica politica aceita e `BLOCK`. O resolvedor retorna:

- `DETERMINADO`: existe uma unica versao vigente com fonte
  `OFFICIAL_VALIDATED` e valor presente;
- `INDETERMINADO`: identificador ausente ou nenhuma versao aplicavel a data;
- `BLOQUEADO`: fonte nao validada/revogada/ausente ou conflito de vigencias.

Resultados indeterminados ou bloqueados nunca carregam valor utilizavel. Nao
ha fallback para ultima versao, versao futura, media, indice calculado ou
constante no codigo.

## Evidencia e integracao futura

Toda resolucao e serializavel e inclui data de referencia, instante da
resolucao, estado, motivo, fallback, versao selecionada e evidencia completa
das versoes consideradas. O consumidor futuro deve persistir esse snapshot no
audit trail de tenant ja existente junto do resultado da regra.

Esta entrega nao registra limite de receita de pessoa fisica, nao calcula IPCA
e nao inclui os valores 240000 ou 288000. Esses dados dependem de gate proprio.
