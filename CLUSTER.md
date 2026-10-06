# Administration du cluster K3s

Les scripts de ce dépôt préparent un serveur K3s et rendent persistants les réglages de sécurité de CoreDNS, Metrics Server et Local Path Provisioner. Cette administration est indépendante du déploiement applicatif.

## Environnement pris en charge

- Ubuntu avec systemd, architecture x86_64 et un utilisateur disposant de sudo.
- Un seul serveur K3s, avec les chemins de configuration et de données standard.
- Version K3s épinglée dans [infra/k3s/VERSION](infra/k3s/VERSION) : `v1.36.5+k3s1`.
- Accès réseau aux sources d'installation et aux registres d'images.

Les scripts ne gèrent pas les clusters multi-nœuds, les registres miroirs ou les chemins personnalisés via `--config`, `K3S_CONFIG_FILE` ou `--data-dir`. Une installation complète sur une VM vierge ne fait pas partie des tests automatisés ; la valider dans l'environnement cible.

## Installation et préparation

Sur le serveur :

```bash
sudo apt update
sudo apt install -y curl git openssl python3
git clone https://github.com/Prateor/DevSecOps.git
cd DevSecOps
sudo bash scripts/setup-cluster.sh
sudo bash scripts/test-cluster-storage.sh
```

Si K3s est absent, le script télécharge l'installateur officiel depuis `get.k3s.io` et demande la version du dépôt via `INSTALL_K3S_VERSION`. L'installateur lui-même est téléchargé au moment de l'exécution. Si K3s existe avec une autre version, le script refuse de continuer ; il ne réalise pas de mise à niveau.

Le script redémarre le service K3s. Sur un cluster existant, prévoir une fenêtre de maintenance sans livraison en cours.

## Configuration persistante

Le script `setup-cluster.sh` :

1. Ajoute `/etc/rancher/k3s/config.yaml.d/99-delivery-platform.yaml`, qui désactive Traefik et fixe les permissions du kubeconfig administrateur à `0600`.
2. Récupère les manifests système générés sur le serveur cible.
3. Applique les patches Kustomize de `infra/k3s/`, vérifie les images et les protections, puis effectue une validation côté serveur.
4. Ajoute des fichiers `.skip` aux trois manifests d'origine et installe la copie durcie dans `/var/lib/rancher/k3s/server/manifests/delivery-system-hardening.yaml`.
5. Redémarre K3s et lance les vérifications du cluster.

Les protections incluent des comptes non privilégiés, le profil seccomp `RuntimeDefault` et les paramètres de sécurité propres à chaque composant. Les permissions administratives restent nécessaires pour gérer les composants système ; elles ne sont pas attribuées à l'identité du déploiement applicatif.

Les fichiers `.skip` empêchent K3s de réappliquer les manifests d'origine sans supprimer leurs ressources. Les autres fichiers de Metrics Server, notamment son Service et ses droits, restent gérés par K3s. Ne pas désactiver CoreDNS, Metrics Server ou Local Storage avec `--disable` : cette option les désinstalle.

Examiner les options déjà passées au service et les modifications locales des manifests avant d'utiliser la procédure sur un cluster existant. La désactivation de Traefik convient au Service NodePort fourni ; elle ne convient pas à un cluster qui dépend déjà de cet ingress controller.

## Vérifications

```bash
sudo bash scripts/verify-cluster.sh
sudo bash scripts/test-cluster-storage.sh
```

Le premier script vérifie la version, les fichiers persistants, la disponibilité des composants et leurs contextes de sécurité. Il attend également la disponibilité des métriques. Si Delivery Desk est déployé, il teste son rollout, la résolution DNS depuis son Pod et `/readyz`.

Le second script crée un namespace `storage-check`, un PVC et un Pod temporaires, puis vérifie création, écriture, lecture et suppression du volume. Il refuse de réutiliser un namespace existant. En cas d'échec, les ressources sont conservées pour diagnostic.

Après un redémarrage du service ou du serveur, relancer ces deux scripts. Un délai d'initialisation de Metrics Server peut produire temporairement `Metrics API not available` ; la vérification doit finalement réussir.

Pour préparer les secrets et déployer l'application, poursuivre avec [DEPLOYMENT.md](DEPLOYMENT.md).

## Scan du cluster

Avec Trivy installé sur le serveur :

```bash
mkdir -p reports
sudo trivy k8s \
  --kubeconfig /etc/rancher/k3s/k3s.yaml \
  --scanners misconfig --skip-images --report all --format json \
  --output "$PWD/reports/trivy-cluster.json" \
  --timeout 15m
```

Ce scan recherche les mauvaises configurations du cluster, pas les vulnérabilités des images ou de l'OS. Il peut créer un Job de collecte sur le nœud ; ajouter `--disable-node-collector` pour désactiver cette collecte, avec une couverture réduite. Consulter la [documentation Trivy Kubernetes](https://trivy.dev/docs/latest/target/kubernetes/).

L'exemple produit un rapport sans imposer de seuil de blocage. Comparer les scans avec la même version de Trivy et en tenant compte des mises à jour de ses règles. Examiner séparément les workloads applicatifs et les ressources système, en particulier les permissions des ClusterRoles. Ne pas publier les rapports bruts sans vérifier les informations qu'ils contiennent.

## Mises à jour

Les `.skip` empêchent la mise à jour automatique des trois manifests concernés. Une évolution de K3s exige de revoir :

- `infra/k3s/VERSION` ;
- les images attendues dans `scripts/check_cluster_hardening.py` ;
- les patches Kustomize et les tests associés.

Le script de préparation refuse un changement de version sur un cluster existant. La mise à niveau de K3s doit donc être planifiée et réalisée séparément selon sa documentation, puis suivie de la préparation et des vérifications. Changer uniquement le numéro de version du dépôt ne suffit pas.

## Données et sauvegardes

Le script conserve une sauvegarde de configuration dans `/var/lib/delivery-platform/backups/DATE-PID`, accessible uniquement à root. Elle ne contient ni la base applicative ni une sauvegarde complète du cluster.

Les secrets, les kubeconfigs et les données SQLite ne sont pas versionnés. Sur un nouveau serveur, recréer les accès selon [DEPLOYMENT.md](DEPLOYMENT.md) et restaurer la base séparément si nécessaire. Le stockage `local-path` survit au redémarrage du serveur, mais pas à sa destruction. Une nouvelle clé de session invalide les sessions existantes.

## Retour aux composants d'origine

Cette opération retire le durcissement personnalisé et redémarre K3s. Depuis le serveur :

```bash
sudo mv /var/lib/rancher/k3s/server/manifests/delivery-system-hardening.yaml \
  /var/lib/delivery-platform/hardening-disabled.yaml
sudo rm -f /var/lib/rancher/k3s/server/manifests/coredns.yaml.skip \
  /var/lib/rancher/k3s/server/manifests/metrics-server/metrics-server-deployment.yaml.skip \
  /var/lib/rancher/k3s/server/manifests/local-storage.yaml.skip
sudo systemctl restart k3s
```

Ne pas supprimer manuellement l'AddOn durci ni ses ressources pour ce retour arrière. Vérifier ensuite les composants, le DNS, les métriques et le stockage. Cette opération ne réactive pas Traefik ; sa désactivation reste définie dans le fichier de configuration complémentaire.

Références : [composants K3s et fichiers .skip](https://docs.k3s.io/installation/packaged-components), [configuration K3s](https://docs.k3s.io/installation/configuration), [Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/).
