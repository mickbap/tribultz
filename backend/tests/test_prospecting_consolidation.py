"""Consolidação por CNPJ básico (PO-2026-07-SALES-001, Fase 1) — puro, sem DB.

Cobre exatamente a lista de risco do plano aprovado: consolidação matriz+filiais,
match de CNAE-alvo via secundária, exclusão por situação cadastral inativa,
enriquecimento cruzado (Empresas/Simples/Sócios) e classificação de domínio de
e-mail já com a razão social conhecida.
"""

from decimal import Decimal
from pathlib import Path

from app.services.prospecting.consolidation import (
    TARGET_CNAES,
    build_consolidated_orgs,
    discover_target_cnpj_basicos,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "prospecting"


class TestDiscoverTargetCnpjBasicos:
    def test_matches_principal_cnae(self):
        target = discover_target_cnpj_basicos(FIXTURE_DIR, TARGET_CNAES)
        assert "10000000" in target  # ALPHA: CNAE principal 6920601
        assert "30000000" in target  # GAMA: CNAE principal 6920602 (mesmo baixada)
        assert "40000000" in target  # DELTA: CNAE principal 6920601

    def test_matches_secondary_cnae(self):
        target = discover_target_cnpj_basicos(FIXTURE_DIR, TARGET_CNAES)
        assert "20000000" in target  # BETA: CNAE alvo só na secundária

    def test_negative_control_never_in_target_set(self):
        target = discover_target_cnpj_basicos(FIXTURE_DIR, TARGET_CNAES)
        assert "50000000" not in target  # LOJA QUALQUER: nenhum CNAE alvo


class TestBuildConsolidatedOrgs:
    def test_excludes_org_with_inactive_matriz(self):
        """GAMA tem CNAE-alvo mas situação cadastral BAIXADA — decisão de design
        documentada: exclusão de todo o universo de candidatos, não só do Tier A."""
        orgs = build_consolidated_orgs(FIXTURE_DIR, dump_reference="2026-07-fixture")
        cnpjs = {o.cnpj_basico for o in orgs}
        assert "30000000" not in cnpjs
        assert len(orgs) == 3  # ALPHA, BETA, DELTA (GAMA excluída, LOJA nunca no alvo)

    def test_consolidates_matriz_and_filiais(self):
        orgs = build_consolidated_orgs(FIXTURE_DIR, dump_reference="2026-07-fixture")
        alpha = next(o for o in orgs if o.cnpj_basico == "10000000")
        assert alpha.qtd_estabelecimentos == 3  # matriz + 2 filiais
        assert alpha.uf == "RS"  # endereço da matriz, não de uma filial
        assert alpha.cnpj_matriz == "10000000000191"

    def test_enriches_from_empresas_simples_socios(self):
        orgs = build_consolidated_orgs(FIXTURE_DIR, dump_reference="2026-07-fixture")
        alpha = next(o for o in orgs if o.cnpj_basico == "10000000")
        assert alpha.razao_social == "ESCRITORIO ALPHA CONTABILIDADE LTDA"
        assert alpha.porte == "05"
        assert alpha.capital_social == Decimal("100000.00")
        assert alpha.opcao_simples is True
        assert alpha.opcao_mei is False
        assert alpha.qtd_socios == 2  # dois sócios no fixture

    def test_mei_flag_comes_from_simples_not_empresas_porte(self):
        orgs = build_consolidated_orgs(FIXTURE_DIR, dump_reference="2026-07-fixture")
        beta = next(o for o in orgs if o.cnpj_basico == "20000000")
        assert beta.opcao_mei is True
        assert beta.qtd_estabelecimentos == 1
        assert beta.qtd_socios == 1

    def test_email_domain_category_uses_razao_social_known_only_after_enrichment(self):
        orgs = build_consolidated_orgs(FIXTURE_DIR, dump_reference="2026-07-fixture")
        alpha = next(o for o in orgs if o.cnpj_basico == "10000000")
        beta = next(o for o in orgs if o.cnpj_basico == "20000000")
        delta = next(o for o in orgs if o.cnpj_basico == "40000000")
        assert alpha.email_domain_category == "dominio_nominal"
        assert beta.email_domain_category == "gratuito"
        assert delta.email_domain_category == "ausente"  # sem correio_eletronico no fixture

    def test_email_type_classified_independently_of_domain(self):
        # Ordem Complementar, item 6 — dimensão separada de email_domain_category.
        orgs = build_consolidated_orgs(FIXTURE_DIR, dump_reference="2026-07-fixture")
        alpha = next(o for o in orgs if o.cnpj_basico == "10000000")
        beta = next(o for o in orgs if o.cnpj_basico == "20000000")
        delta = next(o for o in orgs if o.cnpj_basico == "40000000")
        assert alpha.email_type == "contato"  # contato@alphacontabilidade.com.br
        assert beta.email_type == "outro"  # beta@gmail.com
        assert delta.email_type == "ausente"  # sem correio_eletronico

    def test_source_dump_reference_is_stamped_on_every_org(self):
        orgs = build_consolidated_orgs(FIXTURE_DIR, dump_reference="2026-07-fixture")
        assert all(o.source_dump_reference == "2026-07-fixture" for o in orgs)
