#!/usr/bin/env bash
# ============================================================
# TRIBULTZ — Verificação de Acessos (macOS / Linux / Git Bash)
# Run: bash tools/check_access.sh
# Requires: curl, ssh, bash. Opcionais: mgc, gh, vercel
#
# Não contém segredos e não escreve nenhum. Lê a API key da Magalu
# de $MGC_API_KEY. Só faz chamadas de leitura.
# ============================================================

VM_HOST="201.54.20.18"
VM_USER="ubuntu"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
# Fingerprints das chaves autorizadas na VM (públicos — não são segredo).
# Ao adicionar uma máquina, autorize a chave em ~/.ssh/authorized_keys na VM e liste aqui.
KEY_FPS="SHA256:ydI3GwtHcGHjUvcCzFQgOp7zypbiVwqqiicGlhun7gg=tribultz-infra (Windows)
SHA256:6DqZCh26dT2Ce0KPD8ZwMXPtZ9++3siBctZKD1E+8ig=tribultz-infra (Mac)"
API="https://api.tribultz.com.br"
FRONTEND="https://tribultz.com.br"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; DIM='\033[2m'; NC='\033[0m'
PASS=0; FAIL=0; WARN=0
ok()   { echo -e "  ${GREEN}✓${NC} $1"; PASS=$((PASS+1)); }
bad()  { echo -e "  ${RED}✗${NC} $1"; [ -n "$2" ] && echo -e "    ${DIM}→ $2${NC}"; FAIL=$((FAIL+1)); }
warn() { echo -e "  ${YELLOW}!${NC} $1"; [ -n "$2" ] && echo -e "    ${DIM}→ $2${NC}"; WARN=$((WARN+1)); }
code() { curl -s -o /dev/null -w '%{http_code}' -m 15 "$@"; }

echo
echo "=== 1. SSH → VM de produção ==============================="
if [ ! -f "$SSH_KEY" ]; then
  bad "chave $SSH_KEY não existe" "copie a chave privada da máquina antiga (ela NÃO está no git)"
else
  # macOS/Linux recusam chave com permissão frouxa; Git Bash no Windows usa ACL e ignora
  case "$(uname -s)" in
    Darwin) PERM=$(stat -f '%Lp' "$SSH_KEY" 2>/dev/null) ;;
    Linux)  PERM=$(stat -c '%a' "$SSH_KEY" 2>/dev/null) ;;
    *)      PERM="" ;;   # MINGW/MSYS/CYGWIN: permissão POSIX não é significativa
  esac
  if [ -n "$PERM" ]; then
    case "$PERM" in
      600|400) ok "permissão da chave: $PERM" ;;
      *)       bad "permissão da chave é $PERM — o SSH recusa a chave" "chmod 600 $SSH_KEY" ;;
    esac
  else
    echo -e "  ${DIM}· permissão não verificada (Windows usa ACL, não modo POSIX)${NC}"
  fi
  FP=$(ssh-keygen -lf "${SSH_KEY}.pub" 2>/dev/null | awk '{print $2}')
  if [ -z "$FP" ]; then
    warn "sem ${SSH_KEY}.pub para conferir fingerprint"
  else
    NAME=$(printf '%s\n' "$KEY_FPS" | grep -F "$FP=" | cut -d= -f2-)
    if [ -n "$NAME" ]; then
      ok "chave reconhecida: $NAME"
    else
      # Não é falha: a autoridade é o teste de conexão logo abaixo. Uma chave nova
      # e legítima simplesmente ainda não foi listada em KEY_FPS.
      warn "chave não listada em KEY_FPS ($FP)" "se a conexão abaixo funcionar, a chave é válida — considere adicioná-la a KEY_FPS"
    fi
  fi

  if ssh -i "$SSH_KEY" -o BatchMode=yes -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new \
       "$VM_USER@$VM_HOST" 'exit 0' 2>/dev/null; then
    ok "SSH conecta em $VM_USER@$VM_HOST"
  else
    bad "SSH falhou" "a chave pública precisa estar em ~/.ssh/authorized_keys na VM; confira também o firewall (porta 22)"
  fi
fi

echo
echo "=== 2. Magalu Cloud (mgc CLI) ============================="
if ! command -v mgc >/dev/null 2>&1; then
  bad "mgc não está no PATH" "instale: github.com/MagaluCloud/mgccli (Mac: darwin_arm64) e confira o sha256"
else
  ok "mgc encontrado: $(mgc --version 2>/dev/null | head -1)"
  # Testa o acesso de verdade, não a forma de autenticar: serve tanto para
  # sessão OAuth (mgc auth login) quanto para MGC_API_KEY.
  if mgc virtual-machine instances list 2>/dev/null | grep -q 'tribultz-api'; then
    if [ -n "$MGC_API_KEY" ]; then
      ok "acesso ok — VM tribultz-api visível (via MGC_API_KEY)"
    else
      ok "acesso ok — VM tribultz-api visível (via sessão de 'mgc auth login')"
    fi
  else
    if [ -n "$MGC_API_KEY" ]; then
      bad "MGC_API_KEY definida mas a chamada falhou" "key errada/revogada, ou key de outro tenant"
    elif mgc auth tenant list >/dev/null 2>&1; then
      # Autenticado, mas sem enxergar a VM: quase sempre é tenant errado.
      bad "autenticado, mas a VM tribultz-api não aparece" "TENANT ERRADO. A conta tem 2 tenants e o 'mgc auth login' cai no pessoal (mickel.baptista@outlook.com) por padrão; a VM vive no mickel@6tech.net.br (managed). Veja 'mgc auth tenant list' e selecione o correto. ATENÇÃO: 'mgc auth tenant set' IMPRIME access_token e refresh_token em texto puro — redirecione a saída (> /dev/null) ou não compartilhe o terminal."
    else
      bad "sem acesso à Magalu" "rode 'mgc auth login' (OAuth por navegador, cria sessão persistente) OU export MGC_API_KEY=... — sem um dos dois o mgc falha com 'RefreshToken is not set'"
    fi
  fi
fi

echo
echo "=== 3. GitHub (gh CLI) ===================================="
if ! command -v gh >/dev/null 2>&1; then
  warn "gh não instalado" "brew install gh && gh auth login"
elif gh auth status >/dev/null 2>&1; then
  ok "gh autenticado ($(gh api user --jq .login 2>/dev/null))"
  gh auth status 2>&1 | grep -qi "'workflow'" \
    && ok "escopo workflow presente" \
    || warn "sem escopo workflow" "não edita .github/workflows via API — só via push. Corrigir: gh auth refresh -h github.com -s workflow"
else
  bad "gh não autenticado" "gh auth login"
fi

echo
echo "=== 4. Vercel ============================================="
echo -e "  ${DIM}Deploy NÃO depende desta máquina: quem publica é o vercel[bot] via GitHub App.${NC}"
if ! command -v vercel >/dev/null 2>&1; then
  warn "vercel CLI não instalado" "só é necessário para deploy manual (vercel --prod). Deploy por push não precisa."
elif vercel whoami >/dev/null 2>&1; then
  ok "vercel CLI autenticado ($(vercel whoami 2>/dev/null | tail -1))"
else
  warn "vercel CLI não autenticado" "vercel login — depois 'vercel link' (org team_Yj7YsH3ejoP3hlLyQivNVlS4, projeto tribultz). Não bloqueia deploys."
fi

echo
echo "=== 5. .env.prod local vs VM (fonte de verdade) ==========="
if [ ! -f .env.prod ]; then
  warn ".env.prod não existe aqui" "ssh -i $SSH_KEY $VM_USER@$VM_HOST 'sudo cat /opt/tribultz/.env' > .env.prod"
elif ! ssh -i "$SSH_KEY" -o BatchMode=yes -o ConnectTimeout=12 "$VM_USER@$VM_HOST" 'exit 0' 2>/dev/null; then
  warn "sem SSH — não dá para comparar com a VM"
else
  H=$(command -v md5sum >/dev/null && echo md5sum || echo "md5 -q")
  ssh -i "$SSH_KEY" -o BatchMode=yes "$VM_USER@$VM_HOST" \
    'sudo grep -E "^[A-Za-z_][A-Za-z0-9_]*=" /opt/tribultz/.env | while IFS="=" read -r k v; do v="${v%\"}"; v="${v#\"}"; printf "%s %s\n" "$k" "$(printf "%s" "$v" | md5sum | cut -c1-8)"; done' 2>/dev/null | sort > /tmp/_vm.$$
  grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env.prod | while IFS='=' read -r k v; do
    v="${v%\"}"; v="${v#\"}"; v="${v%$'\r'}"
    printf "%s %s\n" "$k" "$(printf "%s" "$v" | $H | cut -c1-8)"
  done | sort > /tmp/_lo.$$
  D=$(join /tmp/_vm.$$ /tmp/_lo.$$ 2>/dev/null | awk '$2!=$3' | wc -l | tr -d ' ')
  M=$(join -v1 /tmp/_vm.$$ /tmp/_lo.$$ 2>/dev/null | wc -l | tr -d ' ')
  if [ "$D" = "0" ] && [ "$M" = "0" ]; then
    ok "em sincronia com a VM ($(wc -l < /tmp/_vm.$$ | tr -d ' ') chaves)"
  else
    bad "drift: $D valores divergem, $M chaves da VM faltam aqui" "a VM é a fonte de verdade — puxe de lá, não copie de outra máquina"
    join -v1 /tmp/_vm.$$ /tmp/_lo.$$ 2>/dev/null | awk '{print "      falta: "$1}'
  fi
  rm -f /tmp/_vm.$$ /tmp/_lo.$$
fi

echo
echo "=== 6. Produção no ar ====================================="
C=$(code "$FRONTEND");     [ "$C" = "200" ] && ok "frontend $C" || bad "frontend $C"
C=$(code "$API/health");   [ "$C" = "200" ] && ok "api/health $C" || bad "api/health $C"

echo
echo "==========================================================="
echo -e "  ${GREEN}$PASS ok${NC} · ${YELLOW}$WARN aviso(s)${NC} · ${RED}$FAIL falha(s)${NC}"
[ "$FAIL" -gt 0 ] && echo -e "  ${DIM}Falhas em 1 ou 2 = você fica sem acesso operacional à infra.${NC}"
echo -e "  ${DIM}Avisos em 3 ou 4 não impedem deploy (é tudo server-side).${NC}"
echo
exit $([ "$FAIL" -gt 0 ] && echo 1 || echo 0)
