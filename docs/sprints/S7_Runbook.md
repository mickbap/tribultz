# S7 Runbook — Motor de Validação Fiscal NFS-e

> Versão 1.0 — 21/03/2026
> Milestone: S7 (Rules Pack Discovery)
> Issues: #33 (Runbook + QA), #13 (Discovery Top 10)

---

## 1. Visão Geral

O motor de validação Tribultz aplica regras fiscais determinísticas sobre documentos NFS-e (XML), gerando **findings** com severidade, evidência e recomendação. A implementação é **dual-stack**: frontend (TypeScript, modo offline) e backend (Python/CrewAI, modo API).

### Arquitetura

```
┌──────────────────────────────────────────────────┐
│  Frontend (Next.js)                              │
│  xmlRules.ts → ValidationResultV11               │
│  Mock Mode: validação local, sem API             │
├──────────────────────────────────────────────────┤
│  Backend (FastAPI + CrewAI)                      │
│  ParseNFSeXMLTool → ValidateFiscalRulesTool      │
│  API Mode: parse S3 + validação + AI analysis    │
└──────────────────────────────────────────────────┘
```

### Contrato de saída (Finding)

Cada finding segue o formato **Evidence v1.1**:

| Campo | Tipo | Obrigatório | Exemplo |
|-------|------|-------------|---------|
| `rule_id` | string | sim | `CST_3_DIGITS` |
| `severity` | `FATAL` \| `ALERT` | sim | `FATAL` |
| `field` | string | sim | `CST` |
| `xpath` | string | sim | `/NFS-e/infNfse//CST` |
| `snippet` | string | sim | `<CST>12</CST>` |
| `recommendation` | string | sim | `"CST deve ter 3 dígitos…"` |

---

## 2. Top 10 Regras (baseline S7)

| # | rule_id | Sev | Campo | Regra | Base Legal |
|---|---------|-----|-------|-------|-----------|
| 1 | `CST_3_DIGITS` | FATAL | CST | Exatamente 3 dígitos | LC 214 |
| 2 | `CCLASSTRIB_6_DIGITS` | FATAL | cClassTrib | Exatamente 6 dígitos | LC 214 |
| 3 | `SERVICE_CODE_6_DIGITS` | FATAL | CodigoServico | Exatamente 6 dígitos | LC 214 |
| 4 | `XML_PARSE` | FATAL | documento | XML bem-formado | — |
| 5 | `NCM_PLACEHOLDER` | ALERT | NCM | Revisar classificação | LC 214 |
| 6 | `IBSCBS_MISSING` | FATAL | IBS/CBS | 4 tags obrigatórias | LC 214 + LC 227 |
| 7 | `IBSCBS_CALC` | FATAL | ValorCBS/IBS | Base × Alíquota (±R$0,01) | LC 227 |
| 8 | `CEST_MISSING` | FATAL | CEST | Presença obrigatória | LC 227 |
| 9 | `CEST_FORMAT` | FATAL | CEST | Exatamente 7 dígitos | LC 227 |
| 10 | `LAYOUT_PORTAL` | FATAL | Estrutura | Tags Portal Nacional | LC 214 |

**Alíquotas de referência (período de teste):** CBS 0,10% · IBS 0,90%

---

## 3. Variações de Tag (provedores)

O motor é **namespace-agnostic**. Namespaces XML são removidos antes da extração.

| Campo | Tags aceitas |
|-------|-------------|
| CST | `CST`, `cst`, `CodigoSituacaoTributaria` |
| cClassTrib | `cClassTrib`, `ClassTrib`, `CodigoClassificacaoTributaria` |
| CodigoServico | `CodigoServico`, `CodigoServicoPrestado`, `ItemListaServico`, `cServ`, `codigoServico` |
| NCM | `NCM`, `ncm`, `CodigoNCM` |
| CEST | `CEST`, `cest`, `CodigoCEST` |
| BaseCalculo | `BaseCalculo`, `baseCalculo`, `ValorBaseCalculo`, `BaseICMS` |
| AliquotaCBS | `AliquotaCBS`, `aliquotaCbs`, `AliqCBS` |
| ValorCBS | `ValorCBS`, `valorCbs`, `ValorContribuicaoBensServicos` |
| AliquotaIBS | `AliquotaIBS`, `aliquotaIbs`, `AliqIBS` |
| ValorIBS | `ValorIBS`, `valorIbs`, `ValorImpostoBensServicos` |

**Frontend:** regex strip `xml.replace(/<(\/?)\w+[\w.-]*:/g, "<$1")`
**Backend:** split `tag.split("}")[-1]`

---

## 4. Como Adicionar uma Nova Regra

### Passo 1 — Definir a regra

Antes de codificar, documentar:
- `rule_id` (SCREAMING_SNAKE_CASE, ex: `ALIQUOTA_RANGE`)
- Severidade: `FATAL` (bloqueio) ou `ALERT` (informativo)
- Campo alvo e XPath
- Condição de disparo (objetiva, sem ambiguidade)
- Recommendation (texto para o usuário)
- Base legal (LC 214, LC 227, ou normativo)

### Passo 2 — Frontend (xmlRules.ts)

```typescript
// 1. Extrair o campo (usar firstTag com variações conhecidas)
const meuCampo = firstTag(xmlNorm, ["TagPrincipal", "TagVariante"]);

// 2. Aplicar a regra
if (meuCampo && !/^\d{3}$/.test(meuCampo.value)) {
  findings.push({
    rule_id: "MINHA_REGRA",
    title: "Título descritivo",
    severity: "FATAL" as FindingSeverity,
    where: {
      field: "MeuCampo",
      xpath: `/NFS-e/infNfse//${meuCampo.tag}`,
      snippet: meuCampo.snippet,
    },
    recommendation: "Texto da recomendação.",
  });
}
```

### Passo 3 — Backend (validate_fiscal_rules_tool.py)

```python
# 1. Extrair campo no parse_nfse_xml_tool.py (adicionar tag ao elif chain)
elif tag in ("TagPrincipal", "TagVariante") and not fields["meu_campo"]:
    fields["meu_campo"] = text

# 2. Aplicar regra no validate_fiscal_rules_tool.py
meu_campo = (fields.get("meu_campo") or "").strip()
if not re.fullmatch(r"\d{3}", meu_campo):
    findings.append({
        "rule_id": "MINHA_REGRA",
        "severity": "FATAL",
        "field": "MeuCampo",
        "xpath": "/NFS-e/infNfse//MeuCampo",
        "snippet": f"<MeuCampo>{meu_campo}</MeuCampo>" if meu_campo else "(não encontrado)",
        "recommendation": "Texto da recomendação.",
    })
```

### Passo 4 — Testes

**Frontend** (`xmlRules.test.ts`):
```typescript
it("MINHA_REGRA fires when campo invalid", () => {
  const xml = `<?xml version="1.0"?><NFS-e>...<MeuCampo>XX</MeuCampo>...</NFS-e>`;
  const result = validateXmlRules({ tenantId: "t", documentType: "NFSE", xml });
  const f = result.findings.find(f => f.rule_id === "MINHA_REGRA");
  expect(f).toBeDefined();
  expect(f!.severity).toBe("FATAL");
  expect(f!.where.snippet).toContain("XX");
});
```

**Backend** (`test_nfse_tools.py`):
```python
def test_minha_regra_is_fatal(self):
    result = json.loads(self._tool()._run("inv-1", self._fields_json(meu_campo="XX")))
    rule_ids = [f["rule_id"] for f in result["findings"]]
    assert "MINHA_REGRA" in rule_ids
```

### Passo 5 — Gates (DoD)

Rodar **antes de abrir PR**:

```bash
# Frontend
cd frontend && npm test --silent && npm run build

# Backend
cd backend && python -m pytest tests/tools/ -q
```

---

## 5. Critérios de Aceite QA (Checklist)

Para cada regra nova ou modificada, verificar **todos** os itens:

### Funcional
- [ ] Regra dispara no cenário correto (fixture XML com erro)
- [ ] Regra **não** dispara no cenário correto (fixture XML válido)
- [ ] `rule_id` é único e segue padrão SCREAMING_SNAKE_CASE
- [ ] `severity` é FATAL ou ALERT (nunca outro valor)
- [ ] `recommendation` é acionável (diz o que corrigir)

### Evidência
- [ ] `xpath` aponta para o campo correto no XML
- [ ] `snippet` contém o trecho relevante do XML
- [ ] Finding inclui todos os campos obrigatórios (rule_id, severity, field, xpath, snippet, recommendation)

### Paridade frontend/backend
- [ ] Mesma regra implementada em `xmlRules.ts` e `validate_fiscal_rules_tool.py`
- [ ] Mesmas variações de tag em ambos os motores
- [ ] Mesma severidade e condição de disparo

### Testes
- [ ] Teste unitário frontend: regra dispara (FAIL case)
- [ ] Teste unitário frontend: regra não dispara (PASS case)
- [ ] Teste unitário backend: regra dispara (FAIL case)
- [ ] Teste unitário backend: regra não dispara (PASS case)
- [ ] Gates passando: `npm test` + `npm run build` + `pytest`

### Variações de provedor
- [ ] Tag variations documentadas na tabela (seção 3)
- [ ] Fixture com namespace testada (se aplicável)

---

## 6. Exemplos de Referência

| Exemplo | Arquivo | Cenário | Resultado |
|---------|---------|---------|-----------|
| A | `docs/sprints/discovery/examples/example_a.xml` | 3 FATAL: IBS/CBS ausentes, ClassTrib 4 dígitos, CEST ausente | **FAIL** |
| B | `docs/sprints/discovery/examples/example_b.xml` | 3 FATAL: CBS errado, IBS errado, CEST 5 dígitos | **FAIL** |
| C | `docs/sprints/discovery/examples/example_c.xml` | Tudo correto | **PASS** |

Gabarito detalhado: `docs/sprints/discovery/examples/S6_Discovery_Examples.md`

---

## 7. Vocabulário Fiscal

| Termo | Significado |
|-------|------------|
| CBS | Contribuição sobre Bens e Serviços (federal, 0,10%) |
| IBS | Imposto sobre Bens e Serviços (estadual/municipal, 0,90%) |
| CEST | Código Especificador da Substituição Tributária |
| ClassTrib | Classificação Tributária do serviço |
| CST | Código de Situação Tributária |
| NCM | Nomenclatura Comum do Mercosul |
| NFS-e | Nota Fiscal de Serviços eletrônica |
| LC 214 | Lei Complementar 214 (reforma tributária geral) |
| LC 227 | Lei Complementar 227 (13/jan/2026, atualizações) |

---

## 8. Arquivos-Chave

| Camada | Arquivo | Função |
|--------|---------|--------|
| Frontend engine | `frontend/src/lib/validation/xmlRules.ts` | Motor de validação (10 regras) |
| Frontend tests | `frontend/src/lib/validation/xmlRules.test.ts` | 24 testes unitários |
| Frontend fixtures | `frontend/src/lib/validation/fixtures/*.xml` | 4 fixtures XML |
| Backend parser | `backend/app/crews/tools/parse_nfse_xml_tool.py` | Extração XML → campos |
| Backend validator | `backend/app/crews/tools/validate_fiscal_rules_tool.py` | 10 regras fiscais |
| Backend tests | `backend/tests/tools/test_nfse_tools.py` | 21 testes unitários |
| Discovery | `docs/sprints/discovery/S6_Discovery_Consolidated.md` | Top 10 + paths + runbook base |
| Exemplos | `docs/sprints/discovery/examples/` | 3 XMLs + gabarito |
