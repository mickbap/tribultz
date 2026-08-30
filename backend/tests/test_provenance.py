"""Contrato da fundação de proveniência regulatória (#682)."""
from __future__ import annotations

import datetime as dt

import pytest

from app.data.provenance import (
    ArtifactProvenance,
    ProvenanceError,
    fingerprint_bytes,
    fingerprint_payload,
)

OFICIAL = "https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=x"


def _prov(**kw) -> ArtifactProvenance:
    base = dict(
        artefato="IT 2023.002",
        versao="2.00",
        fonte="Portal Nacional da NF-e — Documentos › Diversos",
        source_url=OFICIAL,
        observado_em=dt.date(2026, 8, 29),
        fingerprint="a" * 64,
    )
    base.update(kw)
    return ArtifactProvenance(**base)  # type: ignore[arg-type]


class TestContratoMinimo:
    def test_os_seis_campos_do_contrato_existem(self):
        d = _prov().to_dict()
        for campo in ("artefato", "versao", "fonte", "source_url", "observado_em", "fingerprint"):
            assert campo in d, campo

    def test_roundtrip_preserva_identidade(self):
        p = _prov()
        assert ArtifactProvenance.from_dict(p.to_dict()) == p

    def test_roundtrip_de_fonte_viva_preserva_none(self):
        p = _prov(versao=None)
        assert ArtifactProvenance.from_dict(p.to_dict()).versao is None


class TestFonteViva:
    def test_versao_none_e_estado_legitimo(self):
        p = _prov(versao=None, source_url="https://dfe-portal.svrs.rs.gov.br/CFF/ClassificacaoTributaria")
        assert p.is_live_source is True
        assert "fonte viva" in p.rotulo()

    def test_versao_em_branco_e_rejeitada_por_ser_ambigua(self):
        # "não tem versão" (None) != "não sabemos a versão" ("" ou "  ")
        for vazio in ("", "   "):
            with pytest.raises(ProvenanceError, match="ambígua"):
                _prov(versao=vazio)

    def test_artefato_versionado_nao_e_fonte_viva(self):
        assert _prov().is_live_source is False
        assert _prov().rotulo() == "IT 2023.002 v2.00"


class TestAutoridadeNormativa:
    @pytest.mark.parametrize("url", [
        "https://www.nfe.fazenda.gov.br/portal/x",
        "https://dfe-portal.svrs.rs.gov.br/CFF/ClassificacaoTributaria",
        "https://www.confaz.fazenda.gov.br/x",
    ])
    def test_portais_oficiais_sao_aceitos(self, url):
        assert _prov(source_url=url).source_url == url

    @pytest.mark.parametrize("url", [
        "https://fiscoscan.com.br/tabela-cfop",
        "https://www.forumsped.com.br/topico/725",
        "https://documentacao.senior.com.br/nt-2026-002",
        "https://blog.contabilidade.com/cfop",
    ])
    def test_fonte_secundaria_e_recusada_como_autoridade(self, url):
        with pytest.raises(ProvenanceError, match="não oficial"):
            _prov(source_url=url)

    def test_url_malformada_nao_vira_host_vazio_aceito(self):
        with pytest.raises(ProvenanceError, match="não oficial"):
            _prov(source_url="nao-e-url")


class TestObrigatorios:
    @pytest.mark.parametrize("campo", ["artefato", "fonte", "fingerprint"])
    def test_campo_vazio_falha(self, campo):
        with pytest.raises(ProvenanceError):
            _prov(**{campo: "  "})


class TestFingerprint:
    def test_conteudo_bruto_identico_gera_hash_identico(self):
        assert fingerprint_bytes(b"abc") == fingerprint_bytes(b"abc")

    def test_um_byte_diferente_muda_o_hash(self):
        assert fingerprint_bytes(b"abc") != fingerprint_bytes(b"abd")

    def test_payload_normalizado_ignora_ordem_de_chaves(self):
        assert fingerprint_payload({"a": 1, "b": 2}) == fingerprint_payload({"b": 2, "a": 1})

    def test_payload_detecta_edicao_in_place_de_valor(self):
        assert fingerprint_payload({"a": 1}) != fingerprint_payload({"a": 2})


class TestDeteccaoDeMudanca:
    def test_reobservar_o_mesmo_conteudo_em_outra_data_nao_e_mudanca(self):
        antes = _prov(observado_em=dt.date(2026, 8, 1))
        depois = antes.observed_now(dt.date(2026, 8, 29))
        assert depois.changed_from(antes) is False
        assert depois.observado_em == dt.date(2026, 8, 29)

    def test_conteudo_diferente_e_mudanca_mesmo_com_a_mesma_versao(self):
        # edição in-place do artefato sem bump de versão é exatamente o que o
        # fingerprint existe para pegar
        assert _prov(fingerprint="b" * 64).changed_from(_prov()) is True
