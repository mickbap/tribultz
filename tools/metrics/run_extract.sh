#!/usr/bin/env bash
# Query pack v1 — Cockpit de Unit Economics (ORD-QA-002 / ORD-DADOS-001).
#
# Roda as 5 queries deste diretório contra o Postgres de produção via SSH na
# VM (nunca expõe a porta do banco localmente) e traz o resultado como CSV
# para reports/metrics/ (gitignored — dado de produção nunca vai pro git).
#
# Uso: bash tools/metrics/run_extract.sh
# Pré-requisito: chave SSH autorizada na VM (ver docs/infra/secrets_inventory.md).

set -euo pipefail

VM_HOST="ubuntu@201.54.20.18"
SSH_KEY="$HOME/.ssh/id_ed25519"
REMOTE_DIR="/tmp/qa_extract_$(date +%Y%m%d%H%M%S)"
LOCAL_DIR="reports/metrics/$(date +%Y-%m)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$LOCAL_DIR"
ssh -i "$SSH_KEY" "$VM_HOST" "mkdir -p $REMOTE_DIR"
scp -i "$SSH_KEY" "$SCRIPT_DIR"/q*.sql "$VM_HOST:$REMOTE_DIR/"

ssh -i "$SSH_KEY" "$VM_HOST" bash -s "$REMOTE_DIR" << 'REMOTE'
set -e
cd "$1"
DB_URL=$(sudo grep "^DATABASE_URL=" /opt/tribultz/.env | cut -d= -f2- | sed 's/postgresql+psycopg2:/postgresql:/')
for f in q1_mrr q2_churn q3_retencao q4_ativacao q5_consumo; do
  psql "$DB_URL" -v ON_ERROR_STOP=1 --csv -f "${f}.sql" -o "${f}.csv" 2>"${f}.err" \
    && echo "OK: ${f} — $(($(wc -l < "${f}.csv") - 1)) linha(s)" \
    || { echo "FALHOU: ${f}"; cat "${f}.err"; exit 1; }
done
REMOTE

scp -i "$SSH_KEY" "$VM_HOST:$REMOTE_DIR/*.csv" "$LOCAL_DIR/"
ssh -i "$SSH_KEY" "$VM_HOST" "rm -rf $REMOTE_DIR"

echo "Extrato salvo em $LOCAL_DIR/ (fora do git — reports/ é gitignored)."
