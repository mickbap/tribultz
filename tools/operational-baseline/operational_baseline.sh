#!/usr/bin/env bash
# Tribultz Weekly Snapshot — retrato semanal do estado da empresa (produto + infra
# + dados + saúde). Hábito: rodar toda sexta.
#
#   bash tools/operational-baseline/operational_baseline.sh [repo_root]
#
# Mede o que consegue no ambiente atual; fontes indisponíveis viram "n/d" (o slot
# permanece, para o histórico ser consistente). Não falha se um grep achar 0.
set +e
export PATH="$PATH:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-$(cd "$HERE/../.." && pwd)}"
cd "$ROOT" || exit 1
TEMPLATE="$HERE/templates/snapshot.md"
CONFIG="$HERE/baseline_config.yml"
DATE="$(date +%F)"
YEAR="$(date +%Y)"
mkdir -p "$HERE/output/$YEAR"
OUT="$HERE/output/$YEAR/$DATE.md"

# ── medições ──────────────────────────────────────────────────────────────────
n_lines() { wc -l | tr -d ' '; }
count()   { grep -oE "$1 = [0-9]+" frontend/src/lib/validation/rulesMeta.ts 2>/dev/null | grep -oE '[0-9]+' | head -1; }
absent()  { grep -rnwE "$1" backend/app frontend/src 2>/dev/null | grep -viE 'test|\.md|snapshot' | n_lines; }

REF="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
WEEK="$(date +%V)"
RULES="$(count RULES_COUNT)";       RULES="${RULES:-n/d}"
CLASSTRIB="$(count CLASSTRIB_COUNT)"; CLASSTRIB="${CLASSTRIB:-n/d}"
ROUTERS="$(ls backend/app/routers/*.py 2>/dev/null | grep -v __init__ | n_lines)"
ENDPOINTS="$(grep -rhoE '@router\.(get|post|put|delete|patch|api_route)' backend/app/routers 2>/dev/null | n_lines)"
PAGES="$(ls -d frontend/src/app/*/ 2>/dev/null | n_lines)"
MIGRATIONS="$(ls backend/app/alembic/versions/*.py 2>/dev/null | n_lines)"
TODOS="$(grep -rnE 'TODO|FIXME|XXX' backend/app frontend/src 2>/dev/null | grep -viE '\.md|snapshot' | n_lines)"
S3="$(grep -c '_probe_s3' backend/app/routers/health.py 2>/dev/null)"
[ "${S3:-0}" -gt 0 ] 2>/dev/null && STORAGE_PROBE="presente" || STORAGE_PROBE="AUSENTE"

# gh (se disponível)
if command -v gh >/dev/null 2>&1; then
  ISSUES_OPEN="$(gh issue list --repo mickbap/tribultz --state open --limit 200 --json number -q 'length' 2>/dev/null)"
  ISSUES_P2="$(gh issue list --repo mickbap/tribultz --state open --label P2 --limit 200 --json number -q 'length' 2>/dev/null)"
fi
ISSUES_OPEN="${ISSUES_OPEN:-n/d}"; ISSUES_P2="${ISSUES_P2:-n/d}"

# db (não medido aqui — preenchido em ambiente com banco: CI/VM)
USERS="n/d (requer DB)"; TENANTS="n/d (requer DB)"; APIKEYS="n/d (requer DB)"
LAUDOS="n/d (requer DB)"; XMLS="n/d (requer DB)"; PENDING_MIGS="n/d (requer DB)"
RFCS="ver tribultz-brain (status: proposed)"

EA="$(absent EarlyAdopter)"; EG="$(absent EarlyGrant)"
EL="$(absent EffectiveLicense)"; TERA="$(absent TERA)"
NEXT_PRIORITY="$(grep -E '^next_priority:' "$CONFIG" | sed -E 's/^next_priority: *"?//; s/"? *$//')"

# ── render (substitui {{VAR}} no template) ────────────────────────────────────
render="$(cat "$TEMPLATE")"
for kv in DATE WEEK REF BRANCH RULES CLASSTRIB ROUTERS ENDPOINTS PAGES \
          MIGRATIONS PENDING_MIGS STORAGE_PROBE USERS TENANTS APIKEYS LAUDOS XMLS \
          TODOS ISSUES_OPEN ISSUES_P2 RFCS EA EG EL TERA NEXT_PRIORITY; do
  val="${!kv}"
  render="${render//\{\{$kv\}\}/$val}"
done
printf '%s\n' "$render" > "$OUT"
echo "Snapshot: $OUT (semana $WEEK, ref $BRANCH@$REF)"
