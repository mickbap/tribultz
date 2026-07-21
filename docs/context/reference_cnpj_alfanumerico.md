---
name: cnpj-alfanumerico-receita-federal
description: "CNPJ alfanumérico (Receita Federal) — cronograma oficial e gap conhecido no validador de CNPJ da Tribultz"
metadata:
  node_type: memory
  type: reference
---

## Cronograma oficial (confirmado em fonte primária gov.br, verificado 21/07/2026)

- **27/07/2026, 7h** — entrada em produção dos sistemas da Receita Federal para o novo modelo.
- **31/07/2026** — emissão do primeiro CNPJ alfanumérico.
- Fonte: [Receita Federal — "Implantação do CNPJ Alfanumérico ocorrerá a partir de 31 de julho"](https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/julho/implantacao-do-cnpj-alfanumerico-ocorrera-a-partir-de-31-de-julho)
- Nota técnica de origem: Nota Técnica Conjunta CNPJ Alfanumérico (NFe Fazenda, NT 2025.001) — distinta da NT 2026.004 (layout NF-e/NFC-e que dá suporte ao campo `CNPJ` alfanumérico no XML; não confundir as duas ao pesquisar).

## Formato

14 caracteres, mantendo o tamanho atual:
- Posições 1–8: raiz — alfanumérica (letras + números)
- Posições 9–12: ordem do estabelecimento — alfanumérica
- Posições 13–14: dígitos verificadores — **permanecem numéricos**

## Escopo do impacto

- **Só afeta inscrições novas a partir de 31/07/2026.** Empresas já cadastradas mantêm o CNPJ atual (100% numérico), sem qualquer ação necessária.
- Adoção real por clientes da Tribultz é gradual — uma empresa precisa se registrar sob o novo formato, começar a operar/emitir documento fiscal, e então chegar a ser cliente/onboarding — não é um risco de "hoje", mas a janela já abriu (10 dias a partir de 21/07/2026).

## Gap conhecido no motor Tribultz (verificado 21/07/2026, ainda sem Issue própria até este registro)

Três pontos assumem CNPJ como exatamente 14 dígitos **numéricos** — vão rejeitar incorretamente um CNPJ alfanumérico legítimo:

| Local | Comportamento hoje | Efeito com CNPJ alfanumérico |
|---|---|---|
| `backend/app/schemas/auth.py:102-110` (`RegisterRequest.validate_cnpj`) | `re.sub(r"\D","",v)` + `len(digits) != 14` → `ValueError` | **Bloqueia o cadastro** de uma empresa nova na Tribultz (422 na API) |
| `backend/app/services/cnpj_validator.py:69-83` (`validate_cnpj`) | mesma checagem de 14 dígitos numéricos | Consulta a BrasilAPI/ReceitaWS nunca chega a ser feita — retorna erro "CNPJ deve ter 14 dígitos" |
| `backend/app/routers/auth.py:59-62` (`_cnpj_to_slug`) | `re.sub(r"\D","",cnpj)` — descarta letras ao montar o slug do tenant | Colisão silenciosa de slug entre CNPJs alfanuméricos diferentes que compartilhem os mesmos dígitos |
| `backend/app/routers/validate_xml.py:2079` (`_enrich_cnpj`) | `re.match(r"^\d{14}$", ...)` → `return None` se não bater | Degradação silenciosa (não é FATAL) — só para de enriquecer com status da Receita, não bloqueia a validação do XML em si |

O primeiro (schemas/auth.py) é o mais sério: bloqueia onboarding real de uma empresa nova, não é só degradação de uma feature secundária.

## Ação recomendada

Não implementado ainda — segue a governança Product First do CLAUDE.md (requisito legal/regulatório entra na matriz de priorização via Issue, não como iniciativa espontânea). Ver [#514](https://github.com/mickbap/tribultz/issues/514).
