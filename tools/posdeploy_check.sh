#!/usr/bin/env bash
# Verificação de pós-deploy do Tribultz — uso do Owner e do Techlead.
#
# Confere, em ordem: saúde dos subsistemas, containers na VM, todas as rotas
# públicas, todas as rotas da área logada, se a API protegida exige auth (e não
# devolve 5xx), e a integridade do feed público do changelog.
#
# Sai com código 0 quando tudo passa e com o número de falhas caso contrário —
# então serve tanto para ler na tela quanto para encadear em outro comando.
#
# Uso:  bash tools/posdeploy_check.sh "rótulo do que acabou de subir"
#
# Requer: curl, python3 e acesso SSH à VM (host `tribultz-vm`). Sem o SSH, a
# seção de containers falha e o resto continua valendo.
set -uo pipefail
SITE="https://tribultz.com.br"
API="https://api.tribultz.com.br"
FALHAS=0
ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
bad()  { printf "  \033[31m✗\033[0m %s\n" "$1"; FALHAS=$((FALHAS+1)); }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; }

echo "=== PÓS-DEPLOY ${1:-} · $(TZ=America/Sao_Paulo date '+%d/%m %H:%M:%S') ==="

echo "-- 3. Infraestrutura e dependências --"
H=$(curl -s -m 30 "$API/health/deep")
if [ -z "$H" ]; then bad "health/deep sem resposta"; else
  ST=$(printf '%s' "$H" | python3 -c "import sys,json;print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
  [ "$ST" = "ok" ] && ok "health/deep status=ok" || bad "health/deep status=$ST"
  printf '%s' "$H" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for k,v in d.items():
    if k in ('status','latency_ms'): continue
    print(('  \033[32m✓\033[0m ' if v in ('ok','unconfigured') else '  \033[31m✗\033[0m ')+f'{k}={v}')
" 2>/dev/null
fi

echo "-- Containers na VM --"
ssh -o ConnectTimeout=20 tribultz-vm 'cd /opt/tribultz && sudo docker compose -f infra/docker-compose.prod.yml ps --format "{{.Service}} {{.Status}}"' 2>/dev/null | while read -r l; do
  case "$l" in *"Up"*) printf "  \033[32m✓\033[0m %s\n" "$l";; *) printf "  \033[31m✗\033[0m %s\n" "$l";; esac
done

echo "-- 4a. Rotas públicas --"
for r in "" pricing register login contato data-policy diagnostico calculadora classificacao simulador compliance split-payment changelog blog privacy terms lgpd cookies refund-policy founding-partners; do
  C=$(curl -s -o /dev/null -m 25 -w "%{http_code}" "$SITE/$r")
  [ "$C" = "200" ] && ok "/$r → $C" || bad "/$r → $C"
done

echo "-- 4b. Rotas da área logada (devem servir a casca, não 5xx) --"
for r in dashboard validate-xml validate-sped audit closing jobs report settings documents credits billing support exceptions feedback select-mode admin; do
  C=$(curl -s -o /dev/null -m 25 -w "%{http_code}" "$SITE/$r")
  [ "$C" = "200" ] && ok "/$r → $C" || bad "/$r → $C"
done

echo "-- 4c. API: pública responde, protegida exige auth (não 5xx) --"
C=$(curl -s -o /dev/null -m 25 -w "%{http_code}" "$API/api/v1/news"); [ "$C" = "200" ] && ok "GET /news → 200" || bad "GET /news → $C"
C=$(curl -s -o /dev/null -m 25 -w "%{http_code}" "$API/api/v1/public/data-policy"); [ "$C" = "200" ] && ok "GET /public/data-policy → 200" || bad "GET /public/data-policy → $C"
for p in "documents" "jobs" "credits/balance" "billing/me"; do
  C=$(curl -s -o /dev/null -m 25 -w "%{http_code}" "$API/api/v1/$p")
  case "$C" in 401|403) ok "GET /$p → $C (protegida)";; 5*) bad "GET /$p → $C (erro de servidor)";; *) warn "GET /$p → $C";; esac
done

echo "-- Feed do changelog --"
curl -s -m 25 "$API/api/v1/news" | python3 -c "
import sys,json
from collections import Counter
d=json.load(sys.stdin); c=Counter((x['title'],x['category']) for x in d)
dup=sum(1 for v in c.values() if v>1)
print(('  \033[32m✓\033[0m ' if dup==0 else '  \033[31m✗\033[0m ')+f'{len(d)} entradas, {dup} duplicatas')
" 2>/dev/null || bad "feed ilegível"

echo "=== $( [ $FALHAS -eq 0 ] && printf '\033[32mAPROVADO\033[0m' || printf "\033[31m%s FALHA(S)\033[0m" $FALHAS ) ==="
exit $FALHAS
