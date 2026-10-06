#!/usr/bin/env bash
# Test réel du stockage, indépendant du PVC delivery-data.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID -eq 0 ]] || { echo "Exécuter avec sudo bash scripts/test-cluster-storage.sh." >&2; exit 1; }
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
[[ -z $(k3s kubectl get namespace storage-check --ignore-not-found -o name) ]] || {
  echo "Le namespace storage-check existe déjà : examiner le test précédent avant de continuer." >&2
  exit 1
}
trap 'echo "Test interrompu : ressources conservées dans storage-check pour diagnostic." >&2' ERR
k3s kubectl apply -f k8s/storage-check.yaml
k3s kubectl -n storage-check wait --for=condition=Ready pod/storage-check --timeout=180s
k3s kubectl -n storage-check exec storage-check -- \
  sh -c 'echo "stockage OK" > /data/test.txt && test "$(cat /data/test.txt)" = "stockage OK"'
test_pv=$(k3s kubectl -n storage-check get pvc test-data -o jsonpath='{.spec.volumeName}')
[[ "$test_pv" =~ ^pvc-[a-z0-9-]+$ ]] || { echo "Nom du volume temporaire inattendu." >&2; exit 1; }
k3s kubectl -n storage-check delete pod storage-check
k3s kubectl -n storage-check delete pvc test-data
k3s kubectl wait --for=delete "pv/$test_pv" --timeout=180s
k3s kubectl delete namespace storage-check
echo "Stockage validé : création, écriture, lecture et suppression."
