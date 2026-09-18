# Fundações fiscais temporais, relacionais e probatórias — Ordem 07

## Escopo e compatibilidade

Esta entrega cria uma API interna de serviços (`app.services.fiscal_foundations`).
Não adiciona endpoints HTTP, interface de usuário, rotinas de ingestão, conectores,
tratamento tributário, cálculo, seleção de CST/cClassTrib ou dependência do motor
fiscal. Não contém política material do art. 271 nem fluxos do Portal.

O domínio anterior do Simples permanece na tabela `manifestacoes_eleicao_ibs_cbs`.
A migration 0044 adiciona somente sua identidade de política: regime
`SIMPLES_NACIONAL`, versão `SIMPLES_2026_V1`. Não copia registros, não cria partes
por dedução e não fabrica eventos `OPTION_DEFERRED` ou `OPTION_EFFECTIVE`.

A função pública `resolver_eleicao_ibs_cbs` mantém assinatura e retorno. Seu corpo
anterior fica preservado em `_resolver_simples_v1`, acessível pelo dispatcher
`resolve_policy`. Prazos, continuidade, cancelamento e evidência insuficiente
permanecem exatamente como antes. Esse comportamento é uma exceção explícita de
compatibilidade, não um mecanismo permitido para novos regimes. Não há alteração
nas APIs existentes ou nos documentos históricos.

## Modelo e políticas

- `fiscal_parties`: identidade PF/PJ local ao tenant, sem papéis customer/supplier.
  CPF e CNPJ são strings normalizadas; CNPJ admite letras. Validação é de formato,
  não comprova existência cadastral, natureza cooperativa ou associação.
- `fiscal_election_policies`: regime, versão, fonte e mecanismo imutáveis por tenant.
  Novas políticas só utilizam `EXPLICIT_EVENTS_V1`. Não há fallback para mecanismo
  desconhecido. Nenhuma política específica de cooperativa é pré-cadastrada.
- `fiscal_elections`: pedido interno, parte, política e exercício opcional. Seu UUID
  não representa protocolo do Portal. Exercício informado não prova exercício
  efetivo; documento pode ser vinculado com papel `FISCAL_YEAR`.
- `fiscal_facts`: eventos e afirmações versionados, com fonte e tipo de origem,
  data do evento, intervalo de validade e momento UTC de registro. Tipo de origem
  distingue documentação privada, registro oficial e artefato regulatório; não
  reutiliza a allowlist de hosts de `ArtifactProvenance` para documentos privados.
- `fiscal_fact_evidence`: documento confirmado, papel probatório e SHA-256 presos
  a uma revisão do fato. Um documento pode sustentar vários papéis. Isso não
  valida automaticamente a interpretação jurídica de seu conteúdo.

O serviço recebe uma sessão SQLAlchemy e `tenant_id` obrigatório. O chamador
controla commit/rollback e deve obter o tenant da autenticação, nunca de identidade
fiscal informada livremente. Todos os pais são consultados no tenant. FKs compostas
`(tenant_id, id)` protegem também escritas que contornem o serviço.

## Estados da eleição

`OPTION_REQUESTED`, `OPTION_DEFERRED` (deferido), `OPTION_EFFECTIVE` e
`OPTION_CANCELLED` são fatos diferentes com documentos próprios. Podem chegar fora
de ordem; o resolvedor ordena semanticamente pelas datas, não pela ingestão.

Para `EXPLICIT_EVENTS_V1`:

- Pedido sozinho continua solicitado, mesmo depois de anos.
- Deferimento documentado não cria fato de eficácia.
- Eficácia exige os três fatos documentados e cronologia coerente. Um fato explícito
  pode informar início futuro; a consulta só retorna eficaz dentro desse intervalo.
- Cancelamento documentado de pedido pendente retorna cancelado, sem eficácia.
  Deferimento/eficácia contraditórios, múltiplos eventos concorrentes ou datas
  desconhecidas retornam `INDETERMINATE`. Não há reabertura automática.
- Fora do período documentado não há renovação nem continuidade presumidas.
- Retroatividade que exija política própria permanece indeterminada neste mecanismo.

`event_at` e `cancelled_at` têm precisão de **dia** (`DATE`); não é fabricado horário
para datas documentais. `recorded_at` é timestamp UTC com fuso. A política genérica
não resolve uma disputa de ordem intradiária. Datas de validade são inclusivas em
ambas as pontas; fim nulo representa afirmação documentada sem fim informado, não
uma dedução a partir do cadastro atual.

## Associação e revisão histórica

`was_party_member_at(session, tenant_id=..., party_id=..., cooperative_id=...,
transaction_date=..., known_at=...)` retorna estado, motivo e IDs dos fatos usados.
`cooperative_id` é o papel na consulta, não qualificação de natureza jurídica.

Somente fatos `PROVEN_MEMBER`/`PROVEN_NOT_MEMBER` com relação `MEMBER_OF` participam.
Sem cobertura probatória, retorna `INDETERMINATE`. Afirmações positivas e negativas
simultâneas também retornam indeterminação. Uma data de admissão recebida isoladamente
não cria automaticamente relação; é necessário registrar a afirmação de associação.

A lista fiscal, sua atualização e a documentação societária são fatos distintos.
`TAX_ASSOCIATE_LIST` não satisfaz sozinho o papel probatório de criação da associação.
Nenhuma consulta produz elegibilidade de operação ou resultado tributário.

Uma retificação informa `supersedes_id`, conserva linhagem e incrementa revisão.
Não pode mudar tenant, partes ou pedido. Pode corrigir a afirmação de associação
entre positiva/negativa. A versão anterior e suas provas permanecem no banco.
Afirmações independentes conflitantes não são resolvidas pela regra "última vence".

`known_at` seleciona o conhecimento disponível naquele instante, independentemente
da data da operação. Primeiro são selecionadas as revisões; depois a validade.
Assim, corrigir um intervalo não ressuscita sua versão antiga fora do novo período.

Banco e serviço exigem documentos confirmados com conteúdo fixado e hash. Constraint
adiada exige prova tipada ao finalizar a transação; fato e vínculos são atômicos.
Depois do commit não se acrescenta prova retroativamente a uma revisão: registra-se
nova revisão com o conjunto completo de provas. Triggers bloqueiam UPDATE, DELETE
ou TRUNCATE nos registros da fundação.

## Preservação e impacto de storage

`documents.retention_class` distingue `STANDARD` e `FISCAL_EVIDENCE`.
`preserve_document` classifica explicitamente e registra motivo. Vincular um documento
a um fato também o preserva, em trigger no banco. Nenhum novo prazo jurídico é criado.

O job existente de 365 dias seleciona apenas `STANDARD`. Documentos probatórios,
inclusive versões supersedidas e fontes de afirmações conflitantes, permanecem.
Um trigger bloqueia exclusão, retirada da classificação e alteração de conteúdo
vinculado. A classificação e a vinculação adquirem lock no documento antes de
concluir; o expurgo usa `FOR UPDATE SKIP LOCKED`. Se a exclusão já ganhou o lock e
concluiu, a tentativa de vincular falha; não é admitida prova com documento ausente.

Sem política válida de descarte: **preservar**. Não existe endpoint ou método de
liberação nesta versão. A política atual de documentos comuns continua igual.

Impacto: crescimento de bytes preservados e número de revisões, sem teto de idade.
Acompanhar bytes e contagem por tenant/classe, inclusive objetos confirmados e
staging referenciados. Hash detecta alterações, mas não é autenticação jurídica.

O futuro lifecycle deverá ter política versionada, fundamento, escopo, aprovação,
verificação de todos os vínculos/revisões e bloqueios, autorização de descarte e
trilha auditável; somente então uma rotina específica poderá liberar/excluir prova.
Mudança de storage tier pode ser independente do descarte se preservar integridade
e acesso. Regras externas do bucket não podem expirar esses objetos: a proteção
implementada é da aplicação/banco, e esta entrega não altera lifecycle da nuvem.

## Migration, implantação e rollback

0044 depende de 0043, já presente na main. É aditiva: cinco tabelas, duas colunas
legadas de política e classificação/motivo de preservação em documentos. Documentos
anteriores recebem `STANDARD`; não há interpretação automática de referências
textuais antigas para deduzir quais arquivos são provas. Quando identificados,
devem ser classificados explicitamente antes de entrarem em uso probatório.

Aplicar migrations antes de subir esta versão do backend. Não houve execução em
produção nesta entrega. Até integrar a API interna a fluxos autorizados, não há
classificação automática de documentos antigos por conteúdo.

Downgrade/upgrade real é testado e preserva integralmente registros legados. Com
novas fundações vazias e sem documentos preservados, o schema volta a 0043. **Depois
de registrar dados novos ou preservar documentos, downgrade é recusado atomicamente**:
não se pode apagar histórico nem devolver provas ao expurgo antigo por rollback.
Nesse caso, usar rollback de aplicação compatível mantendo o schema ou preparar um
plano explícito de preservação antes de desfazer a estrutura. Nenhum dado é apagado
silenciosamente para fazer um downgrade passar.

## Verificação

Testes cobrem estados, limites, fatos fora de ordem, ausência/conflito, revisões,
conhecimento histórico, provas tipadas, isolamento no serviço e FKs, conteúdo
confirmado, imutabilidade, retenção e lock concorrente sobre documento já commitado.
Banco descartável separado verifica backfill, downgrade/upgrade e recusa de rollback
com dados. Regressão mantém os testes originais de domínio e endpoints do Simples.
