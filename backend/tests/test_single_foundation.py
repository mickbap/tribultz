"""INV-3 — SINGLE HANDOFF FOUNDATION (Round 8 §13, DEC-9).

Existe exatamente UMA implementação ativa para persistência, identidade,
contrato, ownership, suppression e processamento do handoff comercial.
Duplicação aqui é pior que bug comum: duas implementações individualmente
corretas produzem estados incompatíveis.

Também caça resíduos da linha descartada (feat/commercial-handoff-f1-f3):
migration concorrente com a MESMA revision, tabelas commercial_*, segunda
família de models/serviços. Qualquer referência inesperada quebra este teste.
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
APP = BACKEND / "app"
VERSIONS = APP / "alembic" / "versions"

DISCARDED_TABLES = (
    "commercial_persons",
    "commercial_person_identities",
    "commercial_leads",
    "commercial_lead_events",
)
DISCARDED_PATHS = ("services/commercial", "models/commercial", "schemas/handoff")


def _py_files(root: Path):
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def test_revision_0037_existe_exatamente_uma_vez():
    """Gate Alembic §4: 1 revision id, 0 duplicada — ataque explícito à 0037."""
    hits = []
    for f in VERSIONS.glob("*.py"):
        if re.search(r'^revision\s*=\s*"2026_08_12_0037"', f.read_text(), re.M):
            hits.append(f.name)
    assert hits == ["2026_08_12_0037_add_crm_handoff_foundations.py"], (
        f"revision 2026_08_12_0037 em arquivos inesperados: {hits}"
    )


def test_um_unico_head_alembic():
    """Gate Alembic §4: 1 caminho válido, 1 head esperado."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["2026_08_12_0037"], f"heads inesperados: {heads}"


def test_zero_referencias_as_tabelas_descartadas():
    """Busca estática do §12 pelos nomes das tabelas da implementação descartada."""
    offenders = []
    for f in _py_files(BACKEND):
        if f.name == Path(__file__).name:
            continue  # este arquivo cita os nomes para caçá-los
        text = f.read_text()
        for table in DISCARDED_TABLES:
            if table in text:
                offenders.append(f"{f.relative_to(BACKEND)}: {table}")
    assert offenders == [], "resíduos da linha descartada:\n" + "\n".join(offenders)


def test_zero_modulos_da_linha_descartada():
    for rel in DISCARDED_PATHS:
        assert not (APP / rel).exists() and not (APP / f"{rel}.py").exists(), (
            f"módulo da linha descartada presente: app/{rel}"
        )


def _count_definitions(pattern: str) -> list[str]:
    hits = []
    for f in _py_files(APP):
        for _ in re.finditer(pattern, f.read_text(), re.M):
            hits.append(str(f.relative_to(BACKEND)))
    return hits


def test_uma_unica_maquina_de_estados_e_um_unico_contrato():
    """Uma enum de ownership, uma de automation, um contrato de handoff."""
    ownership = _count_definitions(r"^class OwnershipState\b")
    automation = _count_definitions(r"^class AutomationState\b")
    contract = _count_definitions(r"^class HandoffEvent\b")
    capability = _count_definitions(r"^class ProviderCapability\b")
    assert ownership == ["app/services/handoff/ownership.py"], ownership
    assert automation == ["app/services/handoff/ownership.py"], automation
    assert contract == ["app/services/handoff/contract.py"], contract
    assert capability == ["app/services/handoff/capability.py"], capability


def test_uma_unica_tabela_por_conceito():
    """Os models canônicos existem uma vez; nenhum model paralelo do conceito."""
    tablenames = []
    for f in _py_files(APP / "models"):
        tablenames += re.findall(r'__tablename__\s*=\s*"([a-z_]+)"', f.read_text())
    for canonical in (
        "crm_person_identities",
        "crm_lead_links",
        "crm_lead_events",
        "crm_state_transitions",
    ):
        assert tablenames.count(canonical) == 1, f"{canonical}: {tablenames.count(canonical)}x"
    for discarded in DISCARDED_TABLES:
        assert discarded not in tablenames
