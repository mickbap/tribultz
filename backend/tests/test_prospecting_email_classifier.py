"""Classificador de domínio de e-mail (PO-2026-07-SALES-001, Fase 1) — puro, sem DB."""

import pytest

from app.services.prospecting.email_classifier import classify_domain, extract_domain


class TestExtractDomain:
    def test_extracts_domain_from_email(self):
        assert extract_domain("contato@escritoriosilva.com.br") == "escritoriosilva.com.br"

    def test_none_when_missing_at(self):
        assert extract_domain("nao-e-email") is None

    def test_none_when_empty(self):
        assert extract_domain("") is None
        assert extract_domain(None) is None


class TestClassifyDomain:
    def test_ausente_when_no_email(self):
        assert classify_domain(None) == "ausente"
        assert classify_domain("") == "ausente"

    @pytest.mark.parametrize("domain", ["gmail.com", "hotmail.com", "yahoo.com.br", "uol.com.br"])
    def test_gratuito_for_known_free_providers(self, domain):
        assert classify_domain(f"contato@{domain}") == "gratuito"

    def test_dominio_nominal_when_domain_derives_from_razao_social(self):
        assert classify_domain(
            "contato@silvacontabilidade.com.br",
            razao_social="Silva Contabilidade Ltda",
        ) == "dominio_nominal"

    def test_dominio_nominal_when_domain_derives_from_nome_fantasia(self):
        assert classify_domain(
            "contato@contafacil.com.br",
            razao_social="J. Pereira Serviços Contábeis Ltda",
            nome_fantasia="ContaFacil",
        ) == "dominio_nominal"

    def test_dominio_generico_when_no_relation_to_company_name(self):
        assert classify_domain(
            "contato@escritoriodigital.com.br",
            razao_social="Almeida & Souza Contabilidade Ltda",
        ) == "dominio_generico"

    def test_generic_legal_suffixes_are_not_enough_to_match(self):
        # "contabilidade"/"ltda" sozinhos não deveriam bastar para casar com
        # qualquer domínio genérico do ramo — são descartados na tokenização.
        assert classify_domain(
            "contato@contabilidadeonline.com.br",
            razao_social="Ferreira Contabilidade Ltda",
        ) == "dominio_generico"
