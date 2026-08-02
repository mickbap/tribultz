# Query Pack — Cockpit de Unit Economics (v1)

Ferramenta interna (ORD-QA-002 / ORD-DADOS-001): extrai as métricas de
unit economics (MRR, churn, retenção, ativação, consumo) direto do
Postgres de produção, sem instrumentação nova — todo dado já existe nas
tabelas do produto.

Scripts standalone, execução manual, mesmo padrão de
`tools/prospecting/` e `tools/architecture_audit.py`.

## Uso

```bash
bash tools/metrics/run_extract.sh
```

Conecta via SSH na VM de produção (nunca expõe a porta do banco
localmente), roda as 5 queries lá e traz o CSV de volta pra
`reports/metrics/<ano-mes>/` — **gitignored**, dado de produção nunca
entra no git. Os arquivos `.sql` deste diretório são a única coisa
versionada.

Pré-requisito: chave SSH autorizada na VM (ver
`docs/infra/secrets_inventory.md`).

## Queries

| Arquivo | Métrica | Observação |
|---|---|---|
| `q1_mrr.sql` | MRR real por plano | Exclui tenants com Early Grant ativo (Founding Partners) — sem isso, MRR conta como receita algo que não é cobrado |
| `q2_churn.sql` | Cancelamentos por mês | Aproximação — sem histórico de status, é tendência, não taxa exata por coorte |
| `q3_retencao.sql` | Retenção por coorte de criação | **Não é conversão trial→pago** — `subscriptions.status` não tem histórico de transição; conversão real vem do funil comercial (Rumy), o banco só mostra o status atual |
| `q4_ativacao.sql` | Dias até a 1ª validação bem-sucedida | Usa `jobs.job_type='validate_xml'` + `status='SUCCESS'` |
| `q5_consumo.sql` | Uso do plano por período | Proxy de engajamento no v1; detalhe por rota/feature fica pra v2 |

## Fora desta entrega (v1 termina nessas 5 queries)

- Créditos fiscais de Split Payment (`documents.fiscal_metadata`) — métrica
  de valor entregue, distinta de unit economics de billing. v2.
- Uso por rota/feature individual — v2, pela matriz de priorização.
- CAC e funil comercial — vêm do extrato de Vendas (Attio), não do banco.
