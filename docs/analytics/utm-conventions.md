# Convenção de UTMs — Tribultz

Padrão obrigatório de marcação de links que trazem tráfego **para** o site
(`tribultz.com.br`). Sem UTM, o GA4 classifica a sessão como **`Unassigned`**
(hoje 100% do tráfego cai aí) e perdemos a atribuição por canal — base para medir
ROI de aquisição.

> Eventos do funil (`generate_lead`, `sign_up`, `begin_checkout`, `purchase`)
> medem **o que** o usuário faz. As UTMs medem **de onde** ele veio. As duas
> coisas juntas = CAC e ROI por canal.

## Onde aplicar

UTM vai na **URL de destino no nosso site** — não no `wa.me`. Ex.: a mensagem de
WhatsApp / bio / e-mail contém um link `https://tribultz.com.br/...?utm_...`.

| Canal | Aplicar UTM em |
|-------|----------------|
| WhatsApp (broadcast, bio, assinatura) | link do site dentro da mensagem |
| E-mail (HubSpot, transacional) | todos os CTAs |
| Instagram / LinkedIn / X | link da bio e dos posts |
| Anúncios pagos (Google/Meta) | URL final do anúncio |
| Blog / parcerias / guest posts | links de saída para o site |

Tráfego **orgânico de busca** e **direto** não recebem UTM (o GA4 já os classifica
sozinho). Não marque links **internos** do próprio site (quebra a atribuição).

## Os 5 parâmetros

| Parâmetro | Obrigatório | O que é | Exemplos |
|-----------|:-:|---------|----------|
| `utm_source` | ✅ | origem específica | `whatsapp`, `instagram`, `linkedin`, `hubspot`, `google`, `meta` |
| `utm_medium` | ✅ | tipo de canal (define o agrupamento no GA4) | `social`, `email`, `cpc`, `referral`, `organic_social` |
| `utm_campaign` | ✅ | campanha/iniciativa | `rejeicao_1024`, `lc214_lancamento`, `black_friday_2026` |
| `utm_content` | ➖ | variação/criativo (A/B) | `cta_topo`, `banner_v2`, `story_3` |
| `utm_term` | ➖ | palavra-chave (só paga) | `validar_nfe_cbs` |

### Regras de nomenclatura (consistência é tudo)
- **minúsculas**, sem espaços, sem acento. Separador: `_` (underscore).
- Valores de um **vocabulário fixo** (a tabela acima) — `whatsapp` sempre, nunca `Whats`/`wpp`/`zap`.
- `utm_medium` define o **Grupo de Canais** do GA4. Use os medium "canônicos" do
  GA4 para não cair em `Unassigned`: `cpc`/`paid` → Paid; `email` → Email;
  `social`/`organic_social` → Organic Social; `referral` → Referral.

## Modelos prontos (copiar e colar)

```text
# WhatsApp (link do site dentro da mensagem)
https://tribultz.com.br/?utm_source=whatsapp&utm_medium=social&utm_campaign=rejeicao_1024

# Bio do Instagram
https://tribultz.com.br/?utm_source=instagram&utm_medium=organic_social&utm_campaign=perfil_bio

# E-mail HubSpot (CTA principal)
https://tribultz.com.br/pricing?utm_source=hubspot&utm_medium=email&utm_campaign=lc214_lancamento&utm_content=cta_topo

# Google Ads
https://tribultz.com.br/?utm_source=google&utm_medium=cpc&utm_campaign=cbs_ibs&utm_term=validar_nfe_cbs

# LinkedIn (post orgânico)
https://tribultz.com.br/?utm_source=linkedin&utm_medium=organic_social&utm_campaign=conteudo_reforma
```

## Validação no GA4
1. Após publicar links marcados, conferir em **Relatórios → Aquisição → Aquisição
   de tráfego** se o tráfego sai de `Unassigned` para os canais corretos.
2. Cruzar com as conversões (`sign_up`, `begin_checkout`, `purchase`) para obter
   **conversão e receita por canal** → decisão de onde investir.

## Manutenção
Toda nova campanha/canal deve reusar os valores desta tabela. Se precisar de um
`utm_source`/`campaign` novo, adicione-o aqui no mesmo PR para manter o vocabulário
único e a atribuição limpa.
