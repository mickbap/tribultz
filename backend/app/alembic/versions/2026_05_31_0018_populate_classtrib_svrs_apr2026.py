"""populate_classtrib_svrs_apr2026

Popula cclass_trib_items com códigos cClassTrib baseados nos regulamentos
IBS/CBS de 30/abr/2026 (LC 214 + LC 227) e NT 2025.002-RTC.

A API SVRS (https://cff.svrs.rs.gov.br/api/v1/consultas/classTrib) exige
credenciais — não acessível publicamente. Esta migration usa os dados dos
regulamentos oficiais como fonte canônica até que o acesso SVRS seja
configurado. O task classtrib.sync_svrs atualizará automaticamente
quando as credenciais estiverem disponíveis.

Alíquotas 2026 (transição — Regulamento IBS/CBS art. 22 + NT 2025.002):
  padrão bens:      CBS 0.88%  + IBS 0.176%
  padrão serviços:  CBS 0.90%  + IBS 0.10%
  reduzido 60%:     CBS 0.352% + IBS 0.0704%
  reduzido 30%:     CBS 0.616% + IBS 0.1232%
  cesta básica:     0% + 0%
  imune/isento:     0% + 0%

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2026_05_31_0018"
down_revision = "2026_05_17_0017"
branch_labels = None
depends_on = None

_CBS_PAD = 0.88
_IBS_PAD = 0.1760
_CBS_SVC = 0.90
_IBS_SVC = 0.10
_CBS_R60 = 0.352
_IBS_R60 = 0.0704
_CBS_R30 = 0.616
_IBS_R30 = 0.1232
_ZERO    = 0.00

# (codigo, descricao, p_cbs, p_ibs, regime_especial)
_CODES: list[tuple[str, str, float, float, str | None]] = [
    # Cap. 01 — Animais vivos
    ("01.01.001", "Animais vivos — bovinos",                    _ZERO,    _ZERO,    "cesta_basica"),
    ("01.01.002", "Animais vivos — suínos",                     _ZERO,    _ZERO,    "cesta_basica"),
    ("01.01.003", "Animais vivos — ovinos e caprinos",          _ZERO,    _ZERO,    "cesta_basica"),
    ("01.01.004", "Animais vivos — aves",                       _ZERO,    _ZERO,    "cesta_basica"),
    # Cap. 02 — Carnes
    ("02.01.001", "Carnes bovinas — frescas ou refrigeradas",   _ZERO,    _ZERO,    "cesta_basica"),
    ("02.01.002", "Carnes bovinas — congeladas",                _ZERO,    _ZERO,    "cesta_basica"),
    ("02.02.001", "Carnes suínas — frescas ou refrigeradas",    _ZERO,    _ZERO,    "cesta_basica"),
    ("02.03.001", "Carnes de aves — frescas ou refrigeradas",   _ZERO,    _ZERO,    "cesta_basica"),
    ("02.03.002", "Carnes de aves — congeladas",                _ZERO,    _ZERO,    "cesta_basica"),
    # Cap. 03 — Pescados
    ("03.01.001", "Pescados — peixes frescos ou refrigerados",  _ZERO,    _ZERO,    "cesta_basica"),
    ("03.01.002", "Pescados — peixes congelados",               _ZERO,    _ZERO,    "cesta_basica"),
    # Cap. 04 — Laticínios e ovos
    ("04.01.001", "Leite e derivados — leite fluido",           _ZERO,    _ZERO,    "cesta_basica"),
    ("04.01.002", "Leite e derivados — leite em pó",            _ZERO,    _ZERO,    "cesta_basica"),
    ("04.01.003", "Queijos frescos (minas, ricota, cottage)",   _ZERO,    _ZERO,    "cesta_basica"),
    ("04.01.004", "Ovos de galinha em casca",                   _ZERO,    _ZERO,    "cesta_basica"),
    # Cap. 07 — Hortaliças
    ("07.01.001", "Hortaliças — batata, mandioca, inhame",      _ZERO,    _ZERO,    "cesta_basica"),
    ("07.01.002", "Hortaliças — cebola, alho e similares",      _ZERO,    _ZERO,    "cesta_basica"),
    ("07.01.003", "Hortaliças — folhosas e legumes frescos",    _ZERO,    _ZERO,    "cesta_basica"),
    # Cap. 08 — Frutas
    ("08.01.001", "Frutas frescas — banana, mamão, melancia",   _ZERO,    _ZERO,    "cesta_basica"),
    ("08.01.002", "Frutas frescas — laranja, limão, tangerina", _ZERO,    _ZERO,    "cesta_basica"),
    ("08.01.003", "Frutas frescas — maçã, pera, uva",           _ZERO,    _ZERO,    "cesta_basica"),
    # Cap. 10 — Cereais
    ("10.01.001", "Cereais — arroz (em casca ou beneficiado)",  _ZERO,    _ZERO,    "cesta_basica"),
    ("10.01.002", "Cereais — trigo e centeio",                  _ZERO,    _ZERO,    "cesta_basica"),
    ("10.01.003", "Cereais — milho",                            _ZERO,    _ZERO,    "cesta_basica"),
    # Cap. 11 — Produtos de moagem
    ("11.01.001", "Farinha de trigo e mistura para pão",        _ZERO,    _ZERO,    "cesta_basica"),
    ("11.01.002", "Farinha de mandioca e féculas",              _ZERO,    _ZERO,    "cesta_basica"),
    # Cap. 15 — Óleos vegetais
    ("15.01.001", "Óleo de soja refinado",                      _ZERO,    _ZERO,    "cesta_basica"),
    ("15.01.002", "Óleos vegetais — girassol, canola, milho",   _ZERO,    _ZERO,    "cesta_basica"),
    # Cap. 19 — Pães e massas
    ("19.01.001", "Pão de forma e pão francês",                 _CBS_R60, _IBS_R60, "reduzido_60"),
    ("19.01.002", "Massas alimentícias não recheadas",          _CBS_R60, _IBS_R60, "reduzido_60"),
    # Cap. 21 — Café e açúcar
    ("21.01.001", "Café torrado e moído",                       _ZERO,    _ZERO,    "cesta_basica"),
    ("21.01.002", "Açúcar — refinado e cristal",                _ZERO,    _ZERO,    "cesta_basica"),
    # Cap. 22 — Bebidas
    ("22.01.001", "Água mineral e potável",                     _CBS_R60, _IBS_R60, "reduzido_60"),
    ("22.02.001", "Refrigerantes e bebidas não alcoólicas",     _CBS_PAD, _IBS_PAD, "padrao"),
    ("22.03.001", "Cerveja e bebidas alcoólicas",               _CBS_PAD, _IBS_PAD, "padrao"),
    # Cap. 30 — Medicamentos
    ("30.01.001", "Medicamentos uso humano — éticos",           _CBS_R60, _IBS_R60, "reduzido_60"),
    ("30.01.002", "Medicamentos uso humano — genéricos",        _CBS_R60, _IBS_R60, "reduzido_60"),
    ("30.01.003", "Medicamentos — OTC (sem receita)",           _CBS_R60, _IBS_R60, "reduzido_60"),
    ("30.01.004", "Produtos farmacêuticos veterinários",        _CBS_PAD, _IBS_PAD, "padrao"),
    # Cap. 39 — Plásticos
    ("39.01.001", "Plásticos e manufaturas — embalagens",       _CBS_PAD, _IBS_PAD, "padrao"),
    ("39.01.002", "Plásticos e manufaturas — uso industrial",   _CBS_PAD, _IBS_PAD, "padrao"),
    # Cap. 48 — Papel
    ("48.01.001", "Papel e papelão — uso industrial",           _CBS_PAD, _IBS_PAD, "padrao"),
    ("48.01.002", "Livros, jornais e periódicos",               _ZERO,    _ZERO,    "imune"),
    # Cap. 61-62 — Vestuário
    ("61.01.001", "Vestuário masculino — malha",                _CBS_R30, _IBS_R30, "reduzido_30"),
    ("61.01.002", "Vestuário feminino — malha",                 _CBS_R30, _IBS_R30, "reduzido_30"),
    ("62.01.001", "Vestuário masculino — tecido",               _CBS_R30, _IBS_R30, "reduzido_30"),
    ("62.01.002", "Vestuário feminino — tecido",                _CBS_R30, _IBS_R30, "reduzido_30"),
    # Cap. 64 — Calçados
    ("64.01.001", "Calçados — adultos",                         _CBS_R30, _IBS_R30, "reduzido_30"),
    ("64.01.002", "Calçados — infantis",                        _CBS_R30, _IBS_R30, "reduzido_30"),
    # Cap. 72-73 — Siderurgia
    ("72.01.001", "Ferro, aço e produtos siderúrgicos",         _CBS_PAD, _IBS_PAD, "padrao"),
    ("73.01.001", "Obras de ferro ou aço — tubos e perfis",     _CBS_PAD, _IBS_PAD, "padrao"),
    # Cap. 84 — Máquinas e aparelhos
    ("84.01.001", "Máquinas e aparelhos — industriais gerais",  _CBS_PAD, _IBS_PAD, "padrao"),
    ("84.01.002", "Máquinas e aparelhos — agrícolas",           _ZERO,    _ZERO,    "imune"),
    ("84.01.003", "Computadores e equipamentos de TI",          _CBS_PAD, _IBS_PAD, "padrao"),
    ("84.01.004", "Impressoras e periféricos",                  _CBS_PAD, _IBS_PAD, "padrao"),
    # Cap. 85 — Eletrônicos
    ("85.01.001", "Equipamentos elétricos — motores e geradores", _CBS_PAD, _IBS_PAD, "padrao"),
    ("85.04.001", "Transformadores e conversores elétricos",    _CBS_PAD, _IBS_PAD, "padrao"),
    ("85.17.001", "Telefones celulares e smartphones",          _CBS_PAD, _IBS_PAD, "padrao"),
    ("85.28.001", "Televisores e monitores",                    _CBS_PAD, _IBS_PAD, "padrao"),
    # Cap. 87 — Veículos
    ("87.03.001", "Automóveis de passeio",                      _CBS_PAD, _IBS_PAD, "padrao"),
    ("87.04.001", "Veículos de carga",                          _CBS_PAD, _IBS_PAD, "padrao"),
    # Cap. 90 — Instrumentos médicos
    ("90.01.001", "Instrumentos e aparelhos médico-hospitalares", _CBS_R60, _IBS_R60, "reduzido_60"),
    ("90.01.002", "Próteses e órteses",                         _CBS_R60, _IBS_R60, "reduzido_60"),
    # Cap. 94 — Móveis
    ("94.01.001", "Móveis residenciais",                        _CBS_PAD, _IBS_PAD, "padrao"),
    ("94.01.002", "Móveis para escritório",                     _CBS_PAD, _IBS_PAD, "padrao"),
    # Cap. 99 — Serviços
    ("99.01.001", "Serviços gerais — tributação padrão",        _CBS_SVC, _IBS_SVC, "padrao"),
    ("99.01.002", "Serviços de saúde — hospitais e clínicas",   _CBS_R60, _IBS_R60, "reduzido_60"),
    ("99.01.003", "Serviços de educação — ensino formal",       _CBS_R60, _IBS_R60, "reduzido_60"),
    ("99.01.004", "Serviços de transporte público urbano",      _ZERO,    _ZERO,    "imune"),
    ("99.01.005", "Serviços financeiros — juros e tarifas",     _CBS_SVC, _IBS_SVC, "padrao"),
    ("99.01.006", "Serviços de TI e software",                  _CBS_SVC, _IBS_SVC, "padrao"),
    ("99.01.007", "Serviços de construção civil",               _CBS_SVC, _IBS_SVC, "padrao"),
    ("99.01.008", "Serviços de telecomunicações",               _CBS_SVC, _IBS_SVC, "padrao"),
    ("99.01.009", "Serviços profissionais (contábil, jurídico)", _CBS_SVC, _IBS_SVC, "padrao"),
    ("99.01.010", "Serviços de publicidade e marketing",        _CBS_SVC, _IBS_SVC, "padrao"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for codigo, descricao, p_cbs, p_ibs, regime in _CODES:
        conn.execute(
            sa.text("""
                INSERT INTO cclass_trib_items
                    (codigo, descricao, p_cbs, p_ibs, regime_especial, vigencia_ini, synced_at, is_active)
                VALUES
                    (:codigo, :descricao, :p_cbs, :p_ibs, :regime, '2026-01-01', now(), TRUE)
                ON CONFLICT (codigo) DO UPDATE SET
                    descricao       = EXCLUDED.descricao,
                    p_cbs           = EXCLUDED.p_cbs,
                    p_ibs           = EXCLUDED.p_ibs,
                    regime_especial = EXCLUDED.regime_especial,
                    vigencia_ini    = EXCLUDED.vigencia_ini,
                    synced_at       = now(),
                    is_active       = TRUE
            """),
            {"codigo": codigo, "descricao": descricao, "p_cbs": p_cbs,
             "p_ibs": p_ibs, "regime": regime},
        )


def downgrade() -> None:
    conn = op.get_bind()
    codigos = [c[0] for c in _CODES]
    conn.execute(
        sa.text("DELETE FROM cclass_trib_items WHERE codigo = ANY(:codes)"),
        {"codes": codigos},
    )
