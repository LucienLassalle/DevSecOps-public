#!/usr/bin/env bash
# Administration d'une VM Ubuntu mono-nœud, avec les chemins standard de K3s.
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
[[ $EUID -eq 0 ]] || { echo "Exécuter avec sudo bash scripts/setup-cluster.sh." >&2; exit 1; }
[[ $(uname -m) == x86_64 ]] || { echo "Cette procédure et le runner ciblent une VM x86_64." >&2; exit 1; }
for command in curl python3 systemctl; do command -v "$command" >/dev/null; done
version=$(tr -d '\r\n' < infra/k3s/VERSION)
if command -v k3s >/dev/null; then
  installed=$(k3s --version | head -n 1 | awk '{print $3}')
  [[ "$installed" == "$version" ]] || {
    echo "Version installée $installed ; version validée requise $version. Aucun changement." >&2
    exit 1
  }
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
backup="/var/lib/delivery-platform/backups/$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup" /etc/rancher/k3s/config.yaml.d
config=/etc/rancher/k3s/config.yaml.d/99-delivery-platform.yaml
[[ ! -f "$config" ]] || cp "$config" "$backup/config.yaml"
install -m 600 infra/k3s/config.yaml "$config"

if ! command -v k3s >/dev/null; then
  curl --fail --silent --show-error --location https://get.k3s.io -o "$work/install-k3s.sh"
  INSTALL_K3S_VERSION="$version" sh "$work/install-k3s.sh"
fi
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
for _ in $(seq 1 60); do
  if k3s kubectl get --raw=/readyz --request-timeout=5s >/dev/null 2>&1; then break; fi
  sleep 2
done
k3s kubectl wait --for=condition=Ready node --all --timeout=180s

# Les bases sont générées par cette VM : noms, IP DNS et configuration restent locaux.
manifests=/var/lib/rancher/k3s/server/manifests
sources=(coredns.yaml metrics-server/metrics-server-deployment.yaml local-storage.yaml)
bases=(coredns.yaml metrics-server.yaml local-storage.yaml)
for index in "${!sources[@]}"; do
  file="${sources[$index]}"
  [[ -s "$manifests/$file" ]] || {
    echo "Manifest K3s absent : $file. Vérifier les composants et les chemins standard." >&2
    exit 1
  }
  cp "$manifests/$file" "$work/${bases[$index]}"
  cp "$manifests/$file" "$backup/${bases[$index]}"
done
cp infra/k3s/overlay/*.yaml "$work/"
k3s kubectl kustomize "$work" > "$work/hardened.yaml"

# Vérifier le rendu avant de transférer la gestion des composants.
k3s kubectl create --dry-run=client --validate=false -f "$work/hardened.yaml" -o json \
  | python3 scripts/check_cluster_hardening.py
k3s kubectl apply --dry-run=server -f "$work/hardened.yaml" >/dev/null
target="$manifests/delivery-system-hardening.yaml"
[[ ! -f "$target" ]] || cp "$target" "$backup/previous-hardening.yaml"
for index in "${!sources[@]}"; do
  file="${sources[$index]}"
  [[ ! -f "$manifests/$file.skip" ]] || touch "$backup/${bases[$index]}.skip"
  touch "$manifests/$file.skip"
done
# Publication atomique : le contrôleur ne doit pas lire un fichier incomplet.
install -m 600 "$work/hardened.yaml" "$manifests/.delivery-hardening.tmp"
mv "$manifests/.delivery-hardening.tmp" "$target"
k3s kubectl apply -f "$target"
printf '%s\n' "$version" > /var/lib/delivery-platform/k3s-version
echo "Copie durcie installée. Sauvegarde administrative : $backup"
echo "Les bases K3s sont ignorées avec .skip ; leur mise à jour nécessite de relancer ce script."

# Vérification immédiate de la persistance au redémarrage du service.
systemctl restart k3s
bash scripts/verify-cluster.sh
