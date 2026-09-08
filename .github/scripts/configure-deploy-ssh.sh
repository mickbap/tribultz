#!/usr/bin/env bash
set -euo pipefail

# SEC-07: instala a identidade do cliente e a referência de host previamente
# confiável. A chave apresentada pela rede nunca alimenta known_hosts.

SSH_DIR="${SSH_DIR:-${HOME}/.ssh}"

if [ -z "${SSH_KEY:-}" ]; then
  echo "Chave privada SSH de deploy ausente." >&2
  exit 1
fi
if [ -z "${SSH_HOST:-}" ]; then
  echo "Host SSH de deploy ausente." >&2
  exit 1
fi
if [ -z "${SSH_KNOWN_HOSTS:-}" ]; then
  echo "Referência confiável do host SSH ausente." >&2
  exit 1
fi

umask 077
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

private_key_file="$SSH_DIR/id_ed25519"
known_hosts_file="$SSH_DIR/known_hosts"
private_key_tmp="$SSH_DIR/.id_ed25519.tmp"
known_hosts_tmp="$SSH_DIR/.known_hosts.tmp"
trap 'rm -f "$private_key_tmp" "$known_hosts_tmp"' EXIT

printf '%s\n' "$SSH_KEY" > "$private_key_tmp"
printf '%s\n' "$SSH_KNOWN_HOSTS" > "$known_hosts_tmp"
chmod 600 "$private_key_tmp" "$known_hosts_tmp"

if ! ssh-keygen -l -f "$known_hosts_tmp" >/dev/null 2>&1; then
  echo "Referência confiável do host SSH é inválida." >&2
  exit 1
fi
if ! ssh-keygen -F "$SSH_HOST" -f "$known_hosts_tmp" >/dev/null 2>&1; then
  echo "Referência confiável não contém o host SSH solicitado." >&2
  exit 1
fi

mv "$private_key_tmp" "$private_key_file"
mv "$known_hosts_tmp" "$known_hosts_file"
echo "Identidade de deploy e referência confiável do host SSH instaladas."
