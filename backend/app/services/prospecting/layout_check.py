"""Validação de layout dos arquivos da RF (Ordem Complementar à
PO-2026-07-SALES-001, item 2).

Pré-checagem rápida (lê só a primeira linha de cada tabela) antes de qualquer
passada completa — se o número de colunas não bater com o layout oficial já
validado (rf_parser.py), aborta antes de processar qualquer linha. Também
expõe uma checagem de proporção de linhas malformadas por arquivo — usada por
ingest_cnpj_dump.py durante o parsing normal para detectar mudança parcial de
layout que a pré-checagem (só a 1ª linha) não pegaria.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.services.prospecting.rf_parser import (
    EMPRESAS_FIELDS,
    ESTABELECIMENTOS_FIELDS,
    SIMPLES_FIELDS,
    SOCIOS_FIELDS,
    iter_dump_files,
)

_TABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "Empresas": EMPRESAS_FIELDS,
    "Estabelecimentos": ESTABELECIMENTOS_FIELDS,
    "Simples": SIMPLES_FIELDS,
    "Socios": SOCIOS_FIELDS,
}


class LayoutMismatchError(Exception):
    """Layout dos arquivos não bate com o esperado — abortar antes de processar."""


class MalformedRowRatioError(Exception):
    """Proporção de linhas malformadas acima do limite — sinal de layout parcialmente mudado."""


def _first_row_field_count(path: Path) -> int:
    with path.open("r", encoding="latin-1", errors="replace", newline="") as fh:
        first_line = fh.readline()
    return len(first_line.rstrip("\r\n").split(";"))


def detect_layout_signature(dump_dir: Path) -> str:
    """Confere a primeira linha de cada tabela contra o número de campos
    esperado. Levanta LayoutMismatchError na primeira divergência — não
    processa nenhuma linha antes desta checagem passar.

    Retorna uma assinatura textual estável (ex.: "empresas:7campos;
    estabelecimentos:30campos;...") gravada em ProspectIngestionRun para
    auditoria de qual layout foi usado em cada execução.
    """
    signature_parts: list[str] = []
    for table_name, fields in _TABLE_FIELDS.items():
        files = iter_dump_files(dump_dir, table_name)
        if not files:
            raise LayoutMismatchError(
                f"Nenhum arquivo encontrado para a tabela {table_name} em {dump_dir}"
            )
        actual = _first_row_field_count(files[0])
        expected = len(fields)
        if actual != expected:
            raise LayoutMismatchError(
                f"{table_name}: {actual} campos encontrados na primeira linha, {expected} "
                "esperados (layout pode ter mudado — revalidar contra "
                "gov.br/receitafederal/dados/cnpj-metadados.pdf antes de prosseguir)."
            )
        signature_parts.append(f"{table_name.lower()}:{expected}campos")
    return ";".join(signature_parts)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_file_hashes(dump_dir: Path) -> dict[str, str]:
    """Hash de cada arquivo usado nesta execução — item 2 (proveniência)."""
    hashes: dict[str, str] = {}
    for table_name in (*_TABLE_FIELDS, "Municipios"):
        for path in iter_dump_files(dump_dir, table_name):
            hashes[path.name] = sha256_file(path)
    return hashes


def check_malformed_ratio(file_name: str, malformed: int, total: int, max_ratio: float) -> None:
    """Levanta MalformedRowRatioError se malformed/total ultrapassar max_ratio."""
    if total == 0:
        return
    ratio = malformed / total
    if ratio > max_ratio:
        raise MalformedRowRatioError(
            f"{file_name}: {malformed}/{total} linhas malformadas ({ratio:.1%}), acima do "
            f"limite ({max_ratio:.1%}) — layout pode ter mudado parcialmente."
        )
