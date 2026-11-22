# 🍓 Fruits Story — Autopilot gratuit (Drive → FFmpeg → Cloudinary → Buffer)

**État : code prêt à installer, non activé.** Aucune publication n'est créée tant que la variable `PUBLISH_ENABLED` n'est pas définie sur `true` et que les comptes ne sont pas autorisés.

## Ce que fait le projet

1. Chaque matin, GitHub Actions recherche de nouveaux clips dans **01 — Clips à monter**, dans ton Drive.
2. Il attend une paire complète : `FRUITS_EP014_A.mp4` et `FRUITS_EP014_B.mp4`, puis 15, 16, etc.
3. FFmpeg assemble A puis B, uniformise le format **MP4 H.264 / 1080 × 1920 / 30 fps**, conserve l'audio (ajoute du silence si nécessaire).
4. Il héberge la vidéo MP4 sur Cloudinary, afin de fournir un lien public direct et stable à Buffer.
5. Il programme un **Reel Instagram**, une **vidéo TikTok** et un **YouTube Short** pour **15 h heure de Paris**, avec une déclaration de contenu IA sur les trois réseaux.
6. La file Buffer est remplie progressivement, au maximum à **9 publications en attente par compte** (plan Buffer Free : 10 par compte). Les publications passées libèrent de la place.
7. À chaque exécution, il lit les publications Buffer et évite de créer deux fois le même épisode sur le même réseau. Les erreurs sont signalées dans les journaux GitHub Actions.

**Important :** aucun épisode inédit après le 13 n'est actuellement présent dans le dossier Drive. Ce projet ne fabrique pas automatiquement les scénarios, les personnages ni les nouveaux clips. Il automatise le montage et la programmation des clips que tu fournis.

## Configuration nécessaire (une fois)

### 1. Créer les comptes gratuits

- **Buffer** : https://buffer.com/ — connecter Instagram, TikTok et YouTube, puis créer une **clé API personnelle** dans les réglages API. Sur Free, 3 réseaux, 10 publications en attente **par réseau** (et pas par mois).
- **Cloudinary** : https://cloudinary.com/ — créer un compte gratuit et trouver la valeur `CLOUDINARY_URL` (ressemble à `cloudinary://API_KEY:API_SECRET@CLOUD_NAME`). La garder secrète.
- **GitHub** : compte déjà connecté à ChatGPT, mais **aucun dépôt n'existait au moment de la préparation**.

### 2. Google Drive — partage de dossier à une identité technique

1. Dans Google Cloud Console, créer un projet, activer **Google Drive API**, créer un **service account** (compte de service) et télécharger **sa clé JSON**. Conserver la clé privée, jamais dans le chat ni dans le dépôt.
2. Dans Google Drive, partager le dossier `🍓 Séries Fruits — Automatisation` (ou au minimum `01 — Clips à monter`) avec l'adresse `client_email` indiquée dans ce JSON, en **Lecteur**. Vérifier que le service account voit les clips contenus dans le dossier.
3. Placer le contenu complet du JSON dans le secret de dépôt GitHub `GOOGLE_SERVICE_ACCOUNT_JSON`.

Le script n'a besoin que d'un **accès en lecture** et ne modifie pas les clips Drive. L'export final est hébergé sur Cloudinary, pas réinjecté dans Drive. Si Google Cloud bloque la création de clés de service account, il faudra remplacer ce connecteur par une autorisation OAuth utilisateur.

### 3. Installer le projet sur GitHub

1. Créer un dépôt **privé** nommé `fruits-story-autopilot` sur https://github.com/new. Choisir *privé* pour ne pas rendre les identifiants de dossiers ou fichiers visibles publiquement.
2. Décompresser l'archive de ce projet et y ajouter tous les fichiers, y compris le dossier caché `.github/workflows/`.
3. Dans les paramètres du dépôt : **Settings → Secrets and variables → Actions**.
4. Ajouter les **trois secrets** : `GOOGLE_SERVICE_ACCOUNT_JSON`, `BUFFER_API_KEY`, `CLOUDINARY_URL`.
5. Dans **Variables**, ajouter `PUBLISH_ENABLED=false` pour commencer en simulation.
6. Ouvrir **Actions → Fruits Story - Montage et publications → Run workflow** et consulter les journaux. La simulation ne publie rien.
7. Quand les trois comptes Buffer sont bien connectés et les tests réussis, passer **`PUBLISH_ENABLED=true`**. Le workflow se lance ensuite automatiquement chaque jour.

La connexion GitHub à ChatGPT ne donne pas automatiquement la possibilité de créer un nouveau dépôt, ni d'installer une clé API tierce. Ces autorisations initiales demandent ton intervention.

### 4. Ajouter les futurs épisodes

Dans le dossier Drive `01 — Clips à monter`, déposer **exactement deux fichiers** par épisode, dans l'ordre :

- `FRUITS_EP014_A.mp4`
- `FRUITS_EP014_B.mp4`
- `FRUITS_EP015_A.mp4`
- `FRUITS_EP015_B.mp4`

La première date cible est **8 décembre 2026 à 15 h**, et la numérotation commence à **14**. Si la mise en route se produit plus tard, les épisodes non encore programmés sont placés aux prochaines dates libres, toujours à 15 h. Si le montage d'un épisode est incomplet, les suivants ne sont pas programmés, pour préserver l'ordre de l'histoire.

### 5. Adapter les titres (optionnel)

`captions.json` peut contenir :

```json
{
  "14": {
    "title": "La nouvelle aventure commence",
    "description": "Un nouveau personnage arrive... 🍓"
  },
  "15": {
    "title": "La suite de l'histoire",
    "description": "La tension monte..."
  }
}
```

Sans fichier descriptif, une description **générique** est employée pour ne pas inventer l'histoire de nouveaux épisodes.

## Limitations et points de vigilance

- **Gratuit ≠ illimité** : Buffer Free = 10 publications en attente par canal, renouvelables après publication ; Cloudinary Free = un budget mensuel de crédits de stockage/transformation/bande passante ; GitHub Actions Free = minutes incluses. Les quotas et conditions peuvent changer.
- **Ce n'est pas une faille de Metricool** : c'est un autre service officiel avec une file renouvelable. Rien n'est publié via Metricool par ce projet, et son calendrier n'est pas modifié.
- **Aucun contournement des API sociales** : si un canal impose une validation, une reconnexion, ou refuse la publication automatique, il faut corriger la connexion.
- **Vidéos visibles publiquement** : les URLs Cloudinary sont publiques par nécessité technique pour Buffer. Ne pas y héberger de contenu confidentiel.
- **Droits d'auteur** : utiliser uniquement les musiques, images et clips que tu peux publier. Vérifier `youtube_made_for_kids` dans `config.json` selon le public visé : `false` est un réglage initial à confirmer avant activation, pas une conclusion juridique sur ton contenu.
- **Anti-doublons** : chaque légende contient le marqueur visible `#FruitsEP014`, `#FruitsEP015`, etc. Le programme lit les publications Buffer déjà programmées ou envoyées pour ne pas les reproduire sur Buffer. Il ne peut pas inspecter les anciennes publications Metricool, raison pour laquelle la première vidéo autorisée est le numéro **14**, après les épisodes déjà programmés jusqu'au 7 décembre.
- **Horaires GitHub** : les déclencheurs automatiques GitHub Actions peuvent être retardés. La stratégie consiste à programmer plusieurs jours à l'avance dans Buffer, donc un petit retard n'affecte généralement pas une vidéo déjà programmée.
- **Épisode en erreur** : si Buffer signale un statut `error`, le programme le marque comme traité pour éviter de publier un doublon sans diagnostic. Vérifier manuellement et supprimer/corriger la publication avant de relancer.
- **Montages Drive** : l'export est disponible sur Cloudinary ; aucune copie finale n'est envoyée automatiquement dans le dossier Drive `02 — Vidéos prêtes`. Ajouter cette fonction nécessiterait une autorisation Drive en écriture via OAuth de l'utilisateur.
- **Activation** : une vraie publication de test est indispensable. Aucun succès de test réseau n'est affirmé tant que les clés et les canaux personnels ne sont pas en place.

## Commandes locales

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
# Définir GOOGLE_SERVICE_ACCOUNT_JSON + BUFFER_API_KEY pour un vrai essai de lecture
PUBLISH_ENABLED=false python autopilot.py
# ATTENTION : cette commande programme de vraies publications (lorsqu'il existe de nouveaux clips) :
PUBLISH_ENABLED=true python autopilot.py
```

## Sources officielles

- https://buffer.com/pricing
- https://developers.buffer.com/guides/getting-started.html
- https://developers.buffer.com/guides/posts-and-scheduling.html
- https://developers.buffer.com/examples/create-video-post.html
- https://developers.buffer.com/types/InstagramPostMetadataInput.html
- https://developers.buffer.com/types/TikTokPostMetadataInput.html
- https://developers.buffer.com/types/YoutubePostMetadataInput.html
- https://cloudinary.com/pricing
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
