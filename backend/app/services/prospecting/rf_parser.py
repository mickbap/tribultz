"""Parser em streaming dos arquivos de Dados Abertos do CNPJ (PO-2026-07-SALES-001,
Fase 1).

Ordem dos campos validada contra o layout oficial vigente
(gov.br/receitafederal/dados/cnpj-metadados.pdf, lido diretamente nesta entrega).

Encoding dos códigos numéricos (situação cadastral, porte): o PDF mostra "01 – NULA"
mas também "2 – ATIVA"/"08 – BAIXADA", inconsistente quanto a zero à esquerda —
isso é só formatação do documento, não necessariamente o texto bruto do arquivo.
Confirmado empiricamente contra o ETL público mais usado para este dataset
(github.com/aphonsoar/Receita_Federal_do_Brasil_-_Dados_Publicos_CNPJ,
code/ETL_coletar_dados_e_gravar_BD.py): ele lê situação cadastral e porte com
dtype pandas 'Int32', ou seja, são numéricos — para não depender de padding,
normalizamos aqui via int() e nunca comparamos a string bruta.

Arquivos reais são multi-GB, latin-1, separados por ';', sem cabeçalho, divididos
em várias partes por tabela (Estabelecimentos0.csv..9.csv etc.) — por isso tudo
aqui é streaming (csv.reader sobre arquivo aberto), nunca carrega o arquivo
inteiro em memória.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

logger = logging.getLogger("prospecting.rf_parser")

# Ordem exata dos campos por arquivo — validada contra o PDF oficial.
EMPRESAS_FIELDS: tuple[str, ...] = (
    "cnpj_basico", "razao_social", "natureza_juridica", "qualificacao_responsavel",
    "capital_social", "porte", "ente_federativo_responsavel",
)

ESTABELECIMENTOS_FIELDS: tuple[str, ...] = (
    "cnpj_basico", "cnpj_ordem", "cnpj_dv", "identificador_matriz_filial",
    "nome_fantasia", "situacao_cadastral", "data_situacao_cadastral",
    "motivo_situacao_cadastral", "nome_cidade_exterior", "pais",
    "data_inicio_atividade", "cnae_fiscal_principal", "cnae_fiscal_secundaria",
    "tipo_logradouro", "logradouro", "numero", "complemento", "bairro", "cep",
    "uf", "municipio", "ddd1", "telefone1", "ddd2", "telefone2", "ddd_fax",
    "fax", "correio_eletronico", "situacao_especial", "data_situacao_especial",
)

SIMPLES_FIELDS: tuple[str, ...] = (
    "cnpj_basico", "opcao_simples", "data_opcao_simples", "data_exclusao_simples",
    "opcao_mei", "data_opcao_mei", "data_exclusao_mei",
)

SOCIOS_FIELDS: tuple[str, ...] = (
    "cnpj_basico", "identificador_socio", "nome_socio", "cnpj_cpf_socio",
    "qualificacao_socio", "data_entrada_sociedade", "pais", "representante_legal",
    "nome_representante", "qualificacao_representante_legal", "faixa_etaria",
)

MUNICIPIOS_FIELDS: tuple[str, ...] = ("codigo", "descricao")

# Situação cadastral (código -> descrição), do layout oficial. ATIVA é o único
# código elegível para prospecção — ver consolidation.py.
SITUACAO_CADASTRAL_ATIVA = 2


def iter_dump_files(dump_dir: Path, prefix: str) -> list[Path]:
    """Lista os arquivos de uma tabela (ex.: "Estabelecimentos") em ordem estável.

    A RF divide cada tabela em várias partes (Estabelecimentos0, Estabelecimentos1,
    ...) — a ordem entre elas não importa para correção, só para reprodutibilidade
    de logs, por isso ordenamos por nome.
    """
    return sorted(dump_dir.glob(f"{prefix}*"))


@dataclass
class RowCounts:
    """Contador mutável passado por referência — permite ao chamador ler
    total/malformed depois de consumir o iterador (ex.: para o guard de
    sanidade e a checagem de proporção de linhas malformadas, Ordem
    Complementar, itens 1 e 2)."""

    total: int = 0
    malformed: int = 0


def _iter_rows(
    path: Path, fields: tuple[str, ...], counts: Optional["RowCounts"] = None
) -> Iterator[dict[str, str]]:
    """Itera as linhas de um arquivo da RF em streaming, nunca carregando tudo em
    memória. Linhas com número de colunas diferente do esperado são logadas e
    puladas — um dump de dezenas de milhões de linhas não pode falhar inteiro
    por uma linha malformada (a proporção agregada é checada por quem chama,
    via RowCounts — ver layout_check.check_malformed_ratio).
    """
    with path.open("r", encoding="latin-1", errors="replace", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        for line_no, row in enumerate(reader, start=1):
            if counts is not None:
                counts.total += 1
            if len(row) != len(fields):
                if counts is not None:
                    counts.malformed += 1
                logger.warning(
                    "Linha malformada ignorada: %s:%d (esperado %d campos, veio %d)",
                    path.name, line_no, len(fields), len(row),
                )
                continue
            yield dict(zip(fields, row))


def iter_empresas(dump_dir: Path, counts: Optional["RowCounts"] = None) -> Iterator[dict[str, str]]:
    for path in iter_dump_files(dump_dir, "Empresas"):
        yield from _iter_rows(path, EMPRESAS_FIELDS, counts)


def iter_estabelecimentos(
    dump_dir: Path, counts: Optional["RowCounts"] = None
) -> Iterator[dict[str, str]]:
    for path in iter_dump_files(dump_dir, "Estabelecimentos"):
        yield from _iter_rows(path, ESTABELECIMENTOS_FIELDS, counts)


def iter_simples(dump_dir: Path, counts: Optional["RowCounts"] = None) -> Iterator[dict[str, str]]:
    for path in iter_dump_files(dump_dir, "Simples"):
        yield from _iter_rows(path, SIMPLES_FIELDS, counts)


def iter_socios(dump_dir: Path, counts: Optional["RowCounts"] = None) -> Iterator[dict[str, str]]:
    for path in iter_dump_files(dump_dir, "Socios"):
        yield from _iter_rows(path, SOCIOS_FIELDS, counts)


def load_municipios(dump_dir: Path) -> dict[str, str]:
    """Carrega a tabela de domínio Municípios inteira em memória — é pequena
    (poucos milhares de linhas), ao contrário das 4 tabelas-fato principais."""
    result: dict[str, str] = {}
    for path in iter_dump_files(dump_dir, "Municipios"):
        for row in _iter_rows(path, MUNICIPIOS_FIELDS):
            result[row["codigo"].strip()] = row["descricao"].strip()
    return result


# ── Normalização de campos ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ParseWarning:
    field: str
    raw_value: str
    context: str


def parse_situacao_cadastral(raw: str) -> Optional[int]:
    """Normaliza via int() — nunca compara a string bruta (ver nota no topo do
    módulo sobre a ambiguidade de zero à esquerda no PDF)."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def parse_porte(raw: str) -> str:
    """Normaliza para 2 dígitos com zero à esquerda (forma canônica usada como
    chave na rubrica: "00"/"01"/"03"/"05"), independente de como o arquivo real
    representa o valor (com ou sem padding)."""
    raw = raw.strip()
    if not raw:
        return "00"
    try:
        return f"{int(raw):02d}"
    except ValueError:
        return "00"


def parse_bool_sn(raw: str) -> bool:
    """S/N/branco -> bool. Branco ("outros", por definição do layout oficial) é
    colapsado em False — só o eixo MEI/não-MEI importa para o pré-score da Fase 1."""
    return raw.strip().upper() == "S"


def parse_decimal_br(raw: str) -> Decimal:
    """RF usa vírgula como separador decimal (ex.: "150000,00")."""
    raw = raw.strip()
    if not raw:
        return Decimal("0")
    try:
        return Decimal(raw.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return Decimal("0")


def parse_date_yyyymmdd(raw: str) -> Optional[date]:
    """Datas da RF vêm como YYYYMMDD ou em branco (nunca ocorreram)."""
    raw = raw.strip()
    if not raw or raw == "0" * len(raw):
        return None
    try:
        return date(int(raw[0:4]), int(raw[4:6]), int(raw[6:8]))
    except (ValueError, IndexError):
        return None


def parse_cnaes_secundarios(raw: str) -> list[str]:
    """CNAE fiscal secundária: múltiplas ocorrências separadas por vírgula
    (regra explícita do layout oficial)."""
    return [c.strip() for c in raw.split(",") if c.strip()]
