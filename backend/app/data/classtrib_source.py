"""Extração e assinatura da fonte oficial cClassTrib (SVRS) — implementação ÚNICA.

Extraído de ``scripts/resync_classtrib.py`` (#673) para que o coletor e a probe de
frescor falem exatamente a mesma língua. Antes havia risco de duas leituras
divergentes da mesma página: a probe poderia declarar "sem mudança" comparando um
universo diferente do que o coletor grava.

O script continua dono do que é dele — ``fetch_html`` com retry, guards de
sanidade, diff legível, CLI e escrita em disco. Aqui ficam apenas as funções
puras que ambos precisam.

Fonte: consulta pública da SVRS, **sem credencial**. Nada aqui toca APIs
governamentais autenticadas (RFB/CGIBS) — essas têm desenho próprio em
ADR-0016/0017 e RFC-0027/0028.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Optional

SOURCE_URL = "https://dfe-portal.svrs.rs.gov.br/CFF/ClassificacaoTributaria"

#: Indicadores por DFe na fonte SVRS → rótulo no classtrib.json.
DFE_INDICATORS = {
    "IndNfe": "NFE", "IndNfce": "NFCE", "IndCte": "CTE", "IndCteos": "CTEOS",
    "IndBpe": "BPE", "IndNf3e": "NF3E", "IndNfcom": "NFCOM", "IndNfse": "NFSE",
    "IndBpetm": "BPETM", "IndBpeta": "BPETA", "IndNfag": "NFAG", "IndNfgas": "NFGAS",
    "IndNfsvia": "NFSVIA", "IndNfabi": "NFABI",
}

#: Chaves de DADOS comparadas para detectar mudança real. O bloco ``meta`` — que
#: carrega ``date`` e contagens — é deliberadamente ignorado: senão todo dia
#: haveria "mudança" só porque o carimbo mudou.
CODE_KEYS = ("by_code", "by_cst", "cst_descriptions")
NCM_KEYS = ("by_ncm",)


def extract_groups(html: str) -> list:
    """Maior blob JSON balanceado contendo os grupos de CST/classificações."""
    decoder = json.JSONDecoder()
    best: Optional[list] = None
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
        raise ValueError("blob JSON de classTrib não encontrado na página")
    return best


def normalize(groups: list[dict], *, today: Optional[dt.date] = None) -> dict:
    """Grupos brutos da SVRS → estrutura do classtrib.json."""
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
            dfe = sorted(label for ind, label in DFE_INDICATORS.items() if c.get(ind))
            by_code[code] = {
                "cst": cst,
                "cst_description": nome_cst,
                "description": (c.get("NomeClassTrib") or "").strip(),
                "reduction_ibs_pct": float(c.get("PercRedIbs") or 0.0),
                "reduction_cbs_pct": float(c.get("PercRedCbs") or 0.0),
                "tipo_aliquota": c.get("TipoAliq"),
                # Crédito presumido IBS/CBS: se True, a operação pode carregar a tag
                # cCredPres (#339). Só alguns cClassTrib permitem — fonte SVRS:
                # IndPermiteCredPres.
                "permite_cred_pres": bool(c.get("IndPermiteCredPres")),
                # Subgrupos do UB84 (gIBSCBSMono) exigidos pelo cClassTrib — NT
                # 2025.002 v1.50, regime monofásico (#404). Fonte SVRS:
                # IndMonoRetem/IndMonoRet/IndMonoDif.
                "mono_retencao": bool(c.get("IndMonoRetem")),
                "mono_retido_anteriormente": bool(c.get("IndMonoRet")),
                "mono_diferimento": bool(c.get("IndMonoDif")),
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
            "date": (today or dt.date.today()).isoformat(),
            "total_codes": len(by_code),
            "total_cst_groups": len(cst_descriptions),
        },
        "by_code": dict(sorted(by_code.items())),
        "by_cst": dict(sorted(by_cst.items())),
        "cst_descriptions": dict(sorted(cst_descriptions.items())),
    }


def data_signature(d: dict, keys: tuple[str, ...] = CODE_KEYS) -> str:
    """Hash estável do CONTEÚDO (ignorando ``meta``).

    Cobre atributos, não só a lista de códigos: mudança de alíquota, de descrição
    ou de indicador em um código existente altera a assinatura. É o que impede
    uma edição in-place de passar por "sem mudança".
    """
    payload = {k: d.get(k) for k in keys}
    return hashlib.md5(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def codes_of(d: dict) -> set[str]:
    """Conjunto de cClassTrib de uma estrutura normalizada — para o diff legível."""
    return set((d.get("by_code") or {}).keys())
