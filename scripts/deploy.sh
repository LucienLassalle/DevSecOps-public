#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

image="${1:?Fournir une image GHCR avec son digest}"
if [[ ! "$image" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]]; then
  echo "Référence invalide : une image GHCR avec digest sha256 est requise." >&2
  exit 1
fi
export KUBECONFIG="${DELIVERY_KUBECONFIG:-$HOME/.kube/delivery-ci.yaml}"
[[ -r "$KUBECONFIG" ]] || { echo "Exécuter scripts/setup-deployer.sh sur la VM." >&2; exit 1; }
command -v kubectl >/dev/null
command -v curl >/dev/null

manifest=$(mktemp)
trap 'rm -f "$manifest"' EXIT
placeholder='image: ghcr.io/prateor/devsecops:deployed-by-ci'
[[ $(grep -cF "$placeholder" k8s/app.yaml) -eq 1 ]] || {
  echo "Le manifest doit contenir exactement une image à remplacer." >&2
  exit 1
}
sed "s|$placeholder|image: $image|" k8s/app.yaml > "$manifest"
kubectl -n delivery apply -f "$manifest"
kubectl -n delivery rollout status deployment/delivery-desk --timeout=180s
actual=$(kubectl -n delivery get deployment delivery-desk \
  -o jsonpath='{.spec.template.spec.containers[0].image}')
[[ "$actual" == "$image" ]] || { echo "L'image déployée ne correspond pas à l'image publiée." >&2; exit 1; }
curl --fail --silent --show-error --retry 5 --retry-connrefused --retry-delay 2 \
  --max-time 10 http://127.0.0.1:30080/readyz
curl --fail --silent --show-error --max-time 10 http://127.0.0.1:30080/healthz
kubectl -n delivery get pods,svc,pvc
printf '\nImage déployée : %s\n' "$image"
