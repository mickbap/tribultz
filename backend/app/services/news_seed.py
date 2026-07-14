from __future__ import annotations

import logging

from sqlalchemy import inspect, select

from app.database import SessionLocal, engine
from app.models.news import News

logger = logging.getLogger(__name__)

DEFAULT_NEWS_TITLE = "Lançamento da Memória Fiscal Multi-tenant"
DEFAULT_NEWS_DESCRIPTION = (
    "Ativamos a memória fiscal persistente com isolamento por tenant, "
    "armazenamento em Redis e recuperação de precedentes após reinício da API."
)
DEFAULT_NEWS_CATEGORY = "Feature"

# Campanha "contagem regressiva 03/08" (#407). Categoria Advisory: fato
# regulatório externo, não recurso novo do produto — cada entrada é honesta
# sobre o que a Tribultz já cobre hoje vs. o que está em avaliação/roadmap.
REGULATORY_ADVISORIES: list[dict[str, str]] = [
    {
        "title": "03/08/2026: SEFAZ passa a rejeitar NF-e sem IBS/CBS no Regime Normal (CRT 3)",
        "description": (
            "A partir de 03/08/2026 entram em produção, para o Regime Normal (CRT 3), as "
            "regras UB12-10 e W34-20 da NT 2025.002-RTC v1.40: Rejeição 1115 (IBS/CBS ausente "
            "no item) e Rejeição 1119 (grupo de totais IBSCBSTot ausente quando algum item "
            "informa IBS/CBS). Simples Nacional e MEI entram em 04/01/2027. A Tribultz já "
            "valida esses cenários antes da emissão, em /validate-xml. "
            "Fonte: NT 2025.002-RTC v1.40 (SEFAZ/CONFAZ)."
        ),
    },
    {
        "title": "NT 2025.002 v1.50: novo grupo para o regime monofásico de combustíveis (CBS/IBS)",
        "description": (
            "Foi publicada a versão 1.50 da NT 2025.002-RTC, com um grupo específico para "
            "operações do regime monofásico de combustíveis e novos indicadores de "
            "cClassTrib. A cobertura dessas regras no motor de validação da Tribultz está "
            "em avaliação — acompanhe as próximas atualizações neste changelog. "
            "Fonte: NT 2025.002-RTC v1.50 (Portal Nacional da NF-e)."
        ),
    },
    {
        "title": "Novos leiautes: NT 2026.002 (presencial/não presencial) e NT 2026.003 (DANFE Simplificado T2)",
        "description": (
            "Foram publicados os schemas das Notas Técnicas 2026.002 (indicador de operação "
            "presencial/não presencial) e 2026.003 (DANFE Simplificado modelo T2). O impacto "
            "no parser de validação da Tribultz está em avaliação — acompanhe as próximas "
            "atualizações neste changelog. Fonte: Portal Nacional da NF-e / SEFAZ."
        ),
    },
    {
        "title": "Split Payment: Receita Federal e CGIBS publicam Manual de Integração e Swagger da Plataforma Pública",
        "description": (
            "O Ato Conjunto RFB/CGIBS nº 2/2026 (03/06/2026) autorizou a publicação do Manual "
            "de Integração e da especificação técnica (Swagger) da Plataforma Pública do "
            "Split Payment, mecanismo de retenção automática de IBS/CBS previsto para 2027. "
            "A Tribultz oferece hoje conteúdo e simulação de impacto em /split-payment. "
            "Fonte: Receita Federal / Comitê Gestor do IBS."
        ),
    },
]
REGULATORY_ADVISORY_CATEGORY = "Advisory"


def ensure_default_news_entry() -> None:
    if not inspect(engine).has_table("news"):
        return

    with SessionLocal() as db:
        existing = db.scalar(
            select(News.id).where(
                News.title == DEFAULT_NEWS_TITLE,
                News.category == DEFAULT_NEWS_CATEGORY,
            )
        )
        if existing is not None:
            return

        db.add(
            News(
                title=DEFAULT_NEWS_TITLE,
                description=DEFAULT_NEWS_DESCRIPTION,
                category=DEFAULT_NEWS_CATEGORY,
            )
        )
        db.commit()
        logger.info("default_news_seeded title=%s", DEFAULT_NEWS_TITLE)


def ensure_regulatory_advisories() -> None:
    """Semeia as 4 notícias regulatórias da campanha 03/08 (#407), idempotente."""
    if not inspect(engine).has_table("news"):
        return

    with SessionLocal() as db:
        for entry in REGULATORY_ADVISORIES:
            existing = db.scalar(
                select(News.id).where(
                    News.title == entry["title"],
                    News.category == REGULATORY_ADVISORY_CATEGORY,
                )
            )
            if existing is not None:
                continue

            db.add(
                News(
                    title=entry["title"],
                    description=entry["description"],
                    category=REGULATORY_ADVISORY_CATEGORY,
                )
            )
            db.commit()
            logger.info("regulatory_advisory_seeded title=%s", entry["title"])
