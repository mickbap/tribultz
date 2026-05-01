"""Parser de arquivo SPED Fiscal (EFD-ICMS/IPI).

Extrai os registros relevantes para validação CBS/IBS:
  0000 — cabeçalho / identificação da empresa
  0200 — tabela de produtos (NCM, CEST, descrição)
  C100 — documento fiscal emitido (NF-e)
  C170 — itens da NF
  C190 — analítico (CST, CFOP, alíquotas)

Formato: linhas pipe-delimitadas  |REGISTRO|campo|campo|...|\n
Encoding: UTF-8 ou latin-1 (tenta UTF-8 primeiro).
"""

from __future__ import annotations

import io
import logging
from datetime import date
from typing import Iterator

logger = logging.getLogger(__name__)

# Índices dos campos por registro (0-based após remover primeiro e último pipe)
_IDX = {
    "0000": {"cod_ver": 1, "dt_ini": 3, "dt_fin": 4, "nome": 5, "cnpj": 6, "uf": 8},
    "0200": {"cod_item": 1, "descr": 2, "unid": 5, "tipo_item": 6, "ncm": 7, "cest": 12},
    "C100": {"ind_oper": 1, "cod_part": 3, "cod_mod": 4, "num_doc": 8, "dt_doc": 10, "vl_doc": 19},
    "C170": {"num_item": 1, "cod_item": 2, "descr_compl": 3, "qtd": 4, "unid": 5, "vl_item": 6, "vl_desc": 7},
    "C190": {"cst_icms": 1, "cfop": 2, "aliq_icms": 3, "vl_bc_icms": 4, "vl_icms": 5},
}


def _parse_date(s: str) -> date | None:
    if not s or len(s) != 8:
        return None
    try:
        return date(int(s[4:8]), int(s[2:4]), int(s[0:2]))
    except ValueError:
        return None


def _safe(fields: list[str], idx: int) -> str:
    try:
        return fields[idx].strip()
    except IndexError:
        return ""


def _iter_lines(content: bytes) -> Iterator[list[str]]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1", errors="replace")

    for raw in io.StringIO(text):
        raw = raw.strip()
        if not raw.startswith("|"):
            continue
        fields = raw.split("|")
        # remove empty first and last elements caused by leading/trailing pipes
        if fields and fields[0] == "":
            fields = fields[1:]
        if fields and fields[-1] == "":
            fields = fields[:-1]
        if fields:
            yield fields


def parse(content: bytes) -> dict:
    """
    Parses SPED Fiscal content and returns:
    {
        "empresa": {"cnpj", "nome", "uf"},
        "periodo": {"ini": date, "fim": date},
        "produtos": [{"cod_item", "descr", "ncm", "cest", "unid"}],
        "nfs": [{"num_doc", "dt_doc", "vl_doc", "itens": [...]}],
        "total_linhas": int,
        "erros_parse": int,
    }
    """
    empresa: dict = {}
    periodo: dict = {}
    produtos: dict[str, dict] = {}   # cod_item → dict
    nfs: list[dict] = []
    nf_atual: dict | None = None
    total = 0
    erros = 0

    for fields in _iter_lines(content):
        total += 1
        reg = fields[0] if fields else ""

        try:
            if reg == "0000":
                idx = _IDX["0000"]
                empresa = {
                    "cnpj": _safe(fields, idx["cnpj"]),
                    "nome": _safe(fields, idx["nome"]),
                    "uf":   _safe(fields, idx["uf"]),
                }
                periodo = {
                    "ini": _parse_date(_safe(fields, idx["dt_ini"])),
                    "fim": _parse_date(_safe(fields, idx["dt_fin"])),
                }

            elif reg == "0200":
                idx = _IDX["0200"]
                cod = _safe(fields, idx["cod_item"])
                if cod:
                    produtos[cod] = {
                        "cod_item":  cod,
                        "descr":     _safe(fields, idx["descr"]),
                        "ncm":       _safe(fields, idx["ncm"]).replace(".", "").replace("-", ""),
                        "cest":      _safe(fields, idx["cest"]).replace(".", ""),
                        "unid":      _safe(fields, idx["unid"]),
                        "tipo_item": _safe(fields, idx["tipo_item"]),
                    }

            elif reg == "C100":
                idx = _IDX["C100"]
                nf_atual = {
                    "num_doc": _safe(fields, idx["num_doc"]),
                    "dt_doc":  _parse_date(_safe(fields, idx["dt_doc"])),
                    "vl_doc":  _safe(fields, idx["vl_doc"]),
                    "itens":   [],
                }
                nfs.append(nf_atual)

            elif reg == "C170" and nf_atual is not None:
                idx = _IDX["C170"]
                nf_atual["itens"].append({
                    "cod_item": _safe(fields, idx["cod_item"]),
                    "vl_item":  _safe(fields, idx["vl_item"]),
                    "qtd":      _safe(fields, idx["qtd"]),
                    "unid":     _safe(fields, idx["unid"]),
                })

            elif reg == "C190" and nf_atual is not None:
                idx = _IDX["C190"]
                nf_atual.setdefault("c190", []).append({
                    "cst_icms":  _safe(fields, idx["cst_icms"]),
                    "cfop":      _safe(fields, idx["cfop"]),
                    "aliq_icms": _safe(fields, idx["aliq_icms"]),
                    "vl_bc":     _safe(fields, idx["vl_bc_icms"]),
                    "vl_icms":   _safe(fields, idx["vl_icms"]),
                })

        except Exception:  # noqa: BLE001
            erros += 1

    return {
        "empresa":      empresa,
        "periodo":      periodo,
        "produtos":     list(produtos.values()),
        "nfs":          nfs,
        "total_linhas": total,
        "erros_parse":  erros,
    }
