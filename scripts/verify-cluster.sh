#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID -eq 0 ]] || { echo "Exécuter avec sudo bash scripts/verify-cluster.sh." >&2; exit 1; }
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
expected=$(tr -d '\r\n' < infra/k3s/VERSION)
installed=$(k3s --version | head -n 1 | awk '{print $3}')
[[ "$installed" == "$expected" ]] || { echo "Version K3s différente du dépôt." >&2; exit 1; }
for file in coredns.yaml metrics-server/metrics-server-deployment.yaml local-storage.yaml; do
  [[ -f "/var/lib/rancher/k3s/server/manifests/$file.skip" ]]
done
[[ -s /var/lib/rancher/k3s/server/manifests/delivery-system-hardening.yaml ]]
for _ in $(seq 1 60); do
  if k3s kubectl get --raw=/readyz --request-timeout=5s >/dev/null 2>&1; then break; fi
  sleep 2
done
k3s kubectl wait --for=condition=Ready node --all --timeout=180s
for deployment in coredns metrics-server local-path-provisioner; do
  k3s kubectl -n kube-system rollout status "deployment/$deployment" --timeout=180s
done
k3s kubectl -n kube-system get deployments coredns metrics-server local-path-provisioner -o json \
  | python3 scripts/check_cluster_hardening.py
[[ -z $(k3s kubectl -n kube-system get deployment traefik --ignore-not-found -o name) ]] || {
  echo "Traefik est encore présent. Vérifier les options --disable et la configuration K3s." >&2
  exit 1
}
for _ in $(seq 1 30); do
  if k3s kubectl top nodes; then break; fi
  sleep 2
done
k3s kubectl top nodes >/dev/null
# Sur une nouvelle VM, l'application sera préparée ensuite avec setup-deployer.sh.
if [[ -n $(k3s kubectl -n delivery get deployment delivery-desk --ignore-not-found -o name) ]]; then
  k3s kubectl -n delivery rollout status deployment/delivery-desk --timeout=180s
  k3s kubectl -n delivery exec deployment/delivery-desk -- \
    python -c 'import socket; print(socket.gethostbyname("kubernetes.default.svc.cluster.local"))'
  curl --fail --silent --show-error --retry 5 --retry-connrefused \
    --max-time 10 http://127.0.0.1:30080/readyz
fi
printf '\nCluster vérifié après redémarrage.\n'
