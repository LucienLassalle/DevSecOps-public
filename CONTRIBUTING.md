# Contribuer

Les corrections, améliorations de documentation et retours de test sont les bienvenus. Pour une vulnérabilité, suivre [SECURITY.md](SECURITY.md) plutôt que publier les détails dans une issue.

## Tester le projet

Pour découvrir l'application, suivre l'[installation locale ou Docker Compose](README.md). Kubernetes et un runner autohébergé ne sont pas nécessaires pour ces essais.

Pour signaler un bug, ouvrir une issue avec :

- les étapes de reproduction ;
- le résultat attendu et le résultat obtenu ;
- le commit testé, le système et le mode de lancement ;
- les logs utiles, sans identifiants ni données sensibles.

## Travailler dans un fork

1. Créer un fork et le cloner.
2. Créer une branche de travail à partir de `main`.
3. Effectuer les changements et lancer les tests locaux.
4. Activer GitHub Actions dans le fork si nécessaire, puis pousser la branche.
5. Ouvrir une pull request avec une description du problème, des changements et des vérifications effectuées.

Le workflow utilise le nom du dépôt courant pour publier sur GHCR. Un push vers `main` dans un fork peut donc publier un package puis attendre un runner de déploiement. **Avant ce type de push, supprimer les jobs `publication` et `deployment` de la copie du workflow si vous souhaitez uniquement tester la CI.** Les pushes sur les autres branches et les lancements manuels ne publient ni ne déploient.

Ne pas connecter un runner permanent ayant accès à un cluster au fork public. Consulter les [conditions d'utilisation du runner](DEPLOYMENT.md#runner-et-dépôt-public) pour un déploiement automatisé dans un environnement privé.

## Vérifications locales

Exécuter la suite décrite dans [README.md](README.md#tests). Pour reproduire le contrôle de code sous Linux :

```bash
.venv/bin/python -m pip install ruff
.venv/bin/ruff check --select E9,F63,F7,F82 .
for script in scripts/*.sh; do
  bash -n "$script"
done
```

Sous Windows, installer Ruff avec `.\.venv\Scripts\python.exe -m pip install ruff`, puis lancer `.\.venv\Scripts\ruff.exe check --select E9,F63,F7,F82 .`. Les scripts Bash et leurs tests Linux sont également vérifiés dans GitHub Actions.

Ajouter des tests lorsque le changement introduit un comportement ou corrige un bug. Mettre à jour la documentation lorsque l'installation, la configuration ou l'utilisation change.

## Tester les contrôles bloquants

Effectuer les essais de sécurité dans votre propre fork et sur vos propres instances. Ne pas utiliser de vrais secrets ni viser une infrastructure sans autorisation.

Pour vérifier le blocage IaC :

1. Créer une branche de test.
2. Ajouter temporairement `privileged: true` au `securityContext` du conteneur applicatif dans `k8s/app.yaml`.
3. Pousser cette branche et consulter GitHub Actions.
4. Vérifier l'échec du job IaC et l'absence de construction, publication et déploiement.
5. Supprimer le défaut après le test ; ne pas le fusionner dans la branche principale.

Les seuils des autres contrôles sont décrits dans [SECURITY-POLICY.md](SECURITY-POLICY.md). Un échec attendu sert à vérifier le blocage ; un échec technique du scanner nécessite un diagnostic distinct.

## Préparer une pull request

Garder une portée claire et décrire les vérifications effectuées. Éviter les fichiers générés, les bases SQLite, les rapports contenant des informations sensibles, les kubeconfigs et les tokens. Les contributions doivent conserver le fonctionnement des contrôles de sécurité.
