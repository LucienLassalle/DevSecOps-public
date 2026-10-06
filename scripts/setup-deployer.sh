#!/usr/bin/env bash
# Exécuter comme l'utilisateur du runner (quentin), sans sudo devant bash.
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."

sudo k3s kubectl get namespace delivery >/dev/null
sudo k3s kubectl -n delivery apply -f k8s/storage.yaml -f k8s/service.yaml
sudo k3s kubectl apply -f k8s/ci-access.yaml

# Identifiant local persistant pour ce laboratoire. Le supprimer en fin de projet.
sudo k3s kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: delivery-ci-token
  namespace: delivery
  annotations:
    kubernetes.io/service-account.name: delivery-ci
type: kubernetes.io/service-account-token
EOF

token=""
for _ in $(seq 1 30); do
  token=$(sudo k3s kubectl -n delivery get secret delivery-ci-token \
    -o jsonpath='{.data.token}' | base64 --decode)
  if [[ -n "$token" ]]; then break; fi
  sleep 1
done
[[ -n "$token" ]] || { echo "Le jeton Kubernetes n'a pas été généré." >&2; exit 1; }
ca=$(sudo k3s kubectl -n delivery get secret delivery-ci-token \
  -o jsonpath='{.data.ca\.crt}')
[[ -n "$ca" ]] || { echo "Certificat Kubernetes absent." >&2; exit 1; }

mkdir -p "$HOME/.kube"
config="$HOME/.kube/delivery-ci.yaml"
cat > "$config" <<EOF
apiVersion: v1
kind: Config
clusters:
  - name: local-k3s
    cluster:
      server: https://127.0.0.1:6443
      certificate-authority-data: $ca
users:
  - name: delivery-ci
    user:
      token: $token
contexts:
  - name: delivery
    context:
      cluster: local-k3s
      user: delivery-ci
      namespace: delivery
current-context: delivery
EOF
chmod 600 "$config"
unset token ca
export KUBECONFIG="$config"
kubectl -n delivery get deployments
echo "Accès du runner prêt : $config (ne pas partager ce fichier)."
