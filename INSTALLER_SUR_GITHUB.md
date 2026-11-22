# Installation dans ton dépôt GitHub

Dépôt : https://github.com/Arcol889/fruits-story-autopilot

## Méthode via navigateur (ordinateur conseillé)

1. Télécharge `Fruits_Story_GitHub_Pret_A_Importer.zip`, puis **décompresse-le**.
2. Sur GitHub, ouvre ton dépôt et **Add file > Upload files** : https://github.com/Arcol889/fruits-story-autopilot/upload/main
3. Dépose les fichiers ET le répertoire caché `.github` depuis le dossier décompressé à la racine du dépôt (il ne faut PAS uploader le ZIP tel quel).
4. Appuie sur **Commit changes**.
5. Dans Settings > General > Danger Zone > Change repository visibility, choisis **Private** (important : ton dépôt est public actuellement).
6. Crée un compte Buffer, connecte Instagram, TikTok et YouTube. Crée une clé API Buffer.
7. Crée un compte Cloudinary et récupère CLOUDINARY_URL.
8. Crée une identité technique Google Cloud avec accès Drive en lecture et autorise-la à lire le dossier `01 — Clips à monter`.
9. Dans Settings > Secrets and variables > Actions > Secrets : ajoute `GOOGLE_SERVICE_ACCOUNT_JSON`, `BUFFER_API_KEY`, `CLOUDINARY_URL`.
10. Dans la section Variables, ajoute `PUBLISH_ENABLED=false` pour commencer en simulation.
11. Déclenche Actions > Fruits Story - Montage et publications > Run workflow. Vérifie les journaux.
12. Après avoir ajouté FRUITS_EP014_A.mp4 et FRUITS_EP014_B.mp4 dans Google Drive et vérifié les trois réseaux, active `PUBLISH_ENABLED=true`.

Ne communique jamais les clés ou le contenu JSON dans ChatGPT. Ne mets jamais ces secrets dans les fichiers du dépôt.

## État constaté le 22 novembre 2026

- Dépôt GitHub créé et lisible, mais le connecteur ChatGPT a refusé l’écriture (`403 Resource not accessible by integration`).
- Tous les fichiers sont présents dans cette archive, non installés sur GitHub.
- Six tests unitaires locaux ont réussi. Les intégrations réelles Buffer, Google Drive en compte de service et Cloudinary **ne sont pas encore testées**.
- Aucune publication automatique n’a été lancée et aucune publication Metricool n’a été modifiée.
- Le système ne crée pas de nouveaux scénarios ou clips IA, il assemble les clips A/B fournis.

Remarque : le plan Buffer gratuit permet 10 publications programmées en attente par canal (places renouvelées après publication). Les quotas gratuits de GitHub Actions et Cloudinary restent applicables. Le résultat de l’autopublication dépend des permissions et restrictions propres aux réseaux.
