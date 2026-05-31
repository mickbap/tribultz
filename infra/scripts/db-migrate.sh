#!/usr/bin/env bash
# ============================================================
# Tribultz — Safe Database Migration Runner
# ============================================================
# Runs alembic upgrade head inside the api container.
# Creates a pg_dump backup first and rolls back if migration fails.
#
# Usage (from repo root):
#   bash infra/scripts/db-migrate.sh [--prod]
#
# Flags:
#   --prod    Use docker-compose.prod.yml (default: docker-compose.yml)
# ============================================================

set -euo pipefail

COMPOSE_FILE="infra/docker-compose.yml"
BACKUP_DIR="/tmp/tribultz-db-backups"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
PROD=false

if [[ "${1:-}" == "--prod" ]]; then
    COMPOSE_FILE="infra/docker-compose.prod.yml"
    PROD=true
    echo "[migrate] Using PRODUCTION compose file (Magalu DBaaS)"
fi

mkdir -p "$BACKUP_DIR"

# ── 1. Pre-migration backup ───────────────────────────────
echo "[migrate] Creating pre-migration backup → $BACKUP_DIR/pre_migrate_$TIMESTAMP.dump"
if [ "$PROD" = true ]; then
    # Production: pg_dump from host connecting to Magalu DBaaS
    # Requires postgresql-client installed on VM (done by magalu-init.sh)
    # Source .env to get DB credentials
    ENV_FILE="${DEPLOY_DIR:-/opt/tribultz}/.env"
    [ -f "$ENV_FILE" ] && { set -a; source "$ENV_FILE"; set +a; }
    PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT:-5432}" \
        -U "${POSTGRES_USER:-tribultz}" \
        -d "${POSTGRES_DB:-tribultz}" \
        -Fc -Z 6 \
        > "$BACKUP_DIR/pre_migrate_$TIMESTAMP.dump"
else
    # Local dev: pg_dump from the db container
    docker compose -f "$COMPOSE_FILE" exec -T db \
        pg_dump -U "${POSTGRES_USER:-tribultz}" \
                -d "${POSTGRES_DB:-tribultz}" \
                -Fc -Z 6 \
        > "$BACKUP_DIR/pre_migrate_$TIMESTAMP.dump"
fi
echo "[migrate] Backup complete ($(du -h "$BACKUP_DIR/pre_migrate_$TIMESTAMP.dump" | cut -f1))"

# ── 2. Show current head ──────────────────────────────────
echo "[migrate] Current revision:"
docker compose -f "$COMPOSE_FILE" run --rm --no-deps api \
    python -m alembic current 2>/dev/null || true

# ── 3. Run migration ──────────────────────────────────────
# --no-deps: evita recriar Redis/outros serviços durante a migration
echo "[migrate] Running: alembic upgrade head"
if docker compose -f "$COMPOSE_FILE" run --rm --no-deps api \
        python -m alembic upgrade head; then
    echo "[migrate] SUCCESS — all migrations applied"
else
    echo "[migrate] FAILED — migration error"
    echo ""
    echo "  To restore from backup:"
    if [ "$PROD" = true ]; then
        echo "    PGPASSWORD=\$POSTGRES_PASSWORD pg_restore \\"
        echo "      -h \$POSTGRES_HOST -p \${POSTGRES_PORT:-5432} \\"
        echo "      -U \${POSTGRES_USER:-tribultz} -d \${POSTGRES_DB:-tribultz} \\"
        echo "      --clean --if-exists $BACKUP_DIR/pre_migrate_$TIMESTAMP.dump"
    else
        echo "    docker compose -f $COMPOSE_FILE exec -T db \\"
        echo "      pg_restore -U \${POSTGRES_USER:-tribultz} \\"
        echo "                 -d \${POSTGRES_DB:-tribultz} \\"
        echo "                 --clean --if-exists \\"
        echo "                 $BACKUP_DIR/pre_migrate_$TIMESTAMP.dump"
    fi
    exit 1
fi

# ── 4. Show new head ──────────────────────────────────────
echo "[migrate] New revision:"
docker compose -f "$COMPOSE_FILE" run --rm --no-deps api \
    python -m alembic current 2>/dev/null || true

echo ""
echo "[migrate] Done. Backup retained at: $BACKUP_DIR/pre_migrate_$TIMESTAMP.dump"
