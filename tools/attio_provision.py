#!/usr/bin/env python3
"""Provisionamento controlado do workspace Attio — F4 (Round 6, PO-2026-07-CRM-001).

Fases (todas idempotentes, GET-before-POST):
  snapshot   — baseline somente-leitura (objects/lists/attrs/webhooks) em JSON
  provision  — P1 list de leads · P2 attrs de companies · P3 régua do deals
  verify     — contract-test: workspace real × especificação (gate técnico §4)
  smoke      — entidades 100%% sintéticas [SINTÉTICO-QA]: company SEM domínio,
               person vinculada por record_id, entry na list, prova de que Deal
               só nasce por ato humano; grava state file p/ cleanup
  cleanup    — remove TODAS as entidades sintéticas do state file + confere resíduo

Salvaguardas: aborta antes da primeira escrita se o workspace não for o esperado
(6tech); escrita exige --execute (default = dry-run); nenhum lead real é tocado;
o webhook (P5) NÃO é criado aqui — o secret precisa nascer e morrer na VM (ver
runbook do Round 6). A key é lida de --env-file e jamais impressa.

Uso:
  python tools/attio_provision.py --env-file ../.env.prod snapshot
  python tools/attio_provision.py --env-file ../.env.prod provision --execute
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.attio.com/v2"
EXPECTED_WORKSPACE_ID = "39886476-4a55-413a-9373-e3337c7f69f6"  # 6tech
EXPECTED_WORKSPACE_NAME = "6tech"

LIST_SLUG = "leads_comerciais"
LIST_NAME = "Leads Comerciais"
LEAD_STATUSES = [
    "Prospecção Automatizada", "Resposta Recebida", "Discovery",
    "Qualificado", "Nurture", "Perdido",
]
OWNERSHIP_OPTIONS = ["AUTOMATED", "HANDOFF_REQUESTED", "HUMAN_OWNED", "RELEASED", "CLOSED"]
SOURCE_OPTIONS = ["rumy", "manual", "outro"]
LIST_ATTRS = [
    # (title, api_slug, type, is_unique)
    ("Status", "status", "status", False),
    ("Ownership (espelho)", "ownership_state", "select", False),
    ("Source", "source_system", "select", False),
    ("Campanha", "campaign_id", "text", False),
    ("External Lead ID", "external_lead_id", "text", False),
    ("Handoff solicitado em", "handoff_requested_at", "timestamp", False),
    ("Handoff aceito em", "handoff_accepted_at", "timestamp", False),
    ("Owner", "owner", "actor-reference", False),
]
# DELTA-3 (Round 6): a API recusa is_unique em atributo custom ("Cannot set
# attribute as unique") — unicidade de CNPJ é garantida pelo NOSSO lado via
# query-before-create (comportamento existente de companies.py) + reconciliação.
COMPANY_ATTRS = [
    ("CNPJ", "cnpj", "text", False),
    ("Razão Social", "razao_social", "text", False),
    ("CNAE Principal", "cnae_principal", "text", False),
    ("Porte", "porte", "text", False),
    ("Situação Cadastral", "situacao_cadastral", "text", False),
]
DEAL_STAGES = [
    "Qualificado", "Reunião Agendada", "TERA", "Proposta", "Negociação", "Ganho", "Perdido",
]
DEFAULT_DEAL_STAGES = {"Lead", "In Progress", "Won 🎉", "Lost"}

SYN = "[SINTÉTICO-QA]"
SYN_CNPJ = "11444777000161"  # CNPJ de teste clássico, formato válido, claramente não-real
# DELTA-4 (Round 6): o Attio valida e-mail e recusa TLD reservado ".test" —
# sintético usa example.com (domínio reservado IANA, indeliverável).
SYN_EMAIL = "sintetica.qa@example.com"
STATE_FILE = Path(__file__).with_name(".attio_smoke_state.json")

DELTAS: list[str] = []


def _load_key(env_file: Path) -> str:
    for line in env_file.read_text().splitlines():
        if line.startswith("ATTIO_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    sys.exit(f"ATTIO_API_KEY não encontrada em {env_file}")


class Api:
    def __init__(self, key: str):
        self.key = key

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(
            BASE + path,
            method=method,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:300]
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from e

    def get(self, path):
        return self.call("GET", path)

    def post(self, path, body):
        return self.call("POST", path, body)

    def patch(self, path, body):
        return self.call("PATCH", path, body)

    def delete(self, path):
        return self.call("DELETE", path)


def guard_workspace(api: Api) -> None:
    """Round 6 §2: dúvida sobre o workspace ⇒ parar ANTES da primeira escrita."""
    me = api.get("/self")
    wid, wname = me.get("workspace_id"), me.get("workspace_name")
    if wid != EXPECTED_WORKSPACE_ID or wname != EXPECTED_WORKSPACE_NAME:
        sys.exit(
            f"ABORTADO: workspace inesperado (id={wid} name={wname}); "
            f"esperado {EXPECTED_WORKSPACE_NAME}/{EXPECTED_WORKSPACE_ID}. Nenhuma escrita feita."
        )
    print(f"workspace confirmado: {wname} ({wid})")


# ── fases ────────────────────────────────────────────────────────────────────

def snapshot(api: Api, out: Path) -> dict:
    snap = {
        "self": {k: api.get("/self").get(k) for k in ("workspace_id", "workspace_name", "active")},
        "objects": [o["api_slug"] for o in api.get("/objects")["data"]],
        "lists": [
            {"api_slug": li.get("api_slug"), "name": li.get("name")}
            for li in api.get("/lists")["data"]
        ],
        "companies_attrs": [a["api_slug"] for a in api.get("/objects/companies/attributes")["data"]],
        "people_attrs": [a["api_slug"] for a in api.get("/objects/people/attributes")["data"]],
        "deal_stages": [s["title"] for s in api.get("/objects/deals/attributes/stage/statuses")["data"]],
        "webhooks": len(api.get("/webhooks")["data"]),
    }
    out.write_text(json.dumps(snap, indent=2, ensure_ascii=False))
    print(f"snapshot salvo em {out}")
    print(json.dumps(snap, indent=2, ensure_ascii=False))
    return snap


def _ensure(api, execute, done_msg, create_fn, exists: bool, label: str):
    if exists:
        print(f"  = {label}: já existe (idempotente, nada a fazer)")
        return
    if not execute:
        print(f"  ~ {label}: SERIA criado (dry-run)")
        return
    create_fn()
    print(f"  + {label}: {done_msg}")


def provision(api: Api, execute: bool) -> None:
    print(f"— P1: list '{LIST_SLUG}' ({'EXECUTANDO' if execute else 'dry-run'})")
    lists = {li.get("api_slug") for li in api.get("/lists")["data"]}
    _ensure(
        api, execute, "criada",
        lambda: api.post("/lists", {"data": {
            "name": LIST_NAME, "api_slug": LIST_SLUG, "parent_object": "people",
            "workspace_access": "full-access", "workspace_member_access": [],
        }}),
        LIST_SLUG in lists, f"list {LIST_SLUG}",
    )
    if LIST_SLUG in lists or execute:
        existing = {a["api_slug"] for a in api.get(f"/lists/{LIST_SLUG}/attributes")["data"]}
        for title, slug, typ, uniq in LIST_ATTRS:
            _ensure(
                api, execute, "criado",
                lambda t=title, s=slug, ty=typ, u=uniq: api.post(
                    f"/lists/{LIST_SLUG}/attributes",
                    {"data": {"title": t, "description": t, "api_slug": s, "type": ty,
                              "is_required": False, "is_unique": u, "is_multiselect": False,
                              "config": {}}},
                ),
                slug in existing, f"list attr {slug}:{typ}",
            )
        # statuses e options
        if execute or "status" in existing:
            have = {s["title"] for s in api.get(f"/lists/{LIST_SLUG}/attributes/status/statuses")["data"]} if (execute or "status" in existing) else set()
            for t in LEAD_STATUSES:
                _ensure(api, execute, "criado",
                        lambda tt=t: api.post(f"/lists/{LIST_SLUG}/attributes/status/statuses",
                                              {"data": {"title": tt}}),
                        t in have, f"status '{t}'")
        for attr, opts in (("ownership_state", OWNERSHIP_OPTIONS), ("source_system", SOURCE_OPTIONS)):
            if execute or attr in existing:
                have = {o["title"] for o in api.get(f"/lists/{LIST_SLUG}/attributes/{attr}/options")["data"]}
                for t in opts:
                    _ensure(api, execute, "criada",
                            lambda tt=t, a=attr: api.post(
                                f"/lists/{LIST_SLUG}/attributes/{a}/options", {"data": {"title": tt}}),
                            t in have, f"option {attr}='{t}'")

    print(f"— P2: custom attrs em companies ({'EXECUTANDO' if execute else 'dry-run'})")
    have_c = {a["api_slug"] for a in api.get("/objects/companies/attributes")["data"]}
    for title, slug, typ, uniq in COMPANY_ATTRS:
        _ensure(api, execute, "criado",
                lambda t=title, s=slug, ty=typ, u=uniq: api.post(
                    "/objects/companies/attributes",
                    {"data": {"title": t, "description": t, "api_slug": s, "type": ty,
                              "is_required": False, "is_unique": u, "is_multiselect": False,
                              "config": {}}}),
                slug in have_c, f"companies.{slug}:{typ}{'(unique)' if uniq else ''}")

    print(f"— P3: régua do deals.stage ({'EXECUTANDO' if execute else 'dry-run'})")
    stages = api.get("/objects/deals/attributes/stage/statuses")["data"]
    have_s = {s["title"] for s in stages}
    for t in DEAL_STAGES:
        _ensure(api, execute, "criado",
                lambda tt=t: api.post("/objects/deals/attributes/stage/statuses",
                                      {"data": {"title": tt}}),
                t in have_s, f"deal stage '{t}'")
    for s in stages:
        if s["title"] in DEFAULT_DEAL_STAGES and not s.get("is_archived"):
            sid = s["id"]["status_id"]
            if execute:
                try:
                    api.patch(f"/objects/deals/attributes/stage/statuses/{sid}",
                              {"data": {"is_archived": True}})
                    print(f"  + default '{s['title']}': arquivado")
                except RuntimeError as e:
                    DELTAS.append(f"P3: não foi possível arquivar stage default '{s['title']}': {e}")
                    print(f"  ! delta registrado: {DELTAS[-1]}")
            else:
                print(f"  ~ default '{s['title']}': SERIA arquivado (dry-run)")


def verify(api: Api) -> bool:
    """Contract-test do workspace (gate técnico §4). Verde = pronto pra ativação."""
    ok = True

    def check(cond, label):
        nonlocal ok
        print(f"  {'✓' if cond else '✗'} {label}")
        ok = ok and cond

    def safe_titles(path, key="title"):
        try:
            return {x[key] for x in api.get(path)["data"]}
        except RuntimeError:
            return set()

    lists = {li.get("api_slug") for li in api.get("/lists")["data"]}
    check(LIST_SLUG in lists, f"list {LIST_SLUG} existe")
    if LIST_SLUG in lists:
        attrs = {a["api_slug"]: a for a in api.get(f"/lists/{LIST_SLUG}/attributes")["data"]}
        for _, slug, typ, _u in LIST_ATTRS:
            check(slug in attrs and attrs[slug]["type"] == typ, f"list attr {slug}:{typ}")
        sts = safe_titles(f"/lists/{LIST_SLUG}/attributes/status/statuses")
        check(set(LEAD_STATUSES) <= sts, f"statuses da list ⊇ {len(LEAD_STATUSES)} esperados")
        opts = safe_titles(f"/lists/{LIST_SLUG}/attributes/ownership_state/options")
        check(set(OWNERSHIP_OPTIONS) <= opts, "options de ownership_state completas")
    cattrs = {a["api_slug"]: a for a in api.get("/objects/companies/attributes")["data"]}
    for _, slug, typ, _uniq in COMPANY_ATTRS:
        check(slug in cattrs and cattrs[slug]["type"] == typ, f"companies.{slug}:{typ}")
    print("  · DELTA-3: cnpj sem is_unique (API recusa em custom) — dedupe por "
          "query-before-create do nosso lado")
    dstages = {s["title"] for s in api.get("/objects/deals/attributes/stage/statuses")["data"]
               if not s.get("is_archived")}
    check(set(DEAL_STAGES) <= dstages, "régua do deals ⊇ 7 estágios da máquina comercial")
    extras = dstages - set(DEAL_STAGES)
    check(not extras, f"sem estágios ativos fora da máquina (extras: {sorted(extras) or '—'})")
    pattrs = {a["api_slug"] for a in api.get("/objects/people/attributes")["data"]}
    check("company" in pattrs, "people.company (record-reference) disponível p/ vínculo por id")
    hooks = api.get("/webhooks")["data"]
    check(len(hooks) >= 1, f"webhook Attio→backend configurado ({len(hooks)} ativo(s))")
    print(f"CONTRACT-TEST: {'VERDE' if ok else 'VERMELHO'}")
    if DELTAS:
        print("DELTAS registrados nesta sessão:")
        for d in DELTAS:
            print(f"  - {d}")
    return ok


def smoke(api: Api, execute: bool) -> None:
    if not execute:
        print("smoke (dry-run): criaria company SEM domínio → person por record_id → "
              "entry na list → provaria deals=0 antes → criaria Deal pós-humano → PATCH espelho")
        return
    state: dict = {}
    print("— smoke sintético (tudo marcado [SINTÉTICO-QA])")

    pre = api.post("/objects/companies/records/query",
                   {"filter": {"cnpj": {"$eq": SYN_CNPJ}}, "limit": 5}).get("data", [])
    if pre:
        company = pre[0]
        print("  = company sintética já existia (retomada idempotente)")
    else:
        company = api.post(
            "/objects/companies/records",
            {"data": {"values": {"name": f"{SYN} Empresa Sem Domínio Ltda",
                                 "cnpj": SYN_CNPJ}}},
        )["data"]
    company_id = company["id"]["record_id"]
    state["company_id"] = company_id
    domains = company.get("values", {}).get("domains", [])
    print(f"  + company sem domínio criada ({company_id[:8]}…) domains={domains or 'NENHUM'}")

    found = api.post("/objects/companies/records/query",
                     {"filter": {"cnpj": {"$eq": SYN_CNPJ}}, "limit": 5}).get("data", [])
    assert len(found) == 1 and found[0]["id"]["record_id"] == company_id, (
        "dedupe por query-before-create falhou!"
    )
    print("  ✓ dedupe por CNPJ via query-before-create (DELTA-3): 1 registro, mesmo id")

    person = api.call(
        "PUT", "/objects/people/records?matching_attribute=email_addresses",
        {"data": {"values": {
            "name": [{"first_name": "Sintética", "last_name": "QA",
                      "full_name": f"Sintética QA {SYN}"}],
            "email_addresses": [SYN_EMAIL],
            "company": [{"target_object": "companies", "target_record_id": company_id}],
        }}},
    )["data"]
    person_id = person["id"]["record_id"]
    state["person_id"] = person_id
    linked = person.get("values", {}).get("company", [])
    print(f"  + person criada ({person_id[:8]}…) vínculo company por record_id: "
          f"{'OK' if linked else 'VAZIO (verificar delta)'}")

    entry = api.call(
        "PUT", f"/lists/{LIST_SLUG}/entries",
        {"data": {"parent_record_id": person_id, "parent_object": "people",
                  "entry_values": {"status": "Prospecção Automatizada",
                                   "ownership_state": "HANDOFF_REQUESTED",
                                   "source_system": "rumy",
                                   "external_lead_id": "lead-sintetico-f4",
                                   "campaign_id": f"{SYN} campanha"}}},
    )["data"]
    entry_id = entry["id"]["entry_id"]
    state["entry_id"] = entry_id
    print(f"  + entry na list ({entry_id[:8]}…) status=Prospecção Automatizada")

    deals = api.post("/objects/deals/records/query", {"limit": 50}).get("data", [])
    syn_deals = [d for d in deals if SYN in str(d.get("values", {}).get("name", ""))]
    assert not syn_deals, "Deal sintético existente ANTES da qualificação!"
    print("  ✓ nenhum Deal existe antes da qualificação humana (query confirmou)")

    member = api.get("/workspace_members")["data"][0]
    member_id = member["id"]["workspace_member_id"]
    deal = api.post(
        "/objects/deals/records",
        {"data": {"values": {
            "name": f"{SYN} Oportunidade pós-qualificação humana",
            "stage": "Qualificado",
            "owner": [{"referenced_actor_type": "workspace-member",
                       "referenced_actor_id": member_id}],
            "associated_people": [{"target_object": "people", "target_record_id": person_id}],
            "associated_company": [{"target_object": "companies", "target_record_id": company_id}],
        }}},
    )["data"]
    state["deal_id"] = deal["id"]["record_id"]
    print(f"  + Deal criado APÓS qualificação humana simulada ({state['deal_id'][:8]}…) "
          "stage=Qualificado owner=humano")

    api.patch(f"/lists/{LIST_SLUG}/entries/{entry_id}",
              {"data": {"entry_values": {"ownership_state": "HUMAN_OWNED"}}})
    print("  ✓ PATCH no espelho ownership_state via Attio: aceito (espelho é editável; "
          "a AUTORIDADE segue no Postgres — nada local muda, divergência é papel da "
          "reconciliação futura)")

    STATE_FILE.write_text(json.dumps(state))
    print(f"  state file: {STATE_FILE}")


def cleanup(api: Api, execute: bool) -> None:
    if not STATE_FILE.exists():
        print("cleanup: sem state file — nada registrado para remover")
    else:
        state = json.loads(STATE_FILE.read_text())
        steps = [
            ("deal_id", lambda i: api.delete(f"/objects/deals/records/{i}")),
            ("entry_id", lambda i: api.delete(f"/lists/{LIST_SLUG}/entries/{i}")),
            ("person_id", lambda i: api.delete(f"/objects/people/records/{i}")),
            ("company_id", lambda i: api.delete(f"/objects/companies/records/{i}")),
        ]
        for key, fn in steps:
            if key in state:
                if execute:
                    try:
                        fn(state[key])
                        print(f"  - {key} removido")
                    except RuntimeError as e:
                        print(f"  ! {key}: {e}")
                else:
                    print(f"  ~ {key} SERIA removido (dry-run)")
        if execute:
            STATE_FILE.unlink()
    if execute:
        # resíduo: procurar sobras sintéticas por chaves determinísticas
        res = api.post("/objects/companies/records/query",
                       {"filter": {"cnpj": {"$eq": SYN_CNPJ}}, "limit": 5}).get("data", [])
        res2 = api.post("/objects/people/records/query",
                        {"filter": {"email_addresses": {"$eq": SYN_EMAIL}}, "limit": 5}).get("data", [])
        for r in res:
            api.delete(f"/objects/companies/records/{r['id']['record_id']}")
            print("  - resíduo de company removido por query")
        for r in res2:
            api.delete(f"/objects/people/records/{r['id']['record_id']}")
            print("  - resíduo de person removido por query")
        res = api.post("/objects/companies/records/query",
                       {"filter": {"cnpj": {"$eq": SYN_CNPJ}}, "limit": 5}).get("data", [])
        res2 = api.post("/objects/people/records/query",
                        {"filter": {"email_addresses": {"$eq": SYN_EMAIL}}, "limit": 5}).get("data", [])
        print(f"  resíduo pós-limpeza: companies={len(res)} people={len(res2)} (esperado 0/0)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", required=True, type=Path)
    ap.add_argument("--execute", action="store_true", help="sem esta flag, tudo é dry-run")
    ap.add_argument("phase", choices=["snapshot", "provision", "verify", "smoke", "cleanup"])
    ap.add_argument("--out", type=Path, default=Path("attio_snapshot.json"))
    args = ap.parse_args()

    api = Api(_load_key(args.env_file))
    guard_workspace(api)

    if args.phase == "snapshot":
        snapshot(api, args.out)
    elif args.phase == "provision":
        provision(api, args.execute)
    elif args.phase == "verify":
        sys.exit(0 if verify(api) else 1)
    elif args.phase == "smoke":
        smoke(api, args.execute)
    elif args.phase == "cleanup":
        cleanup(api, args.execute)


if __name__ == "__main__":
    main()
