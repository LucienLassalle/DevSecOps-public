# Déploiement Kubernetes

Ce guide décrit le déploiement de Delivery Desk sur un serveur K3s Linux x86_64. Pour un essai sans Kubernetes, utiliser [Docker Compose](README.md#docker-compose).

## Prérequis

- Cluster préparé selon [CLUSTER.md](CLUSTER.md), avec une StorageClass par défaut.
- Commandes `kubectl`, `curl`, `openssl` et `python3` disponibles sur le serveur.
- Image applicative publiée sur GHCR et identifiée par son digest SHA-256.
- Compte local disposant de `sudo` pour la préparation administrative.

Les commandes ci-dessous s'exécutent depuis la racine du dépôt, sur le serveur K3s. Les exemples entre chevrons sont à remplacer par les valeurs de votre installation.

## Préparer les secrets et les accès

```bash
sudo bash scripts/setup-app-secrets.sh
bash scripts/setup-deployer.sh
```

Le premier script crée le namespace `delivery` et les secrets :

| Secret | Usage |
| --- | --- |
| `delivery-desk-secret` | Clé de session applicative générée aléatoirement |
| `ghcr-access` | Identifiants de téléchargement de l'image GHCR |

Il conserve les secrets existants. Saisir le compte GitHub ayant accès à l'image et un token classique avec `read:packages` lorsque le script les demande. Pour un fork, remplacer le compte proposé par défaut. La visibilité du package GHCR est indépendante de celle du dépôt ; le script fourni prépare un accès authentifié même pour un package public. Ne jamais enregistrer de token dans Git.

Le second script s'exécute **sans `sudo` devant `bash`**, sous le compte qui effectuera les déploiements. Il prépare le PVC, le Service NodePort, les permissions Kubernetes et le kubeconfig `~/.kube/delivery-ci.yaml`, protégé par des permissions `600`.

Vérifier les droits :

```bash
KUBECONFIG="$HOME/.kube/delivery-ci.yaml" kubectl auth can-i patch deployments -n delivery
KUBECONFIG="$HOME/.kube/delivery-ci.yaml" kubectl auth can-i patch services -n delivery
KUBECONFIG="$HOME/.kube/delivery-ci.yaml" kubectl auth can-i get secrets -n delivery
KUBECONFIG="$HOME/.kube/delivery-ci.yaml" kubectl auth can-i get nodes
```

Les résultats attendus sont respectivement `yes`, `no`, `no`, `no`. L'identité peut mettre à jour les Deployments et lire les diagnostics dans `delivery`. Elle ne possède pas de droit direct de lecture des Secrets ; la modification des workloads reste toutefois un accès sensible, car ceux-ci peuvent utiliser des secrets.

Le kubeconfig contient un token persistant : le conserver uniquement sur le serveur. Pour révoquer cet accès, supprimer le Secret `delivery-ci-token` et le RoleBinding `delivery-ci` dans le namespace `delivery`.

## Déployer une image

Récupérer la référence immuable dans le résumé du job de publication ou dans les métadonnées du package GHCR :

```bash
bash scripts/deploy.sh 'ghcr.io/<proprietaire>/<depot>@sha256:<digest-de-64-caracteres>'
```

Le script remplace l'image du manifest dans un fichier temporaire, applique uniquement le Deployment, attend sa disponibilité et vérifie le digest ainsi que `/readyz` et `/healthz`. Ne pas appliquer directement `k8s/app.yaml` : son image est un emplacement réservé au script.

Le kubeconfig peut être remplacé avec la variable `DELIVERY_KUBECONFIG`. Le script doit s'exécuter sur le serveur : les vérifications HTTP utilisent `127.0.0.1:30080`.

```bash
sudo k3s kubectl -n delivery get pods,svc,pvc
curl --fail http://127.0.0.1:30080/readyz
```

Depuis un navigateur, ouvrir `http://<adresse-du-serveur>:30080`. Le Service expose le port sur le réseau du serveur ; limiter son accès au réseau de test. L'installation fournie n'ajoute ni HTTPS ni authentification.

La base est conservée dans le PVC `delivery-data`. Un seul replica et la stratégie `Recreate` sont utilisés : une interruption est attendue lors d'une mise à jour. Une erreur de rollout ou de disponibilité fait échouer le script ; il n'y a pas de retour arrière automatique.

## Livraison avec GitHub Actions

Le workflow fourni prévoit la séquence suivante :

```text
Tests et scans → construction → scan image → publication GHCR → déploiement K3s
```

Les jobs `publication` et `deployment` s'exécutent uniquement sur un push vers `main`, après réussite des contrôles. Une pull request, un push vers une autre branche ou un lancement manuel exécutent les contrôles sans publier ni déployer. L'image analysée est transférée à la publication sans reconstruction ; son digest est transmis au déploiement. L'artifact `rapport-deploiement` conserve les traces du job.

### Runner et dépôt public

**Ne pas connecter un runner permanent contenant l'accès au cluster à un dépôt public ouvert aux contributions.** Une pull request peut modifier le workflow pour demander ce runner ; la condition `push/main` du workflow actuel n'est pas une frontière de sécurité. GitHub recommande d'éviter les runners autohébergés pour les dépôts publics : voir [Secure use of GitHub Actions](https://docs.github.com/en/actions/reference/security/secure-use).

Pour un fork destiné aux tests, supprimer les jobs `publication` et `deployment` du workflow avant un push sur `main`, et conserver les contrôles sur les runners hébergés par GitHub. Pour automatiser une livraison, utiliser un dépôt de déploiement privé réservé aux personnes de confiance, avec un processus explicite de transfert et de validation du digest. Cette séparation n'est pas implémentée dans le workflow fourni.

Dans cet environnement privé, le job de déploiement attend les labels `self-hosted`, `linux`, `x64` et `delivery-k3s`. Configurer le runner selon la [documentation GitHub](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners), sous le même compte local que celui utilisé pour `setup-deployer.sh`, puis installer son service depuis le dossier du runner :

```bash
sudo ./svc.sh install "$(id -un)"
sudo ./svc.sh start
sudo ./svc.sh status
```

Ne pas lancer `config.sh` avec `sudo`. Un seul runner de déploiement doit porter ces labels pour cette installation. Le runner n'a pas à exécuter les scripts d'administration du cluster.

## Diagnostic

```bash
sudo k3s kubectl -n delivery get pods,svc,pvc
sudo k3s kubectl -n delivery get events --sort-by=.metadata.creationTimestamp
sudo k3s kubectl -n delivery logs deployment/delivery-desk --tail=100
sudo k3s kubectl -n delivery describe deployment delivery-desk
```

| Symptôme | Vérification |
| --- | --- |
| `ImagePullBackOff` | Référence de l'image, accès au package et Secret `ghcr-access` |
| PVC `Pending` | StorageClass par défaut et disponibilité du provisioner |
| Rollout en échec | Événements, logs, probes et accès à `/data` |
| Job de déploiement en attente | Disponibilité et labels du runner dans l'environnement privé |
| Interface inaccessible | État du Service NodePort, adresse du serveur et règles réseau |

Retirer les identifiants et les données sensibles avant de partager des logs.
