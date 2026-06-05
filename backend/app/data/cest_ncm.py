"""NCM → ST (Substituição Tributária) lookup.

**Fonte:** Convênio ICMS 142/2018 (CONFAZ) + alterações até 2026.

Este módulo entrega um **subset curado** dos NCMs com maior volume de NF-e
sujeitos a substituição tributária no Brasil, organizados por segmento.

Para cada NCM declarado em uma NF-e, o lookup verifica se o prefixo está em
qualquer segmento ST conhecido. Se sim, o produto **deve** declarar `<CEST>`
(LC 214 + Regulamento IBS/CBS de 30/abr/2026 mantém vinculação ST↔CEST).

## Limitações conhecidas

- Subset cobre os ~12 segmentos de maior volume; entradas raras do Conv. 142
  podem não estar listadas. NCMs ausentes são tratados como **possivelmente
  ST** (severidade `ALERT`, não `FATAL`).
- Seed completo dos ~1300 NCMs do Conv. 142 fica pendente como issue de
  expansão. Quando feito, virar para tabela DB + endpoint integrado SVRS.

## Como atualizar

1. Baixar a versão mais recente do Convênio 142 e seus anexos (CONFAZ).
2. Adicionar prefixos novos ao `ST_NCM_PREFIXES` por segmento.
3. Bumpar `CEST_DATA_VERSION`.
4. Atualizar `frontend/src/lib/validation/cestNcm.ts` (mesmo conteúdo).
"""

from __future__ import annotations

CEST_DATA_VERSION = "2026-06-05"
CEST_DATA_SOURCE = "Convênio ICMS 142/2018 (CONFAZ) — subset curado"

# Mapeamento segmento → lista de prefixos NCM (string variável, ex: "2202", "8714.10").
# Match é por prefixo: NCM do XML "comeca com" qualquer prefixo listado.
ST_NCM_PREFIXES: dict[str, list[str]] = {
    "bebidas_alcoolicas": [
        "2203",      # cervejas
        "2204",      # vinhos
        "2205",      # vermutes
        "2206",      # outras bebidas fermentadas
        "2208",      # destilados (cachaça, vodka, whisky)
    ],
    "bebidas_nao_alcoolicas": [
        "2201",      # águas, gelo
        "2202",      # refrigerantes, isotônicos, energéticos
    ],
    "fumo": [
        "2402",      # charutos, cigarrilhas, cigarros
        "2403",      # outros produtos de fumo
    ],
    "combustiveis_lubrificantes": [
        # Predominantemente monofásico CBS/IBS (CST 620), mas ST de ICMS mantida na transição
        "2710",      # óleos de petróleo (gasolina, diesel, querosene, lubrificantes)
        "2711",      # GLP, GNV
        "2713",      # coque de petróleo
    ],
    "cimento_e_construcao": [
        "2523",      # cimento
        "3214",      # massa para vidraceiro, rejunte
        "3208", "3209", "3210",   # tintas e vernizes
        "6802",      # pedras para construção
        "6810",      # artefatos de cimento, concreto
    ],
    "pneus_e_camaras": [
        "4011",      # pneus novos
        "4012",      # pneus recauchutados
        "4013",      # câmaras de ar
    ],
    "veiculos_automotores": [
        "8701",      # tratores
        "8702",      # ônibus
        "8703",      # automóveis de passageiros
        "8704",      # veículos para transporte de mercadorias
        "8711",      # motocicletas
    ],
    "autopecas": [
        "4009",      # tubos, mangueiras de borracha
        "4016",      # outras obras de borracha
        "7007",      # vidros temperados/laminados (vidros automotivos)
        "7009",      # espelhos retrovisores
        "8407", "8408",   # motores
        "8409",      # partes de motores
        "8413",      # bombas
        "8415",      # ar-condicionado
        "8421",      # filtros
        "8482",      # rolamentos
        "8483",      # eixos, engrenagens
        "8507",      # acumuladores (baterias)
        "8511",      # ignição
        "8512",      # iluminação automotiva
        "8527",      # rádios
        "8536",      # disjuntores, conectores
        "8544",      # chicotes elétricos
        "8708",      # partes e acessórios de veículos
        "8714",      # partes de motocicletas
        "9026", "9029",   # instrumentos automotivos
        "9032",      # reguladores
    ],
    "sorvetes": [
        "2105",      # sorvetes e congelados
    ],
    "produtos_alimenticios_industrializados": [
        # Subset — não todos. Lista CONFAZ tem ~150 itens.
        "1601",      # embutidos
        "1602",      # outras preparações de carne
        "1704",      # balas, chicletes
        "1806",      # chocolates
        "1905",      # biscoitos, bolachas
        "2007",      # geleias, doces de fruta
        "2009",      # sucos de fruta
        "2103",      # molhos, condimentos
        "2104",      # caldos, sopas
        "2106",      # preparações alimentícias diversas (achocolatado, etc)
    ],
    "ferramentas": [
        "8201",      # ferramentas manuais agrícolas
        "8202",      # serras
        "8203",      # limas, alicates
        "8204",      # chaves de porca
        "8205",      # ferramentas manuais
        "8207",      # ferramentas intercambiáveis
        "8211",      # facas
    ],
    "material_eletrico": [
        "8504",      # transformadores
        "8516",      # aquecedores, ferros de passar
        "8517",      # telefones, modems
        "8528",      # TVs, monitores
        "8539",      # lâmpadas
        "8544.49",   # fios e cabos elétricos comuns
    ],
    "cosmeticos_perfumaria_higiene": [
        "3303",      # perfumes
        "3304",      # maquiagem
        "3305",      # cosméticos capilares
        "3306",      # higiene bucal
        "3307",      # desodorantes, depilatórios
        "3401",      # sabões
        "3402",      # detergentes
        "9603.21",   # escovas de dente
    ],
    "medicamentos": [
        "3003",      # medicamentos a granel
        "3004",      # medicamentos em dose
        "3005",      # algodão, gaze, ataduras
        "3006",      # preparações farmacêuticas
    ],
}

# Set "plano" para lookup O(1) por prefixo
_FLAT_ST_PREFIXES: set[str] = {
    prefix
    for prefixes in ST_NCM_PREFIXES.values()
    for prefix in prefixes
}


def _normalize_ncm(ncm: str) -> str:
    """Remove pontos, espaços; mantém só dígitos."""
    return "".join(c for c in (ncm or "") if c.isdigit())


def lookup_ncm_st(ncm: str) -> dict:
    """Determina se o NCM está sujeito a Substituição Tributária.

    Returns:
        {
          "ncm": "22021000",
          "is_st": True,
          "matched_prefix": "2202",
          "segments": ["bebidas_nao_alcoolicas"],
          "source": "...",
          "data_version": "...",
        }
    """
    norm = _normalize_ncm(ncm)
    if not norm:
        return {
            "ncm": ncm,
            "is_st": False,
            "matched_prefix": None,
            "segments": [],
            "source": CEST_DATA_SOURCE,
            "data_version": CEST_DATA_VERSION,
        }

    matched: list[tuple[str, str]] = []  # [(prefix, segment)]
    for segment, prefixes in ST_NCM_PREFIXES.items():
        for prefix in prefixes:
            clean_prefix = _normalize_ncm(prefix)
            if norm.startswith(clean_prefix):
                matched.append((prefix, segment))

    if not matched:
        return {
            "ncm": norm,
            "is_st": False,
            "matched_prefix": None,
            "segments": [],
            "source": CEST_DATA_SOURCE,
            "data_version": CEST_DATA_VERSION,
        }

    # Pega o prefixo mais específico (maior comprimento)
    matched.sort(key=lambda t: len(_normalize_ncm(t[0])), reverse=True)
    best_prefix, _ = matched[0]
    segments = sorted({seg for _, seg in matched})

    return {
        "ncm": norm,
        "is_st": True,
        "matched_prefix": best_prefix,
        "segments": segments,
        "source": CEST_DATA_SOURCE,
        "data_version": CEST_DATA_VERSION,
    }


def is_st_ncm(ncm: str) -> bool:
    """Retorna True se o NCM tem prefixo conhecido como ST. Wrapper conveniente."""
    return lookup_ncm_st(ncm).get("is_st", False)
