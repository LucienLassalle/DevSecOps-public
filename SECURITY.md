# Sécurité

## Périmètre

Les signalements peuvent concerner l'application, les manifests, les scripts et les workflows de la branche `main`. Tester sur le dernier commit pour vérifier si le problème est toujours présent. Aucun engagement de maintenance n'est défini pour les anciennes révisions.

Delivery Desk est une application de démonstration sans authentification ni gestion de rôles. Les statuts et l'historique sont manuels. L'installation fournie utilise HTTP local ; elle ne constitue pas une configuration prête pour une exposition publique.

## Signaler une vulnérabilité

Si le signalement privé est activé sur GitHub, ouvrir **Security → Advisories → Report a vulnerability** dans le dépôt. Voir la [procédure GitHub](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately).

Si cette option n'est pas disponible, ouvrir une issue demandant un canal privé de signalement, sans publier le détail de la vulnérabilité, un exploit ou des identifiants.

Un signalement utile contient :

- le commit et le composant concernés ;
- les conditions nécessaires et les étapes de reproduction ;
- l'impact observé ;
- une correction proposée, si disponible.

Utiliser des données fictives. Ne pas joindre de secrets, de tokens, de kubeconfigs ou de données personnelles. Aucun délai de réponse garanti n'est défini.

## Essais de sécurité

Tester uniquement sur vos propres instances ou dans un périmètre explicitement autorisé. Pour vérifier les blocages de la CI, suivre [CONTRIBUTING.md](CONTRIBUTING.md#tester-les-contrôles-bloquants). Les rapports des scanners sont des éléments de diagnostic ; leur absence de détection ne prouve pas l'absence de vulnérabilités.

Les secrets doivent rester dans les variables locales ou les Secrets Kubernetes. Le fichier `.env` et les kubeconfigs ne doivent pas être commités. Un runner disposant d'identifiants de déploiement nécessite l'isolation expliquée dans [DEPLOYMENT.md](DEPLOYMENT.md#runner-et-dépôt-public).

Les seuils de blocage du pipeline sont définis dans [SECURITY-POLICY.md](SECURITY-POLICY.md).
