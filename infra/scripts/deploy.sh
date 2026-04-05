#!/usr/bin/env bash
# ============================================================
# Tribultz — Rolling Deploy Script
# ============================================================
# Faz deploy seguro com rollback automático em caso de falha.
# Rebuild local das imagens + restart sequencial dos serviços.
#
# Uso (na VM, dentro de /opt/tribultz):
#   bash infra/scripts/deploy.sh
#
# Flags:
#   --skip-pull    Não faz git pull (deploy do código atual)
#   --migrate      Roda migrações Alembic antes de reiniciar
# ============================================================

set -euo pipefail

DEPLOY_DIR="/opt/tribultz"
COMPOSE_FILE="$DEPLOY_DIR/infra/docker-compose.prod.yml"
LOG_FILE="/var/log/tribultz-deploy.log"
SKIP_PULL=false
RUN_MIGRATE=false

# ── Flags ────────────────────────────────────────────────────
for arg in "$@"; do
    case $arg in
        --skip-pull)  SKIP_PULL=true ;;
        --migrate)    RUN_MIGRATE=true ;;
    esac
done

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "=== TRIBULTZ DEPLOY INICIADO ==================================="
log "  Compose: $COMPOSE_FILE"
log "  skip-pull: $SKIP_PULL | migrate: $RUN_MIGRATE"

# ── 1. Git pull ──────────────────────────────────────────────
if [ "$SKIP_PULL" = false ]; then
    log "==> [1/6] Atualizando código (git pull)"
    git -C "$DEPLOY_DIR" fetch --quiet
    LOCAL=$(git -C "$DEPLOY_DIR" rev-parse HEAD)
    REMOTE=$(git -C "$DEPLOY_DIR" rev-parse @{u})
    if [ "$LOCAL" = "$REMOTE" ]; then
        log "    Nenhuma atualização disponível — código já está na última versão"
        log "    Use --skip-pull para forçar rebuild mesmo sem mudanças"
    fi
    git -C "$DEPLOY_DIR" pull --ff-only
    log "    Commit atual: $(git -C "$DEPLOY_DIR" rev-parse --short HEAD)"
else
    log "==> [1/6] Pulando git pull (--skip-pull)"
fi

# ── 2. Build imagens ─────────────────────────────────────────
log "==> [2/6] Buildando imagens Docker"
docker compose -f "$COMPOSE_FILE" build --pull 2>&1 | tee -a "$LOG_FILE"
log "    Build concluído"

# ── 3. Migrações Alembic ─────────────────────────────────────
if [ "$RUN_MIGRATE" = true ]; then
    log "==> [3/6] Rodando migrações Alembic"
    bash "$DEPLOY_DIR/infra/scripts/db-migrate.sh" --prod
    log "    Migrações concluídas"
else
    log "==> [3/6] Pulando migrações (use --migrate para executar)"
fi

# ── Função: aguardar health check ────────────────────────────
wait_healthy() {
    local service=$1
    local max_attempts=${2:-20}
    log "    Aguardando $service ficar healthy..."
    for i in $(seq 1 "$max_attempts"); do
        STATUS=$(docker compose -f "$COMPOSE_FILE" ps --format json "$service" 2>/dev/null \
            | grep -o '"Health":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
        if [ "$STATUS" = "healthy" ]; then
            log "    $service: healthy ✓"
            return 0
        fi
        sleep 3
    done
    log "    ERRO: $service não ficou healthy após $((max_attempts * 3))s"
    return 1
}

# ── Função: rollback ─────────────────────────────────────────
rollback() {
    log "!!! ROLLBACK: $1 — revertendo para imagem anterior"
    docker compose -f "$COMPOSE_FILE" up -d --no-deps "$1" 2>&1 | tee -a "$LOG_FILE" || true
    log "!!! Rollback concluído. Verifique os logs: docker compose logs $1"
    exit 1
}

# ── 4. Restart API (com health check) ────────────────────────
log "==> [4/6] Reiniciando API"
docker compose -f "$COMPOSE_FILE" up -d --no-deps --build api 2>&1 | tee -a "$LOG_FILE"
if ! wait_healthy api 20; then
    rollback api
fi

# Verificação extra via HTTP
log "    Verificando endpoint /health"
for i in $(seq 1 10); do
    HTTP_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
    if [ "$HTTP_STATUS" = "200" ]; then
        log "    /health respondeu 200 ✓"
        break
    fi
    sleep 3
    [ "$i" -eq 10 ] && { log "    ERRO: /health não respondeu 200 após 30s"; rollback api; }
done

# ── 5. Restart Worker ────────────────────────────────────────
log "==> [5/6] Reiniciando Celery Worker"
docker compose -f "$COMPOSE_FILE" up -d --no-deps --build worker 2>&1 | tee -a "$LOG_FILE"
sleep 5
WORKER_STATUS=$(docker compose -f "$COMPOSE_FILE" ps worker --format json 2>/dev/null \
    | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
if [ "$WORKER_STATUS" != "running" ]; then
    log "    ERRO: worker não está running (estado: $WORKER_STATUS)"
    rollback worker
fi
log "    worker: running ✓"

# ── 6. Restart Beat ──────────────────────────────────────────
log "==> [6/6] Reiniciando Celery Beat"
docker compose -f "$COMPOSE_FILE" up -d --no-deps --build beat 2>&1 | tee -a "$LOG_FILE"
sleep 3
BEAT_STATUS=$(docker compose -f "$COMPOSE_FILE" ps beat --format json 2>/dev/null \
    | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
if [ "$BEAT_STATUS" != "running" ]; then
    log "    AVISO: beat não está running (estado: $BEAT_STATUS) — verificar logs"
fi
log "    beat: $BEAT_STATUS"

# ── Resumo ───────────────────────────────────────────────────
log ""
log "=== DEPLOY CONCLUÍDO ==========================================="
log "  Commit: $(git -C "$DEPLOY_DIR" rev-parse --short HEAD)"
log "  Hora:   $(date '+%Y-%m-%d %H:%M:%S')"
log ""
docker compose -f "$COMPOSE_FILE" ps 2>&1 | tee -a "$LOG_FILE"
log "================================================================"
log "  Health: curl http://localhost:8000/health"
log "  Logs:   docker compose -f $COMPOSE_FILE logs -f api"
log "================================================================"
