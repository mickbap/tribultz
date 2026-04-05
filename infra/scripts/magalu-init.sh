#!/usr/bin/env bash
# ============================================================
# Tribultz — Magalu Cloud VM Bootstrap (Solo Soberano)
# ============================================================
# Run as root on a fresh Ubuntu 24.04 LTS instance.
# After this script, the API will be live on :8000 and
# the DB will be migrated to head.
#
# Usage:
#   wget -qO- https://raw.githubusercontent.com/mickbap/tribultz/main/infra/scripts/magalu-init.sh | bash
#   -- OR --
#   scp infra/scripts/magalu-init.sh user@<MAGALU_IP>:/tmp/
#   ssh user@<MAGALU_IP> "sudo bash /tmp/magalu-init.sh"
# ============================================================

set -euo pipefail

REPO_URL="https://github.com/mickbap/tribultz.git"
DEPLOY_DIR="/opt/tribultz"
COMPOSE_FILE="infra/docker-compose.prod.yml"
LOG_FILE="/var/log/tribultz-init.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# ── 1. System deps ────────────────────────────────────────
log "==> Installing system dependencies"
apt-get update -qq
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg git ufw nginx certbot python3-certbot-nginx \
    postgresql-client

# ── 2. Docker Engine ──────────────────────────────────────
if ! command -v docker &>/dev/null; then
    log "==> Installing Docker Engine"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable docker
    log "    Docker $(docker --version) installed"
else
    log "    Docker already present: $(docker --version)"
fi

# ── 3. Clone or update repo ───────────────────────────────
log "==> Cloning repository to $DEPLOY_DIR"
if [ -d "$DEPLOY_DIR/.git" ]; then
    git -C "$DEPLOY_DIR" pull --ff-only
    log "    Repo updated"
else
    git clone --depth 1 "$REPO_URL" "$DEPLOY_DIR"
    log "    Repo cloned"
fi

# ── 4. Environment file ───────────────────────────────────
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    log ""
    log "  !! .env NOT FOUND at $DEPLOY_DIR/.env"
    log "  !! Copy the template and fill ALL fields marked REQUIRED_CHANGE_ME:"
    log "  !!"
    log "  !!   cp $DEPLOY_DIR/.env.prod.template $DEPLOY_DIR/.env"
    log "  !!   nano $DEPLOY_DIR/.env"
    log "  !!"
    log "  !! Required fields (minimum):"
    log "  !!   DATABASE_URL=postgresql+psycopg2://tribultz:<pw>@<magalu-host>:5432/tribultz"
    log "  !!   REDIS_PASSWORD=<openssl rand -hex 24>"
    log "  !!   REDIS_URL=redis://:<REDIS_PASSWORD>@redis:6379/0"
    log "  !!   JWT_SECRET=<openssl rand -hex 32>"
    log "  !!   S3_ACCESS_KEY=<MAGALU_ACCESS_KEY>  S3_SECRET_KEY=<MAGALU_SECRET_KEY>"
    log "  !!"
    log "  After filling .env, rerun: bash $0"
    exit 1
fi
log "    .env found"

# ── 5. Build images ───────────────────────────────────────
log "==> Building Docker images (this may take a few minutes)"
docker compose -f "$DEPLOY_DIR/$COMPOSE_FILE" build --pull 2>&1 | tee -a "$LOG_FILE"

# ── 6. Start Redis ────────────────────────────────────────
# PostgreSQL runs on Magalu DBaaS — no local db container needed
log "==> Starting Redis (broker + cache)"
docker compose -f "$DEPLOY_DIR/$COMPOSE_FILE" up -d redis
log "    Waiting for Redis to be healthy..."
for i in $(seq 1 20); do
    docker compose -f "$DEPLOY_DIR/$COMPOSE_FILE" ps --format json redis 2>/dev/null \
        | grep -q '"Health":"healthy"' && break
    sleep 3
    [ "$i" -eq 20 ] && { log "ERROR: Redis did not become healthy in 60s"; exit 1; }
done
log "    Redis healthy"

# ── 6b. Verify DBaaS connectivity ────────────────────────
log "==> Verifying Magalu DBaaS connectivity"
# Source .env to get POSTGRES_HOST/USER/DB
set -a; source "$DEPLOY_DIR/.env"; set +a
if pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT:-5432}" \
              -U "${POSTGRES_USER:-tribultz}" -d "${POSTGRES_DB:-tribultz}" \
              -t 10 &>/dev/null; then
    log "    DBaaS reachable at ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}"
else
    log "ERROR: Cannot reach DBaaS at ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}"
    log "       Check POSTGRES_HOST in .env and Magalu VPC firewall rules"
    exit 1
fi

# ── 7. Run Alembic migrations ─────────────────────────────
log "==> Running database migrations (alembic upgrade head)"
docker compose -f "$DEPLOY_DIR/$COMPOSE_FILE" run --rm api \
    python -m alembic upgrade head 2>&1 | tee -a "$LOG_FILE"
log "    Migrations complete"

# ── 8. Start full stack ───────────────────────────────────
log "==> Starting full stack (api, worker, beat)"
docker compose -f "$DEPLOY_DIR/$COMPOSE_FILE" up -d 2>&1 | tee -a "$LOG_FILE"

# ── 9. UFW firewall ───────────────────────────────────────
log "==> Configuring UFW firewall"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp     # direct API access (remove after nginx/HTTPS configured)
ufw --force enable
log "    UFW active. Ports: 22, 80, 443, 8000"

# ── 10. Nginx reverse proxy ───────────────────────────────
log "==> Configuring Nginx reverse proxy for api.tribultz.com.br"
cat > /etc/nginx/sites-available/tribultz-api <<'NGINX'
server {
    listen 80;
    server_name api.tribultz.com.br;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        client_max_body_size 50M;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/tribultz-api /etc/nginx/sites-enabled/tribultz-api
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
log "    Nginx configured for api.tribultz.com.br → :8000"

# ── 11. Health check ─────────────────────────────────────
log "==> Waiting for API to be healthy"
for i in $(seq 1 20); do
    STATUS=$(curl -sf http://localhost:8000/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "waiting")
    if [ "$STATUS" = "ok" ] || [ "$STATUS" = "healthy" ]; then
        log "    API healthy: $STATUS"
        break
    fi
    sleep 3
    [ "$i" -eq 20 ] && log "WARNING: API did not respond healthy in 60s — check logs with: docker compose logs api"
done

# ── 12. Summary ───────────────────────────────────────────
log ""
log "=== TRIBULTZ DEPLOY COMPLETE ==================================="
log "  API direct:     http://$(curl -sf ifconfig.me 2>/dev/null || echo '<MAGALU_IP>'):8000/health"
log "  API via nginx:  http://api.tribultz.com.br/health"
log ""
log "  NEXT STEPS:"
log "  1. Point api.tribultz.com.br DNS A record → $(curl -sf ifconfig.me 2>/dev/null || echo '<MAGALU_IP>')"
log "  2. Issue TLS cert: certbot --nginx -d api.tribultz.com.br --non-interactive --agree-tos -m infra@tribultz.com.br"
log "  3. Remove ufw allow 8000/tcp after HTTPS is confirmed"
log "  4. docker compose -f $DEPLOY_DIR/$COMPOSE_FILE ps  ← all containers Running"
log "================================================================="
