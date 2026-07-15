---
name: nt-2025-002-apis-externas-cbs-ibs
description: "Referências técnicas da reforma tributária — NT 2025.002-RTC, Calculadora Oficial (sandbox público), ClassTrib SVRS, homologação NF-e"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 86fbe835-d1ef-4d60-8194-eca70a214920
---

## NT 2025.002-RTC (atual: v1.40 — 20/05/2026; v1.50 emergente p/ monofásico combustíveis)
- Download: https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=AklZnck3o6I%3D
- Define grupo IBSCBS em det/imposto para NF-e/NFC-e
- CSTs: 000, 001, 002, 070, 200, 410, 510, 515, 550, 620, 800, 810, 811, 830
- Alíquotas teste 2026 (simbólicas): CBS 0.90%, IBS 0.10% (IBS estadual 0,10% / municipal 0%)
- Alíquotas de REFERÊNCIA definitivas (Fazenda 2024): CBS 8,8% + IBS 17,7% = ~26,5% (é o que o código usa em uf_rates.py)
- ⚠️ CLAUDE.md do projeto lista alíquotas referência INVERTIDAS (CBS 0,10% / IBS 0,90%) — doc bug; código está correto

### Progressão de versões e prazos (verificado 13/06/2026)
- v1.36 (30/04/2026, Ajuste SINIEF 49/2025) ← versão referenciada no código Tribultz
- v1.40 (20/05/2026): novos campos/grupos/regras; Evento 211110 alterado, 211120 (destinação consumo pessoal) ELIMINADO; novas rejeições (1106, 960); DFeReferenciado obrigatório p/ devolução por item a partir de 01/09/2026
- v1.50 (emergente): reformulação layout monofásico de combustíveis; homologação até 01/09/2026, produção 03/11/2026
- **Prazos obrigatoriedade (Regime Normal CRT=3): homologação 01/07/2026, produção 03/08/2026. Simples/MEI: 04/01/2027**
- Regulamentos IBS e CBS publicados 30/04/2026 (MF + CGIBS); Split Payment — Ato Conjunto RFB/CGIBS nº 02 de 27/05/2026, doc técnico no DOU 03/06/2026, mecanismo só em 2027 (B2B voluntário)
- Guia FlexDocs: https://flexdocs.net/guiaNFe/gerarNFe.detalhe.imp.IBSCBS.html
- Guia TecnoSpeed: https://blog.tecnospeed.com.br/nota-tecnica-reforma-tributaria-nfe-nfce/

## Calculadora Oficial CBS/IBS (Receita Federal) — Validado 24/03/2026
- Portal home: https://piloto-cbs.tributos.gov.br
- Calculadora: https://piloto-cbs.tributos.gov.br/servico/calculadora-consumo/calculadora

### Módulos do portal (6 total)
| Módulo | URL | Acesso |
|--------|-----|--------|
| Calcular Tributos sobre Consumo | /servico/calculadora-consumo/calculadora | **ABERTO** (sem login) |
| Simular Operações de Consumo | - | Bloqueado (login gov.br) |
| Minhas Apurações Assistidas CBS (PR) | - | Bloqueado (login gov.br) |
| Consultar Ressarcimentos CBS (PR) | - | Bloqueado (login gov.br) |
| Consultar Transferências CBS (PR) | - | Bloqueado (login gov.br) |
| **Gerar Credencial para API (PR)** | - | **Bloqueado** (login gov.br) — investigar para 6tech/Tribultz |

### Calculadora — 4 modos
1. **Regime Geral** (`/calculadora/regime-geral`)
   - Operação de Consumo: Data Fato Gerador (art.10 LC 214/25), Bem/Serviço, UF+Município, NCM+Descrição
   - Tributação: CST (dropdown), cClassTrib (dropdown), Valor Base de Cálculo, Quantidade, Unidade de Medida
   - Botões: Importar, Exportar, URL, QR Code, PDF, **XML**
2. **Pedágio** (`/calculadora/pedagio`)
   - Ocorrência (data), Valor da Operação (sem tributos), Tributação, Trechos (UF+Município+Extensão km)
3. **Split Payment Simplificado** (`/calculadora/simplificado`)
   - Data da Operação, CPF/CNPJ, Valor Pago
4. **Bases de Cálculo** (`/calculadora/bases-de-calculo`)
   - Modelos: CBS e IBS para Bens, IS para Bens - Ad valorem, NFS-e
   - Ano do Fato Gerador: 2026
   - Valores que integram a base: Valor do Bem, Ajustes, Juros, Multas, Encargos, Frete, Imposto Seletivo, Outros tributos, Demais importâncias
   - Valores que NÃO integram: ICMS, ISS, PIS, Cofins, PIS Importação, COFINS Importação, COSIP, IPI, Desconto Incondicional

### Outputs da Calculadora
- CBS (federal), IBS estadual, IBS municipal, IS (seletivo)
- Memória de cálculo com base legal
- **Gerador de XML** — trecho XML com tags IBSCBS para NF-e
- Relatório PDF, QR Code, URL compartilhável

### Próximos passos — API
- "Gerar Credencial para API (PR)" está bloqueado — requer login gov.br
- Investigar: como 6tech/Tribultz pode obter credencial para integração via API
- Possível fluxo: login gov.br empresarial → gerar credencial → chamar API programaticamente
- **Apuração Assistida (sandbox)**: Simula não cumulatividade — compra (crédito RAD), venda (débito), compensação

## Conformidade Fácil (ClassTrib)
- Endpoint: https://cff.svrs.rs.gov.br/api/v1/consultas/classTrib

## Homologação NF-e
- SVAN: https://hom.nfe.fazenda.gov.br
- NFS-e Nacional: IE 999999 (homologação), IE 530000 (produção)

## Dados de mercado (março 2026)
- 61.880 documentos fiscais de teste emitidos
- 153 empresas (CNPJs) testando
- 21 software houses integradas
- PlugNotas: integrou calculadora oficial diretamente na emissão
