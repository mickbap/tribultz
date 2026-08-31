"""Modificador de alíquota por NCM — derivado da fonte, não do capítulo.

Decisão fiscal do ROUND CORE 30/08-R (issue #685), opção **C**:

1. NCM com lastro **unânime** na fonte → devolve o valor único sustentado.
2. NCM cujos cClassTrib sustentam tratamentos **diferentes** → ``nao_determinavel``.
3. NCM **sem lastro** → ``nao_determinavel``.

O que este módulo deixou de fazer, e por quê: derivava o modificador do
**capítulo NCM (2 dígitos)** a partir de uma tabela escrita à mão. Um capítulo
agrupa mercadorias com tratamentos distintos — 19 dos 24 capítulos divergiam da
fonte, seis NCMs recebiam imposto **zerado** onde a fonte só sustenta 60%, e um
capítulo aplicava modificador sem lastro algum. A heurística não foi trocada por
outra: onde a fonte não é unânime, não há valor.

Fonte: ``ncm_cclasstrib.json`` (NCM → cClassTrib) + ``classtrib.json``
(cClassTrib → percentual de redução de IBS e CBS).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.data.classtrib_table import CLASSTRIB_BY_CODE
from app.data.ncm_cclasstrib_table import ncm_candidatos


@dataclass(frozen=True)
class NcmModifier:
    """Resultado da resolução do modificador de um NCM.

    ``modifier is None`` significa ``nao_determinavel`` — e nunca deve ser
    substituído por um valor padrão pelo chamador. Ausência de determinação é
    informação, não lacuna a preencher.
    """

    modifier: Decimal | None
    unanime: bool
    fontes: tuple[str, ...]
    motivo: str | None = None

    @property
    def nao_determinavel(self) -> bool:
        return self.modifier is None


_CEM = Decimal("100")


def _modificador_do_codigo(codigo: str) -> tuple[Decimal, Decimal] | None:
    """(mod_ibs, mod_cbs) do cClassTrib. ``60%`` de redução → ``0.4``."""
    item = CLASSTRIB_BY_CODE.get(codigo)
    if item is None:
        return None
    ibs = Decimal(str(item.get("reduction_ibs_pct", 0.0)))
    cbs = Decimal(str(item.get("reduction_cbs_pct", 0.0)))
    return (Decimal("1") - ibs / _CEM, Decimal("1") - cbs / _CEM)


def resolve_ncm_modifier(ncm: str | None) -> NcmModifier:
    """Modificador sustentado pela fonte para o NCM, ou ``nao_determinavel``."""
    if not ncm:
        return NcmModifier(None, False, (), "NCM não informado")

    entradas = ncm_candidatos(ncm)
    if not entradas:
        return NcmModifier(None, False, (), "NCM sem cClassTrib de lastro na fonte")

    fontes = tuple(sorted({e["codigo"] for e in entradas}))
    pares: set[tuple[Decimal, Decimal]] = set()
    for codigo in fontes:
        par = _modificador_do_codigo(codigo)
        if par is None:
            return NcmModifier(
                None, False, fontes,
                f"cClassTrib {codigo} citado para o NCM não consta da tabela oficial",
            )
        pares.add(par)

    if len(pares) > 1:
        return NcmModifier(
            None, False, fontes,
            "cClassTrib vinculados ao NCM sustentam tratamentos diferentes; "
            "a escolha depende do contexto da operação, que não é recebido aqui",
        )

    (mod_ibs, mod_cbs), = pares
    if mod_ibs != mod_cbs:
        # Nenhum NCM de 8 dígitos cai aqui hoje, mas um único valor não
        # representaria dois tratamentos — e inventar qual vale é heurística.
        return NcmModifier(
            None, False, fontes,
            "o tratamento sustentado difere entre IBS e CBS e não cabe em um modificador único",
        )
    return NcmModifier(mod_ibs, True, fontes)
