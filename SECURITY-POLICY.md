# Politique des contrôles de sécurité

Cette politique décrit les seuils appliqués par [.github/workflows/ci.yaml](.github/workflows/ci.yaml). Pour signaler une vulnérabilité, consulter [SECURITY.md](SECURITY.md).

## Contrôles bloquants

| Contrôle | Condition de blocage | Résultats conservés sans blocage |
| --- | --- | --- |
| Lint et tests | Échec d'une vérification | — |
| Gitleaks | Détection d'un secret | — |
| Semgrep | Correspondance d'une règle locale de `.semgrep/rules.yaml`, notamment l'interdiction de `eval()` | Détections des règles du registre non reprises dans les règles locales |
| Trivy — dépendances | Vulnérabilité HIGH ou CRITICAL | UNKNOWN, LOW et MEDIUM |
| Trivy — image | Vulnérabilité HIGH ou CRITICAL, même sans correctif disponible | UNKNOWN, LOW et MEDIUM |
| Trivy — configurations | Mauvaise configuration HIGH ou CRITICAL | UNKNOWN, LOW et MEDIUM |
| ZAP | Alerte de risque élevé dans le rapport | Risques moyen, faible et informatif |
| Exécution des contrôles | Erreur technique empêchant le scan ou l'exploitation du rapport requis | — |

Semgrep produit un rapport complet puis exécute séparément les règles locales bloquantes. Sa sévérité `ERROR` n'est pas une équivalence de HIGH ou CRITICAL chez Trivy.

ZAP utilise un scan Baseline avec analyse passive. Le contrôle Python du rapport détermine le blocage selon le risque ; les catégories WARN/FAIL du Baseline ne définissent pas ce seuil. Ce scan ne remplace pas un test d'intrusion ou une analyse active complète.

Les résultats non bloquants restent à examiner. Les rapports disponibles sont conservés dans les artifacts GitHub Actions ; leur absence après une erreur ne constitue pas une réussite du contrôle.

## Publication et déploiement

La construction dépend de la réussite des contrôles du code, des secrets, des dépendances et de l'IaC. La publication dépend aussi de la réussite du scan de l'image. Les jobs de publication et de déploiement sont limités aux pushes sur `main` dans le workflow fourni.

L'image publiée est celle qui a été analysée, sans reconstruction. Son tag contient le SHA du commit ; le déploiement utilise son digest immuable. Un échec de rollout ou des vérifications HTTP fait échouer la livraison, sans retour arrière automatique.

Ces dépendances de jobs ne configurent pas les règles de fusion du dépôt. Les mainteneurs doivent définir séparément les contrôles requis sur la branche principale dans les paramètres GitHub.

Les contrôles utilisent des runners hébergés par GitHub. Le job de déploiement prévoit un runner autohébergé ; sa configuration nécessite l'isolation décrite dans [DEPLOYMENT.md](DEPLOYMENT.md#runner-et-dépôt-public) avant un usage avec un dépôt public.

## Audit du cluster

Le scan du cluster en fonctionnement est distinct du scan IaC des fichiers du dépôt. La procédure est décrite dans [CLUSTER.md](CLUSTER.md#scan-du-cluster). Les permissions système doivent être évaluées selon leurs usages et leurs attributions ; elles ne doivent pas être supprimées ou ignorées globalement pour rendre le rapport vert.

Le durcissement des composants système est administré séparément du déploiement applicatif. Les fichiers `.skip` transfèrent la gestion de trois manifests à la copie durcie ; une mise à jour K3s exige de revoir cette configuration et de renouveler les vérifications.
