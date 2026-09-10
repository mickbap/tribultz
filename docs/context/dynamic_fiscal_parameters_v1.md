# Objetos regulatorios dinamicos — fundacao e contrato v1

## Decisao arquitetural

A fundacao comum nao sera um registro polimorfico que trate valor monetario,
XSD e mensagem de erro como se fossem o mesmo dado. Ela combina mecanismos ja
existentes no Core — snapshot versionado no Git, `ArtifactProvenance`, allowlist
de autoridades oficiais, fingerprint e resolucao temporal auditavel — e mantem
dois agregados tipados:

1. `FiscalParameterDefinition`: parametro escalar consumivel por uma regra;
2. `TechnicalArtifactDefinition`: manifesto de um pacote tecnico multipartes.

O primeiro agregado e implementado nesta entrega. O segundo tem o contrato
definido abaixo, mas nao e implementado nem populado nesta ordem. Assim o
engine nao passa a conhecer DeRE ou qualquer versao concreta, e o desenho nao
fecha a porta para a segunda classe de objeto.

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

## Contrato futuro para artefatos tecnicos versionados

O manifesto de um artefato tecnico deve representar, sem inferir datas ou
semantica:

- `artifact_id` e `version`;
- `status` factual do pacote;
- `effective_from` e `effective_to`, ambos anulaveis quando a fonte nao
  estabelecer vigencia inequivoca;
- `supersedes` e `superseded_by`, por referencia explicita e validavel;
- fonte/URL oficiais, ato de referencia, data de observacao e fingerprint do
  artefato bruto;
- componentes tipados e seus fingerprints normalizados;
- `rule_id` estavel para cada item comparavel, quando a propria fonte fornecer
  identidade ou quando a normalizacao puder preserva-la sem interpretacao;
- dependencias normativas ou tecnicas adicionais e o estado da sua verificacao.

Os tipos de componente previstos sao `XSD`, `TABLES`, `VALIDATION_RULES`,
`ERROR_MESSAGES`, `SERIES_EVENTS` e `NORMATIVE_DEPENDENCIES`. A lista descreve
partes independentes do pacote: publicar uma delas nao prova que as demais
existem, estao vigentes ou possuem semantica suficiente para uso no motor.

Uma resolucao futura recebera `artifact_id`, `rule_id` opcional e data de
referencia. Ela devolvera a versao e a evidencia aplicaveis, nunca uma versao
mais nova por conveniencia. Ausencia de vigencia oficial, sobreposicao,
cadeia de substituicao inconsistente ou fonte nao validada produzem estado
explicito e valor tecnico nao consumivel.

## Disponibilidade tecnica nao e semantica tributaria

O contrato separa dois resultados:

- disponibilidade tecnica: o artefato/componente existe, tem proveniencia e
  fingerprint validos;
- determinacao semantica: ha fontes suficientes para atribuir o comportamento
  que um consumidor pretende executar.

Quando um componente depender de fonte adicional ainda nao publicada, a
segunda resolucao deve ser exatamente `INDETERMINADO`, com motivo
`FONTE_ADICIONAL_NECESSARIA` e a dependencia ausente na evidencia. XSD,
tabelas, criticas ou mensagens de erro nao suprem silenciosamente um manual
operacional/normativo exigido.

## Diff entre versoes tecnicas

O manifesto futuro armazenara fingerprints por componente e, quando houver
itens normalizados, por `rule_id`. Isso permite calcular, sem interpretar
efeito fiscal:

- `DIFF_SCHEMA` sobre componentes `XSD`;
- `DIFF_TABELAS` sobre componentes `TABLES`;
- `DIFF_REGRAS_VALIDACAO` sobre componentes `VALIDATION_RULES`.

Cada diff classificara itens como adicionados, removidos, alterados ou
inalterados e mantera os fingerprints anterior/novo. Mudanca tecnica nao sera
convertida automaticamente em obrigacao, rejeicao, direito ou efeito fiscal.

## Compatibilidade com o baseline DeRE existente

O registro canonico atual em `regulatory_acts.json` ja preserva a identidade e
o artefato bruto da DeRE v1.2.0, o ato de aprovacao, os claims das series
iniciais D-2000, D-3000 e D-4000 e a dependencia pendente do MOU/MOD. Ele e
evidencia de que a fundacao de proveniencia e adequada, mas nao e ainda um
manifesto tecnico completo: faltam cadeia formal de versoes, componentes
tipados, fingerprints por regra e diff estruturado.

Este delta nao migra esse baseline, nao cria registry de artefatos tecnicos e
nao conecta a DeRE ao engine. Quando houver gate proprio, a migracao devera
preservar os fingerprints e arquivos brutos ja canonizados. Enquanto o MOU/MOD
atualizado permanecer pendente, qualquer semantica dependente dele continuara
`INDETERMINADO — FONTE_ADICIONAL_NECESSARIA`.

## Testes exigidos antes de implementar o tipo B

- versao futura nao e resolvida para competencia anterior;
- vigencia ausente nao e inventada;
- cadeia de substituicao inconsistente e sobreposicao bloqueiam;
- cada componente preserva fonte e fingerprint proprios;
- diff separa schema, tabelas e regras de validacao;
- componente alterado nao cria efeito fiscal automatico;
- dependencia normativa ausente retorna
  `INDETERMINADO/FONTE_ADICIONAL_NECESSARIA`;
- o engine resolve por identificador/data, sem importar versao concreta;
- o baseline DeRE v1.2.0 permanece byte a byte preservado durante eventual
  migracao futura.
