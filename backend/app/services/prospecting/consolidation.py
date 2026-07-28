"""Consolidação por CNPJ básico (PO-2026-07-SALES-001, Fase 1).

Duas passadas em streaming sobre Estabelecimentos (nunca carrega os arquivos
inteiros em memória):

  Pass 1 — descobre o conjunto de cnpj_basico cujo CNAE (principal OU
  secundário) de algum estabelecimento bate com um dos CNAEs-alvo (escritório
  contábil: 6920-6/01 e 6920-6/02). Esperado ~80 mil, trivial de manter em
  memória como um set.

  Pass 2 — re-varre Estabelecimentos, mantendo só as linhas cujo cnpj_basico
  está no conjunto-alvo, e agrupa matriz+filiais.

Depois, uma passada única sobre Empresas/Simples/Sócios, mesmo filtro por
conjunto-alvo (nunca uma junção completa contra os arquivos de dezenas de
milhões de linhas).

Decisão de design explícita (não ambiguidade silenciosa): registros cuja matriz
não está com situação cadastral ATIVA são excluídos de todo o universo de
candidatos aqui, não só do Tier A — não há racional comercial para prospectar
CNPJ baixado/suspenso/inapto em qualquer tier. Esta decisão foi oficializada pela
Ordem de Desenvolvimento Complementar à PO-2026-07-SALES-001 (item 7): situação
cadastral é requisito de elegibilidade, não dimensão pontuada — substitui
qualquer interpretação anterior do texto da PO original.

Sócios: só a CONTAGEM por cnpj_basico é mantida — nome e CPF de sócio nunca são
persistidos (minimização LGPD; a Receita já mascara parcialmente o CPF, mas o
pipeline vai além e não guarda nenhum dado pessoal de sócio).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from app.services.prospecting.email_classifier import classify_domain, extract_domain
from app.services.prospecting.rf_parser import (
    SITUACAO_CADASTRAL_ATIVA,
    iter_empresas,
    iter_estabelecimentos,
    iter_simples,
    iter_socios,
    load_municipios,
    parse_bool_sn,
    parse_cnaes_secundarios,
    parse_date_yyyymmdd,
    parse_decimal_br,
    parse_porte,
    parse_situacao_cadastral,
)

logger = logging.getLogger("prospecting.consolidation")

TARGET_CNAES: frozenset[str] = frozenset({"6920601", "6920602"})


@dataclass
class ConsolidatedOrg:
    cnpj_basico: str
    cnpj_matriz: str
    razao_social: str
    nome_fantasia: Optional[str]
    porte: str
    opcao_mei: bool
    opcao_simples: bool
    capital_social: Decimal
    situacao_cadastral: int
    data_situacao_cadastral: Optional[date]
    data_inicio_atividade: Optional[date]
    qtd_socios: int
    qtd_estabelecimentos: int
    uf: str
    municipio_codigo: Optional[str]
    municipio_nome: Optional[str]
    logradouro: Optional[str]
    numero: Optional[str]
    complemento: Optional[str]
    bairro: Optional[str]
    cep: Optional[str]
    ddd_telefone1: Optional[str]
    telefone1: Optional[str]
    email: Optional[str]
    email_domain: Optional[str]
    email_domain_category: str
    cnae_principal: str
    cnaes_secundarios: list[str]
    source_dump_reference: str


def discover_target_cnpj_basicos(
    dump_dir: Path, target_cnaes: frozenset[str] = TARGET_CNAES
) -> set[str]:
    """Pass 1: cnpj_basico cujo CNAE principal OU secundário de QUALQUER
    estabelecimento bate com um CNAE-alvo."""
    target: set[str] = set()
    for row in iter_estabelecimentos(dump_dir):
        secundarias = set(parse_cnaes_secundarios(row["cnae_fiscal_secundaria"]))
        if row["cnae_fiscal_principal"] in target_cnaes or secundarias & target_cnaes:
            target.add(row["cnpj_basico"])
    return target


def _pick_matriz(cnpj_basico: str, rows: list[dict[str, str]]) -> dict[str, str]:
    matrizes = [r for r in rows if r["identificador_matriz_filial"] == "1"]
    if matrizes:
        return matrizes[0]
    logger.warning(
        "cnpj_basico=%s sem estabelecimento matriz explícito — usando o de menor cnpj_ordem",
        cnpj_basico,
    )
    return min(rows, key=lambda r: r["cnpj_ordem"])


def _consolidate_estabelecimentos(
    dump_dir: Path, target_set: set[str]
) -> dict[str, ConsolidatedOrg]:
    """Pass 2: re-varre Estabelecimentos, agrupa por cnpj_basico (só os do
    conjunto-alvo), aplica o gate de situação cadastral ativa."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in iter_estabelecimentos(dump_dir):
        if row["cnpj_basico"] in target_set:
            grouped[row["cnpj_basico"]].append(row)

    municipios = load_municipios(dump_dir)
    orgs: dict[str, ConsolidatedOrg] = {}

    for cnpj_basico, rows in grouped.items():
        matriz = _pick_matriz(cnpj_basico, rows)

        situacao = parse_situacao_cadastral(matriz["situacao_cadastral"])
        if situacao != SITUACAO_CADASTRAL_ATIVA:
            continue  # exclusão do universo inteiro, não só do Tier A — ver docstring

        email = matriz["correio_eletronico"].strip() or None
        domain = extract_domain(email)
        municipio_codigo = matriz["municipio"].strip() or None

        orgs[cnpj_basico] = ConsolidatedOrg(
            cnpj_basico=cnpj_basico,
            cnpj_matriz=f"{cnpj_basico}{matriz['cnpj_ordem']}{matriz['cnpj_dv']}",
            razao_social="",  # preenchido pela passada em Empresas
            nome_fantasia=matriz["nome_fantasia"].strip() or None,
            porte="00",  # preenchido pela passada em Empresas
            opcao_mei=False,  # preenchido pela passada em Simples
            opcao_simples=False,
            capital_social=Decimal("0"),
            situacao_cadastral=situacao,
            data_situacao_cadastral=parse_date_yyyymmdd(matriz["data_situacao_cadastral"]),
            data_inicio_atividade=parse_date_yyyymmdd(matriz["data_inicio_atividade"]),
            qtd_socios=0,  # preenchido pela passada em Sócios
            qtd_estabelecimentos=len(rows),
            uf=matriz["uf"].strip(),
            municipio_codigo=municipio_codigo,
            municipio_nome=municipios.get(municipio_codigo) if municipio_codigo else None,
            logradouro=matriz["logradouro"].strip() or None,
            numero=matriz["numero"].strip() or None,
            complemento=matriz["complemento"].strip() or None,
            bairro=matriz["bairro"].strip() or None,
            cep=matriz["cep"].strip() or None,
            ddd_telefone1=matriz["ddd1"].strip() or None,
            telefone1=matriz["telefone1"].strip() or None,
            email=email,
            email_domain=domain,
            email_domain_category="ausente",  # recomputado após razão social ser conhecida
            cnae_principal=matriz["cnae_fiscal_principal"],
            cnaes_secundarios=parse_cnaes_secundarios(matriz["cnae_fiscal_secundaria"]),
            source_dump_reference="",  # preenchido por build_consolidated_orgs
        )

    return orgs


def _enrich_with_empresas(dump_dir: Path, orgs: dict[str, ConsolidatedOrg]) -> None:
    for row in iter_empresas(dump_dir):
        org = orgs.get(row["cnpj_basico"])
        if org is None:
            continue
        org.razao_social = row["razao_social"].strip()
        org.porte = parse_porte(row["porte"])
        org.capital_social = parse_decimal_br(row["capital_social"])


def _enrich_with_simples(dump_dir: Path, orgs: dict[str, ConsolidatedOrg]) -> None:
    for row in iter_simples(dump_dir):
        org = orgs.get(row["cnpj_basico"])
        if org is None:
            continue
        org.opcao_simples = parse_bool_sn(row["opcao_simples"])
        org.opcao_mei = parse_bool_sn(row["opcao_mei"])


def _enrich_with_socios_count(dump_dir: Path, orgs: dict[str, ConsolidatedOrg]) -> None:
    counts: dict[str, int] = defaultdict(int)
    for row in iter_socios(dump_dir):
        if row["cnpj_basico"] in orgs:
            counts[row["cnpj_basico"]] += 1
    for cnpj_basico, count in counts.items():
        orgs[cnpj_basico].qtd_socios = count


def build_consolidated_orgs(
    dump_dir: Path,
    *,
    dump_reference: str,
    target_cnaes: frozenset[str] = TARGET_CNAES,
) -> list[ConsolidatedOrg]:
    """Orquestra o pipeline completo de consolidação: Parser -> Normalização ->
    Consolidação (do diagrama da PO). Deduplicação e supressão vêm depois,
    em módulos separados (dedup.py, suppression.py)."""
    target_set = discover_target_cnpj_basicos(dump_dir, target_cnaes)
    logger.info("Pass 1: %d cnpj_basico candidatos (CNAE alvo)", len(target_set))

    orgs = _consolidate_estabelecimentos(dump_dir, target_set)
    logger.info("Pass 2: %d organizações após gate de situação cadastral ativa", len(orgs))

    _enrich_with_empresas(dump_dir, orgs)
    _enrich_with_simples(dump_dir, orgs)
    _enrich_with_socios_count(dump_dir, orgs)

    for org in orgs.values():
        org.source_dump_reference = dump_reference
        org.email_domain_category = classify_domain(org.email, org.razao_social, org.nome_fantasia)

    return list(orgs.values())
