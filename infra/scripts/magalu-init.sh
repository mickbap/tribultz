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
    postgresql-client fail2ban

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
# Permissão restrita — apenas root lê o arquivo com credentials
chmod 600 "$DEPLOY_DIR/.env"
chown root:root "$DEPLOY_DIR/.env"
log "    .env: chmod 600 aplicado (leitura apenas pelo root)"

# ── 4b. Switch to project root so Docker Compose finds .env ──
# With -f /absolute/path, Docker Compose's default project dir is the
# compose file's directory (/opt/tribultz/infra), which has no .env.
# cd to DEPLOY_DIR instead: .env is here, and build context "../backend"
# resolves correctly from the compose file location (../backend from infra/).
cd "$DEPLOY_DIR"
COMPOSE_CMD="docker compose -f $DEPLOY_DIR/$COMPOSE_FILE"

# ── 5. Build images ───────────────────────────────────────
log "==> Building Docker images (this may take a few minutes)"
$COMPOSE_CMD build --pull 2>&1 | tee -a "$LOG_FILE"

# ── 6. Start Redis ────────────────────────────────────────
# PostgreSQL runs on Magalu DBaaS — no local db container needed
log "==> Starting Redis (broker + cache)"
$COMPOSE_CMD up -d redis
log "    Waiting for Redis to be healthy..."
for i in $(seq 1 20); do
    $COMPOSE_CMD ps --format json redis 2>/dev/null \
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
$COMPOSE_CMD run --rm api \
    python -m alembic upgrade head 2>&1 | tee -a "$LOG_FILE"
log "    Migrations complete"

# ── 8. Start full stack ───────────────────────────────────
log "==> Starting full stack (api, worker, beat)"
$COMPOSE_CMD up -d 2>&1 | tee -a "$LOG_FILE"

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

# ── 9b. SSH hardening (CIS Ubuntu 5.2 / STIG) ────────────
log "==> Hardening SSH"
# Apenas desabilita password auth se houver ao menos uma chave autorizada
# — evita lockout acidental na primeira execução
if find /root/.ssh /home -name authorized_keys -readable 2>/dev/null | grep -q .; then
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/'   /etc/ssh/sshd_config
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/'                 /etc/ssh/sshd_config
    sed -i 's/^#\?MaxAuthTries.*/MaxAuthTries 3/'                        /etc/ssh/sshd_config
    sed -i 's/^#\?ClientAliveInterval.*/ClientAliveInterval 300/'        /etc/ssh/sshd_config
    sed -i 's/^#\?ClientAliveCountMax.*/ClientAliveCountMax 2/'          /etc/ssh/sshd_config
    # Ubuntu 22.04+ usa "ssh" (não "sshd") como nome do serviço
    systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true
    log "    SSH: password auth OFF, root login OFF, idle timeout 10 min, max 3 tentativas"
else
    log "    AVISO: authorized_keys não encontrado — SSH hardening pulado para evitar lockout"
    log "    Configure sua chave SSH e execute manualmente:"
    log "      sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config && systemctl reload sshd"
fi

# ── 9c. fail2ban (proteção contra brute force SSH/nginx) ──
log "==> Configurando fail2ban"
# Proteção SSH: bane IP após 5 tentativas em 10 min por 1 hora
cat > /etc/fail2ban/jail.d/tribultz.conf <<'F2B'
[sshd]
enabled  = true
port     = ssh
maxretry = 5
findtime = 600
bantime  = 3600
logpath  = %(sshd_log)s
backend  = %(sshd_backend)s

[nginx-http-auth]
enabled  = true
port     = http,https
maxretry = 5
findtime = 600
bantime  = 3600
F2B
systemctl enable --now fail2ban
log "    fail2ban ativo: bane IPs após 5 tentativas SSH ou auth nginx em 10 min"

# ── 10. Nginx reverse proxy ───────────────────────────────
log "==> Configuring Nginx reverse proxy for api.tribultz.com.br"
cat > /etc/nginx/sites-available/tribultz-api <<'NGINX'
# ── Rate limiting (defesa em profundidade sobre o rate limit da API) ──
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/m;

server {
    listen 80;
    server_name api.tribultz.com.br;

    # ── Security headers (OWASP Secure Headers Project) ──────────
    server_tokens off;                                   # não expõe versão nginx
    add_header X-Frame-Options            "DENY"                            always;
    add_header X-Content-Type-Options     "nosniff"                         always;
    add_header Referrer-Policy            "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy         "camera=(), microphone=(), geolocation=()" always;
    # HSTS será adicionado pelo certbot --redirect após TLS

    location / {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
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

# ── 12. TLS automático via certbot + fechamento da porta 8000 ──
log "==> Tentando emitir certificado TLS (api.tribultz.com.br)"
log "    (Requer que o DNS A já aponte para este IP)"
if certbot --nginx -d api.tribultz.com.br \
           --non-interactive --agree-tos \
           -m infra@tribultz.com.br \
           --redirect 2>&1 | tee -a "$LOG_FILE"; then
    log "    TLS emitido com sucesso ✓"
    # Com TLS ativo, porta 8000 direta não é mais necessária
    ufw delete allow 8000/tcp 2>/dev/null || true
    log "    Porta 8000 fechada — acesso exclusivamente via HTTPS/nginx ✓"
    # Renovação automática
    if command -v snap &>/dev/null && snap list certbot &>/dev/null 2>&1; then
        systemctl enable --now snap.certbot.renew.timer 2>/dev/null || true
    else
        (crontab -l 2>/dev/null; \
         echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'") \
        | sort -u | crontab -
    fi
    log "    Renovação automática de certificado configurada ✓"
else
    log ""
    log "  !! certbot falhou — DNS ainda não aponta para este IP, ou domínio não acessível"
    log "  !! Porta 8000 permanece ABERTA como fallback temporário"
    log "  !!"
    log "  !! Após apontar o DNS, execute:"
    log "  !!   certbot --nginx -d api.tribultz.com.br --non-interactive --agree-tos -m infra@tribultz.com.br"
    log "  !!   ufw delete allow 8000/tcp    # fechar porta após TLS confirmado"
    log ""
fi

# ── 14. Summary ───────────────────────────────────────────
CURRENT_IP=$(curl -sf ifconfig.me 2>/dev/null || echo '<MAGALU_IP>')
log ""
log "=== TRIBULTZ DEPLOY COMPLETE ==================================="
log "  IP:             $CURRENT_IP"
log "  API (direto):   http://$CURRENT_IP:8000/health   (fecha após TLS)"
log "  API (nginx):    http://api.tribultz.com.br/health"
log ""
log "  CHECKLIST PÓS-DEPLOY:"
log "  [ ] DNS A: api.tribultz.com.br → $CURRENT_IP"
log "  [ ] TLS:   certbot (auto-executado acima, verificar logs)"
log "  [ ] Porta 8000 UFW fechada (auto após TLS, verificar: ufw status)"
log "  [ ] Chave SSH configurada + PasswordAuthentication no"
log "  [ ] fail2ban ativo: systemctl status fail2ban"
log ""
log "  OPERAÇÕES:"
log "  Deploy:    bash $DEPLOY_DIR/infra/scripts/deploy.sh"
log "  Migração:  bash $DEPLOY_DIR/infra/scripts/db-migrate.sh --prod"
log "  Status:    docker compose -f $DEPLOY_DIR/$COMPOSE_FILE ps"
log "  Logs API:  docker compose -f $DEPLOY_DIR/$COMPOSE_FILE logs -f api"
log "================================================================="
