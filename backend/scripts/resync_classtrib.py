#!/usr/bin/env python3
"""Re-sincroniza backend/app/data/classtrib.json a partir da fonte oficial SVRS (#313).

A API SVRS Conformidade Fácil (cff.svrs.rs.gov.br) exige credencial institucional
e bloqueia IPs fora da allowlist. PORÉM, a *consulta pública web* em
https://dfe-portal.svrs.rs.gov.br/CFF/ClassificacaoTributaria embute o registro
completo do classTrib como JSON na própria página — fonte autoritativa e acessível
sem credencial. Este script:

  1. baixa a página pública (ou usa --html para um arquivo local),
  2. extrai o maior blob JSON balanceado com os registros (campo CstNavigation/
     ClassificacoesTributarias),
  3. normaliza no schema do classtrib.json (by_code / by_cst / cst_descriptions / meta),
  4. grava o arquivo e imprime um diff resumido vs a versão anterior.

Uso:
    python scripts/resync_classtrib.py [--html caminho.html] [--out caminho.json] [--dry-run]

NÃO re-popula cclass_trib_items (DB): a tabela guarda alíquotas absolutas e a fonte
SVRS fornece apenas reduções — a derivação redução→alíquota é tratada junto do #278.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

SOURCE_URL = "https://dfe-portal.svrs.rs.gov.br/CFF/ClassificacaoTributaria"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "classtrib.json"

# Indicadores por DFe na fonte SVRS → rótulo no classtrib.json.
_DFE_INDICATORS = {
    "IndNfe": "NFE", "IndNfce": "NFCE", "IndCte": "CTE", "IndCteos": "CTEOS",
    "IndBpe": "BPE", "IndNf3e": "NF3E", "IndNfcom": "NFCOM", "IndNfse": "NFSE",
    "IndBpetm": "BPETM", "IndBpeta": "BPETA", "IndNfag": "NFAG", "IndNfgas": "NFGAS",
    "IndNfsvia": "NFSVIA", "IndNfabi": "NFABI",
}


def fetch_html() -> str:
    import httpx

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        "Accept": "text/html,application/json,*/*",
    }
    with httpx.Client(timeout=60, headers=headers, follow_redirects=True) as client:
        resp = client.get(SOURCE_URL)
        resp.raise_for_status()
        return resp.text


def extract_groups(html: str) -> list[dict]:
    """Extrai o maior blob JSON balanceado contendo os grupos de CST/classificações."""
    decoder = json.JSONDecoder()
    best: list | None = None
    i, n = 0, len(html)
    while i < n:
        if html[i] in "[{":
            try:
                obj, end = decoder.raw_decode(html, i)
            except ValueError:
                i += 1
                continue
            chunk = html[i:end]
            if (end - i) > 2000 and ("ClassificacoesTributarias" in chunk or '"Cst"' in chunk):
                if best is None or (end - i) > len(json.dumps(best)):
                    best = obj
                i = end
                continue
        i += 1
    if not isinstance(best, list):
        raise SystemExit("ERRO: blob JSON de classTrib não encontrado na página.")
    return best


def normalize(groups: list[dict]) -> dict:
    by_code: dict[str, dict] = {}
    by_cst: dict[str, list[str]] = {}
    cst_descriptions: dict[str, str] = {}

    for grp in groups:
        cst = str(grp.get("Cst", "")).strip()
        nome_cst = (grp.get("NomeCst") or "").strip()
        if cst:
            cst_descriptions[cst] = nome_cst
        for c in grp.get("ClassificacoesTributarias") or []:
            code = str(c.get("CodClassTrib", "")).strip()
            if not code:
                continue
            dfe = sorted(label for ind, label in _DFE_INDICATORS.items() if c.get(ind))
            by_code[code] = {
                "cst": cst,
                "cst_description": nome_cst,
                "description": (c.get("NomeClassTrib") or "").strip(),
                "reduction_ibs_pct": float(c.get("PercRedIbs") or 0.0),
                "reduction_cbs_pct": float(c.get("PercRedCbs") or 0.0),
                "tipo_aliquota": c.get("TipoAliq"),
                # Crédito presumido IBS/CBS: se True, a operação pode carregar a tag cCredPres
                # (#339). Só alguns cClassTrib permitem — fonte SVRS: IndPermiteCredPres.
                "permite_cred_pres": bool(c.get("IndPermiteCredPres")),
                "dfe_allowed": dfe,
                "vigencia_ini": (c.get("DthIniVig") or "")[:10],
                "legislacao": c.get("TexUrlLegislacao") or "",
            }
            by_cst.setdefault(cst, []).append(code)

    for cst in by_cst:
        by_cst[cst].sort()

    return {
        "meta": {
            "source": "SVRS Conformidade Fácil — consulta pública classTrib (sem credencial)",
            "source_url": SOURCE_URL,
            "extraction_method": "JSON embutido na página /CFF/ClassificacaoTributaria",
            "date": dt.date.today().isoformat(),
            "total_codes": len(by_code),
            "total_cst_groups": len(cst_descriptions),
        },
        "by_code": dict(sorted(by_code.items())),
        "by_cst": dict(sorted(by_cst.items())),
        "cst_descriptions": dict(sorted(cst_descriptions.items())),
    }


def normalize_ncm_mapping(groups: list[dict]) -> dict:
    """Mapeia NCM/NBS → candidatos cClassTrib (6-díg) + base legal, dos anexos (RF-A2 / Order A).

    Cada classificação traz uma lista `Anexos` com `CodNcmNbs` (NCM 8-díg ou NBS 9-díg).
    A mesma NCM pode aparecer em vários cClassTrib → candidatos (a validar, não veredito).
    """
    mapping: dict[str, list[dict]] = {}
    for grp in groups:
        for c in grp.get("ClassificacoesTributarias") or []:
            cod = str(c.get("CodClassTrib", "")).strip()
            leg = c.get("TexUrlLegislacao") or ""
            for ax in c.get("Anexos") or []:
                ncm = str(ax.get("CodNcmNbs") or "").strip()
                if not ncm or not cod:
                    continue
                base = f"Anexo {ax.get('NroAnexo')}"
                desc = (ax.get("DescAnexo") or "").strip()
                if desc:
                    base += f" — {desc}"
                mapping.setdefault(ncm, [])
                if not any(e["codigo"] == cod for e in mapping[ncm]):
                    mapping[ncm].append({"codigo": cod, "base_legal": base, "legislacao": leg})
    for ncm in mapping:
        mapping[ncm].sort(key=lambda e: e["codigo"])
    return {
        "meta": {
            "source": "SVRS Conformidade Fácil — consulta pública (anexos NCM/NBS → cClassTrib)",
            "source_url": SOURCE_URL,
            "date": dt.date.today().isoformat(),
            "total_ncm": len(mapping),
            "total_pares": sum(len(v) for v in mapping.values()),
        },
        "by_ncm": dict(sorted(mapping.items())),
    }


def print_diff(old: dict, new: dict) -> None:
    old_codes = set(old.get("by_code", {}))
    new_codes = set(new["by_code"])
    added = sorted(new_codes - old_codes)
    removed = sorted(old_codes - new_codes)
    print(f"\n── DIFF vs versão anterior ({old.get('meta', {}).get('date', '?')}) ──")
    print(f"  total: {len(old_codes)} → {len(new_codes)}")
    print(f"  + adicionados: {len(added)}")
    print(f"  - removidos:   {len(removed)}")
    if removed:
        print(f"    removidos: {removed[:20]}{' …' if len(removed) > 20 else ''}")
    print(f"  amostra adicionados: {added[:10]}")
    # checagem de sanidade: códigos devem ser 6 dígitos
    bad = [c for c in new_codes if not (c.isdigit() and len(c) == 6)]
    if bad:
        print(f"  ⚠️  códigos fora do formato 6 dígitos: {bad[:10]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="arquivo HTML local (em vez de baixar)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dry-run", action="store_true", help="não grava, só mostra o diff")
    args = ap.parse_args()

    html = Path(args.html).read_text(encoding="utf-8", errors="replace") if args.html else fetch_html()
    groups = extract_groups(html)
    new = normalize(groups)

    if len(new["by_code"]) < 74:
        raise SystemExit(f"ERRO: só {len(new['by_code'])} códigos extraídos (< 74) — abortando p/ não degradar dados.")

    out_path = Path(args.out)
    old = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    print_diff(old, new)

    if args.dry_run:
        print("\n[dry-run] nada gravado.")
        return 0

    out_path.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n✓ gravado {out_path} ({len(new['by_code'])} códigos)")

    # Mapeamento NCM→cClassTrib (anexos) — candidatos do ncm/suggest e /classify (RF-A2, Order A).
    ncm_map = normalize_ncm_mapping(groups)
    if ncm_map["meta"]["total_ncm"] < 500:
        raise SystemExit(f"ERRO: só {ncm_map['meta']['total_ncm']} NCMs mapeadas (< 500) — abortando.")
    ncm_path = out_path.parent / "ncm_cclasstrib.json"
    ncm_path.write_text(json.dumps(ncm_map, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✓ gravado {ncm_path} ({ncm_map['meta']['total_ncm']} NCMs, {ncm_map['meta']['total_pares']} pares)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
