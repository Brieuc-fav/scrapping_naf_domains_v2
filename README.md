# ESN candidate builder (France)

Pipeline pour produire une liste priorisée d’entreprises probablement ESN / SSII (placement de consultants) en combinant SIRENE + signaux web + scoring.

## Ce que fait le script

- Extrait des établissements via l’API publique SIRENE V3 (entreprise.data.gouv.fr) selon des préfixes NAF (ex: 62*, 71*, 70*, 78*).
- Dé-duplique au niveau SIREN (entreprise).
- Devine le site web (si non présent) via heuristiques sur la raison sociale et vérifie l’existence.
- Récupère la homepage et quelques pages candidats (services, careers, jobs…) et recherche des mots-clés pertinents.
- Calcule un score de probabilité ESN / placement.
- Exporte un CSV trié par score.

## Installation (Windows / PowerShell)

- Python 3.10+ recommandé.
- Dépendances (installées automatiquement par l’environnement ci-dessus) :
  - requests, beautifulsoup4, tldextract, pandas, python-dotenv

Vous pouvez aussi installer depuis `requirements.txt`:

```powershell
# Optionnel si vous voulez gérer l’env localement
C:/Users/brieu/AppData/Local/Programs/Python/Python310/python.exe -m pip install -r requirements.txt
```

## Usage rapide

Exécuter un “smoke test” (quelques dizaines d’entrées max) :

```powershell
C:/Users/brieu/AppData/Local/Programs/Python/Python310/python.exe .\build_esn_list.py --naf-codes 62 --max-pages 1 --per-page 50 --outfile .\esn_candidates_sample.csv --sleep 0.8
```

Exécuter une passe ciblée sur des codes NAF précis (exacts):

```powershell
C:/Users/brieu/AppData/Local/Programs/Python/Python310/python.exe .\build_esn_list.py --naf-codes 62.02A,71.12B --max-pages 50 --per-page 100 --outfile .\esn_candidates.csv --sleep 0.6
```

Paramètres utiles:
- `--naf-codes`: codes NAF exacts (ex: 62.02A, 71.12B) ou préfixes (ex: 62, 71) séparés par des virgules.
- `--min-emp` / `--max-emp`: borne heuristique de taille.
- `--exclude-over-emp`: exclusion dure des très grandes entreprises selon la tranche Sirene (par défaut 2000). Mettre `-1` pour désactiver.
- `--per-page` / `--max-pages`: pagination API (cap par préfixe NAF).
- `--sleep`: temporisation entre appels pour la politesse.
- `--outfile`: chemin du CSV de sortie.

### Mode Recherche d’entreprises (conseillé pour le ciblage)

L’API Recherche d’entreprises (ouverte, 7 req/s) offre des filtres utiles (NAF, code postal, effectifs, etc.). Activez-la avec `--use-recherche`:

```powershell
C:/Users/brieu/AppData/Local/Programs/Python/Python310/python.exe .\build_esn_list.py --use-recherche --naf-codes 62.02A,71.12B --max-pages 2 --per-page 25 --outfile .\esn_recherche_sample.csv --sleep 0.6
```

Notes:
- `per_page` est limité à 25 par l’API; le script ajuste automatiquement si vous passez une valeur supérieure.
- Nous filtrons localement les tranches d’effectif à 0 par défaut. Pour inclure ces entreprises, ajoutez `--include-zero-employees`.
- Par défaut, les entreprises au-dessus de 2000 salariés (d’après la tranche Sirene) sont exclues; ajustez avec `--exclude-over-emp`.
- Vous pouvez combiner avec le web scan et SerpAPI comme d’habitude.

### Mode INSEE (clé API publique ou OAuth2)

1) Créez un fichier `.env` (déjà présent) avec, au choix:

```
# Option A: Clé API publique INSEE (recommandé selon votre portail)
SIRENE_API_KEY=<votre_cle_api>

# Option B: OAuth2 (si vous disposez de l’URL token et que le mode est actif)
SIRENE_CLIENT_ID=<votre_client_id>
SIRENE_CLIENT_SECRET=<votre_client_secret>
```

2) Lancez le script avec `--use-insee` (il utilisera automatiquement la clé API ou les identifiants du `.env`).
  Vous pouvez aussi préciser l’URL du token et la base API si nécessaire (le portail INSEE a récemment migré certains endpoints) via flags ou variables d’environnement:

Variables d’environnement optionnelles:

```
SIRENE_TOKEN_URL=https://<nouvelle-url-token>
SIRENE_API_BASE=https://api.insee.fr/api-sirene/3.11
```

```powershell
## Avec clé API publique
```powershell
C:/Users/brieu/AppData/Local/Programs/Python/Python310/python.exe .\build_esn_list.py --use-insee --naf-codes 62.02A,71.12B --max-pages 2 --per-page 100 --outfile .\esn_insee_sample.csv --sleep 0.7
```

## Avec OAuth2 (si disponible)
```powershell
C:/Users/brieu/AppData/Local/Programs/Python/Python310/python.exe .\build_esn_list.py --use-insee --insee-token-url https://<nouvelle-url-token> --insee-base https://api.insee.fr/api-sirene/3.11 --naf-codes 62 --max-pages 2 --per-page 100 --outfile .\esn_insee_sample.csv --sleep 0.7
```

# Exemple avec URLs fournies explicitement (si besoin):
# C:/Users/brieu/AppData/Local/Programs/Python/Python310/python.exe .\build_esn_list.py --use-insee --insee-token-url https://<nouvelle-url-token> --insee-base https://api.insee.fr/api-sirene/3.11 --naf-codes 62 --max-pages 2 --per-page 100 --outfile .\esn_insee_sample.csv --sleep 0.7
```

Le script essaie dans l’ordre: INSEE (si activé) → entreprise.data.gouv.fr → fallback recherche-entreprises. Le quota INSEE par défaut: ~30 appels/min.

### Recherche du site avec SerpAPI (optionnel)

Pour améliorer la détection du site, vous pouvez activer SerpAPI (Google):

1) Ajoutez votre clé dans `.env`:

```
SERPAPI_KEY=<votre_cle_serpapi>
```

2) Lancez avec `--use-serpapi` (le script essaiera d’abord SerpAPI avec la raison sociale, puis l’heuristique locale):

```powershell
C:/Users/brieu/AppData/Local/Programs/Python/Python310/python.exe .\build_esn_list.py --use-insee --use-serpapi --naf-codes 62 --max-pages 2 --per-page 50 --outfile .\esn_sites_serpapi.csv --sleep 0.7
```

Notes:
- Le domaine détecté est stocké dans la colonne `site` et la source dans `site_source` (serpapi | guess | api).
- Le script vérifie la homepage et scanne quelques pages candidates pour repérer des mots-clés pertinents.

### Recherche du site avec serper.dev (alternative à SerpAPI)

Vous pouvez utiliser serper.dev à la place de SerpAPI.

**Configuration avec plusieurs clés API (fallback automatique)**

Le script supporte maintenant plusieurs clés API Serper avec rotation automatique. Lorsqu'une clé atteint sa limite de 2500 requêtes, le système passe automatiquement à la clé suivante.

1) Ajoutez vos clés dans `.env` (jusqu'à 4 clés ou plus) :

```
# Méthode recommandée : plusieurs clés numérotées
SERPER_API_KEY_1=votre_premiere_cle_serper
SERPER_API_KEY_2=votre_deuxieme_cle_serper
SERPER_API_KEY_3=votre_troisieme_cle_serper
SERPER_API_KEY_4=votre_quatrieme_cle_serper

# Méthode legacy (encore supportée) : une seule clé
# SERPER_API_KEY=votre_cle_serper
```

2) Lancez avec `--use-serper` :

```powershell
C:/Users/brieu/AppData/Local/Programs/Python/Python310/python.exe .\build_esn_list.py --use-recherche --use-serper --naf-codes 62.02A,71.12B --per-page 25 --max-pages 2 --outfile .\esn_recherche_sites_serper.csv --sleep 0.6
```

**Fonctionnement du système de rotation :**
- Le script utilise les clés dans l'ordre (KEY_1, KEY_2, KEY_3, KEY_4)
- Quand une clé reçoit une erreur 429 (quota dépassé), le script passe automatiquement à la clé suivante
- Vous pouvez suivre l'utilisation dans les logs : "Rotating to Serper API key #2", etc.
- Avec 4 clés de 2500 requêtes chacune, vous pouvez faire jusqu'à 10 000 recherches au total

Notes:
- `site_source` prendra la valeur `serper` quand le domaine vient de serper.dev.
- Vous pouvez combiner `--use-serper` et `--use-serpapi`; les deux seront tentés avant l'heuristique.
- Le système de rotation est transparent : aucun changement n'est nécessaire dans vos commandes

## Scoring (par défaut)
- NAF ciblé: +3
- Mot-clé dans raison sociale: +2
- Mot-clé trouvé sur site: +3
- Présence d’indications d’offres/“jobs”: +4
- Taille (tranche présente / 10–500 typique): +2

Seuils suggérés:
- Score ≥ 7: fortement probable ESN / placement de consultants
- Score ≥ 4: possible

## Conseils pratiques
- Démarrez avec `--max-pages 3` pour un échantillon, vérifiez ~30–50 entrées à la main, puis ajustez les mots-clés/NAF/seuils.
- L’API publique a des quotas. Fractionnez en plusieurs lancements (batchs/jours) si vous ciblez des milliers d’entrées.
- L’heuristique de domaine est simple; pour une meilleure couverture, pensez à des services tiers (Clearbit, Hunter, SERP API… payants).
- Pour détecter les offres, le script scanne la homepage + quelques URLs candidates; étendez si nécessaire.

## Sortie
CSV avec colonnes: `siren, nom, nom_complet_annuaire, naf, tranche_effectif, site, site_source, score, naf_ok, name_keyword_found, site_keyword_found, job_posting_present, size_ok, score_pertinence, pertinent_for_clustor, signals`.
Note: `nom_complet_annuaire` provient de l’API Recherche d’entreprises quand elle est utilisée (champ "nom_complet" tel qu’affiché sur Annuaire des Entreprises). Il peut être vide pour d’autres sources.

## Dépannage
- Si vous obtenez 0 résultats, vérifiez la connectivité réseau (pare-feu/SSL) et essayez plus tard. Vous pouvez aussi augmenter `--max-pages` ou tester d’autres préfixes NAF.
- En cas de limitation (429), augmentez `--sleep`.
- Si certains sites ne sont pas détectés, peaufinez l’heuristique ou complétez manuellement.
