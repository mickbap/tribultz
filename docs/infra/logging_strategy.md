# Estratégia de Logs e Observabilidade - Tribultz

## Captura e Filtragem de Logs do Docker
A lógica de captura será baseada em um coletor estruturado (ex: FluentBit ou Vector) agindo como sidecar ou daemonset no cluster Docker/Magalu Cloud. Esse agente fará a extração dos logs dos contêineres e aplicará regras de parsing.

## Diferenciação: Ruído Operacional vs. Erros Críticos de Negócio
- **Ruído Operacional (Nível DEBUG/INFO):** Trace de requisição, heartbeats de containers e acessos HTTP puros. Será amostrado (sampled) ou enviado para um storage mais barato (Cold Storage) caso não haja erro.
- **Erros Críticos de Negócio (Nível ERROR/CRITICAL):** Falhas em cálculos tributários, timeout de APIs Sefaz, ou falhas no handoff entre Agentes. Terão processamento síncrono, disparo de alertas (Webhook/Slack) e retenção prioritária.

## Estrutura JSON (Diagnósticos Preditivos para LLM)
Os logs serão estruturados em JSON no padrão ECS (Elastic Common Schema), com campos contextuais para a CrewAI e para o negócio:

```json
{
  "timestamp": "2026-03-27T10:00:00Z",
  "level": "ERROR",
  "service": "crewai-tax-calculator",
  "trace_id": "a1b2c3d4",
  "agent_id": "TaxSpecialist",
  "task_id": "calc_icms_st_sp",
  "event": {
    "type": "business_exception",
    "description": "Timeout na consulta da alíquota base."
  },
  "context": {
    "company_id": "9999",
    "state_origin": "SP",
    "state_dest": "RJ"
  },
  "llm_diagnostics": {
    "suggested_action": null,
    "confidence_score": 0.0
  }
}
```

Essa estrutura plana, enriquecida com `agent_id` e `task_id`, garante que Modelos de Linguagem (como LLMs de análise) possam ser platinados via _few-shot prompting_ para correlacionar logs e apresentar diagnósticos preditivos assertivos.
