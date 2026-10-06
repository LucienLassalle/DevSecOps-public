#!/usr/bin/env bash
# Création administrative des secrets sur une nouvelle VM ; jamais dans le runner.
set -euo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo "Exécuter avec sudo bash scripts/setup-app-secrets.sh." >&2; exit 1; }
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
command -v openssl >/dev/null
command -v python3 >/dev/null
k3s kubectl create namespace delivery --dry-run=client -o yaml | k3s kubectl apply -f -
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
if [[ -z $(k3s kubectl -n delivery get secret delivery-desk-secret --ignore-not-found -o name) ]]; then
  printf '%s' "$(openssl rand -hex 32)" > "$work/SECRET_KEY"
  k3s kubectl -n delivery create secret generic delivery-desk-secret \
    --from-file=SECRET_KEY="$work/SECRET_KEY"
else
  echo "Clé applicative existante conservée."
fi
if [[ -z $(k3s kubectl -n delivery get secret ghcr-access --ignore-not-found -o name) ]]; then
  read -rp "Utilisateur GitHub [Prateor] : " ghcr_user
  ghcr_user="${ghcr_user:-Prateor}"
  read -rsp "Token GitHub classique read:packages (saisie masquée) : " ghcr_token
  printf '\n'
  [[ -n "$ghcr_token" ]] || { echo "Token vide." >&2; exit 1; }
  # Le token n'apparaît ni dans les arguments du processus ni dans la sortie.
  printf '%s' "$ghcr_token" | python3 -c '
import base64, json, sys
user = sys.argv[1]
auth = base64.b64encode((user + ":" + sys.stdin.read()).encode()).decode()
json.dump({"auths": {"ghcr.io": {"auth": auth}}}, sys.stdout)
' "$ghcr_user" > "$work/dockerconfig.json"
  unset ghcr_token
  k3s kubectl -n delivery create secret generic ghcr-access \
    --type=kubernetes.io/dockerconfigjson \
    --from-file=.dockerconfigjson="$work/dockerconfig.json"
else
  echo "Accès GHCR existant conservé."
fi
