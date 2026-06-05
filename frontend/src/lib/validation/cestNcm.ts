/**
 * NCM → ST (Substituição Tributária) lookup.
 *
 * Source: Convênio ICMS 142/2018 (CONFAZ) + alterações até 2026.
 *
 * Mirror of `backend/app/data/cest_ncm.py`. Keep in sync when updating.
 */

export const CEST_DATA_VERSION = "2026-06-05";
export const CEST_DATA_SOURCE = "Convênio ICMS 142/2018 (CONFAZ) — subset curado";

export const ST_NCM_PREFIXES: Record<string, string[]> = {
  bebidas_alcoolicas: ["2203", "2204", "2205", "2206", "2208"],
  bebidas_nao_alcoolicas: ["2201", "2202"],
  fumo: ["2402", "2403"],
  combustiveis_lubrificantes: ["2710", "2711", "2713"],
  cimento_e_construcao: ["2523", "3214", "3208", "3209", "3210", "6802", "6810"],
  pneus_e_camaras: ["4011", "4012", "4013"],
  veiculos_automotores: ["8701", "8702", "8703", "8704", "8711"],
  autopecas: [
    "4009", "4016", "7007", "7009", "8407", "8408", "8409", "8413",
    "8415", "8421", "8482", "8483", "8507", "8511", "8512", "8527",
    "8536", "8544", "8708", "8714", "9026", "9029", "9032",
  ],
  sorvetes: ["2105"],
  produtos_alimenticios_industrializados: [
    "1601", "1602", "1704", "1806", "1905",
    "2007", "2009", "2103", "2104", "2106",
  ],
  ferramentas: ["8201", "8202", "8203", "8204", "8205", "8207", "8211"],
  material_eletrico: ["8504", "8516", "8517", "8528", "8539", "8544.49"],
  cosmeticos_perfumaria_higiene: [
    "3303", "3304", "3305", "3306", "3307",
    "3401", "3402", "9603.21",
  ],
  medicamentos: ["3003", "3004", "3005", "3006"],
};

export type NcmStLookup = {
  ncm: string;
  is_st: boolean;
  matched_prefix: string | null;
  segments: string[];
  source: string;
  data_version: string;
};

function normalizeNcm(ncm: string): string {
  return (ncm ?? "").replace(/\D/g, "");
}

export function lookupNcmSt(ncm: string): NcmStLookup {
  const norm = normalizeNcm(ncm);
  if (!norm) {
    return {
      ncm,
      is_st: false,
      matched_prefix: null,
      segments: [],
      source: CEST_DATA_SOURCE,
      data_version: CEST_DATA_VERSION,
    };
  }

  const matched: Array<{ prefix: string; segment: string }> = [];
  for (const [segment, prefixes] of Object.entries(ST_NCM_PREFIXES)) {
    for (const prefix of prefixes) {
      if (norm.startsWith(normalizeNcm(prefix))) {
        matched.push({ prefix, segment });
      }
    }
  }

  if (matched.length === 0) {
    return {
      ncm: norm,
      is_st: false,
      matched_prefix: null,
      segments: [],
      source: CEST_DATA_SOURCE,
      data_version: CEST_DATA_VERSION,
    };
  }

  matched.sort((a, b) => normalizeNcm(b.prefix).length - normalizeNcm(a.prefix).length);
  const bestPrefix = matched[0].prefix;
  const segments = Array.from(new Set(matched.map((m) => m.segment))).sort();

  return {
    ncm: norm,
    is_st: true,
    matched_prefix: bestPrefix,
    segments,
    source: CEST_DATA_SOURCE,
    data_version: CEST_DATA_VERSION,
  };
}

export function isStNcm(ncm: string): boolean {
  return lookupNcmSt(ncm).is_st;
}
