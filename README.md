# Delivery Desk

Application web de suivi des demandes de livraison, développée avec **Flask et SQLite**. Le dépôt inclut une chaîne GitHub Actions qui vérifie le code, recherche les vulnérabilités, construit une image Docker et peut la déployer sur Kubernetes.

## Fonctionnalités

- Création de demandes : application, version, environnement et description.
- Tableau de bord avec filtres et statuts « À préparer », « Prête » et « Livrée ».
- Historique des créations et changements de statut.
- Stockage SQLite persistant.
- Endpoints `/healthz` et `/readyz` pour vérifier le fonctionnement du service.

Les statuts sont renseignés manuellement : ils ne déclenchent pas le pipeline et ne représentent pas les résultats des scans. L'application ne dispose pas d'authentification ; toute personne ayant accès à l'interface peut consulter et modifier les demandes. Elle est destinée au développement et aux environnements de démonstration.

## Installation locale

Prérequis : Git et Python 3.12 ou 3.13.

```bash
git clone https://github.com/Prateor/DevSecOps.git
cd DevSecOps
```

### Linux et macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m flask --app wsgi run --host 127.0.0.1 --port 8000
```

### Windows — PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app wsgi run --host 127.0.0.1 --port 8000
```

Ouvrir [http://127.0.0.1:8000](http://127.0.0.1:8000). La base est créée dans `instance/delivery.db`. Arrêter le serveur avec `Ctrl+C`. Le serveur Flask sert au développement ; l'image Docker utilise Gunicorn.

## Docker Compose

Prérequis : Docker avec Compose et prise en charge des conteneurs Linux. Les commandes de génération de clé ci-dessous nécessitent aussi Python. Depuis la racine du dépôt, créer un fichier `.env` contenant une clé de session aléatoire.

Linux et macOS :

```bash
python3 -c 'import secrets; print("SECRET_KEY=" + secrets.token_hex(32))' > .env
docker compose up --build -d
```

Windows — PowerShell :

```powershell
python -c 'import secrets; print("SECRET_KEY=" + secrets.token_hex(32))' | Set-Content -LiteralPath .env -Encoding ascii
docker compose up --build -d
```

Si `.env` existe déjà, conserver sa clé au lieu de le recréer. Ce fichier est exclu de Git et ne doit pas être partagé.

L'interface est disponible sur [http://127.0.0.1:8000](http://127.0.0.1:8000). `docker compose logs -f app` affiche les logs ; `docker compose down` arrête le service et conserve les données. L'option `--volumes` supprime également la base.

## Configuration

| Variable | Description | Valeur par défaut |
| --- | --- | --- |
| `SECRET_KEY` | Signature des sessions et protection CSRF | Clé aléatoire à chaque démarrage |
| `DATABASE_PATH` | Chemin du fichier SQLite | `instance/delivery.db`, ou `/data/delivery.db` dans l'image |
| `COOKIE_SECURE` | Envoi du cookie uniquement via HTTPS | `false` |
| `APP_VERSION` | Version exposée par `/healthz` | `0.1.0` |

Utiliser une clé stable pour conserver les sessions après redémarrage. Définir `COOKIE_SECURE=true` pour un accès HTTPS ; la configuration Compose fournie utilise HTTP local.

## Tests

Après l'installation des dépendances :

```bash
# Linux et macOS
.venv/bin/python -m unittest discover -s tests -v
```

```powershell
# Windows
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les tests couvrent le fonctionnement de l'application, la validation des entrées, les protections CSRF, l'échappement HTML, les requêtes SQL et les contrôles des scripts de déploiement et de durcissement. Ils utilisent une base temporaire. Les tests des scripts Bash nécessitant Linux sont ignorés sous Windows ; ces tests ne déploient pas un cluster réel.

## Intégration continue

Le workflow [ci.yaml](.github/workflows/ci.yaml) exécute :

1. Lint, tests et analyse ZAP de l'application démarrée dans le runner.
2. Recherche de secrets avec Gitleaks et analyse SAST avec Semgrep.
3. Analyse des dépendances et des configurations Docker/Kubernetes avec Trivy.
4. Construction de l'image et analyse de ses vulnérabilités, après réussite des contrôles précédents.

Les rapports sont disponibles dans les artifacts des exécutions GitHub Actions. La [politique de sécurité](SECURITY-POLICY.md) définit les blocages.

Sur un push vers `main`, le workflow prévoit aussi une publication sur GHCR et un déploiement K3s par digest. **Ces étapes nécessitent une configuration propre à chaque installation.** Pour tester un fork, suivre [CONTRIBUTING.md](CONTRIBUTING.md), notamment les instructions concernant le runner et les jobs de livraison.

## Documentation

- [Contribuer et tester un fork](CONTRIBUTING.md)
- [Déployer l'application sur Kubernetes](DEPLOYMENT.md)
- [Installer, vérifier et maintenir le cluster K3s](CLUSTER.md)
- [Politique des contrôles de sécurité](SECURITY-POLICY.md)
- [Signaler une vulnérabilité](SECURITY.md)

## Organisation du dépôt

| Répertoire | Contenu |
| --- | --- |
| `app/` | Routes Flask, templates et styles |
| `tests/` | Tests automatisés |
| `scripts/` | Déploiement, administration et vérifications |
| `k8s/` | Manifests applicatifs, stockage et permissions |
| `infra/k3s/` | Version K3s et patches des composants système |
| `.semgrep/` | Règles SAST locales |
| `.github/workflows/` | Intégration continue et livraison |

## Limites

SQLite et la stratégie Kubernetes `Recreate` imposent une seule instance et une interruption lors des mises à jour.
L'historique ne contient pas d'identité utilisateur et n'est pas un journal d'audit immuable.
Un usage partagé nécessite notamment authentification, autorisations, HTTPS et sauvegardes.
**Les scans ne garantissent pas l'absence de vulnérabilités.**
