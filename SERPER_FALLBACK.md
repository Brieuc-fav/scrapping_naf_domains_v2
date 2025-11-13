# Système de Fallback pour l'API Serper

## Vue d'ensemble

Le script `build_esn_list.py` inclut maintenant un système de rotation automatique pour les clés API Serper. Ce système permet de gérer plusieurs clés API et de basculer automatiquement vers la suivante lorsqu'une clé atteint sa limite de quota (2500 requêtes par défaut).

## Configuration

### Méthode 1 : Fichier .env (Recommandé)

Créez ou modifiez votre fichier `.env` et ajoutez vos clés Serper numérotées :

```env
SERPER_API_KEY_1=votre_premiere_cle_ici
SERPER_API_KEY_2=votre_deuxieme_cle_ici
SERPER_API_KEY_3=votre_troisieme_cle_ici
SERPER_API_KEY_4=votre_quatrieme_cle_ici
```

### Méthode 2 : Format Legacy (Toujours supporté)

Si vous n'avez qu'une seule clé, vous pouvez utiliser l'ancien format :

```env
SERPER_API_KEY=votre_cle_unique
```

Le script détectera automatiquement le format et utilisera la clé disponible.

## Fonctionnement

### Rotation automatique

1. **Initialisation** : Le script charge toutes les clés API disponibles (SERPER_API_KEY_1, SERPER_API_KEY_2, etc.)
2. **Utilisation** : Les requêtes commencent avec la première clé (KEY_1)
3. **Détection de limite** : Quand une requête reçoit un code HTTP 429 (Too Many Requests), le script détecte que le quota est dépassé
4. **Rotation** : Le script passe automatiquement à la clé suivante (KEY_2, puis KEY_3, etc.)
5. **Logging** : Un message est affiché : `"Rotating to Serper API key #2"`

### Gestion des erreurs

Le système gère plusieurs types d'erreurs :

- **429 (Quota dépassé)** : Rotation automatique vers la clé suivante
- **Autres erreurs HTTP** : Message d'erreur affiché avec le code de statut
- **Exceptions réseau** : Tentative de rotation si disponible
- **Pas de clés disponibles** : Message d'erreur clair

## Capacité totale

Avec le système de rotation, votre capacité totale est :

- **1 clé** : 2 500 requêtes
- **2 clés** : 5 000 requêtes
- **3 clés** : 7 500 requêtes
- **4 clés** : 10 000 requêtes

## Suivi de l'utilisation

À la fin de l'exécution, le script affiche un résumé de l'utilisation :

```
============================================================
Serper API Usage Summary:
============================================================
  Key #1 (a1b2c3d4...xyz9): 2500 requests
  Key #2 (e5f6g7h8...abc1): 1234 requests
  Key #3 (i9j0k1l2...def2): 0 requests
  Key #4 (m3n4o5p6...ghi3): 0 requests
  Total requests: 3734
============================================================
```

Cela vous permet de :
- Vérifier combien de requêtes ont été effectuées avec chaque clé
- Identifier les clés qui ont atteint leur limite
- Planifier le renouvellement ou l'achat de nouvelles clés

## Extension du système

### Ajouter plus de 4 clés

Par défaut, le script supporte jusqu'à 4 clés API. Pour en ajouter plus :

1. Modifiez le code dans `build_esn_list.py` :

```python
# Cherchez cette ligne (environ ligne 70)
for i in range(1, 5):  # Support up to 4 keys

# Remplacez par (par exemple pour 10 clés)
for i in range(1, 11):  # Support up to 10 keys
```

2. Ajoutez les clés supplémentaires dans votre `.env` :

```env
SERPER_API_KEY_5=cinquieme_cle
SERPER_API_KEY_6=sixieme_cle
# ... etc
```

## Exemples d'utilisation

### Exemple 1 : Petite extraction avec 1 clé

```powershell
# .env contient seulement SERPER_API_KEY_1
python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 10 --outfile test.csv
```

### Exemple 2 : Grande extraction avec 4 clés

```powershell
# .env contient SERPER_API_KEY_1 à SERPER_API_KEY_4
python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A,71.12B --max-pages 100 --outfile large_extract.csv
```

Le script utilisera automatiquement toutes les clés disponibles en rotation.

## Bonnes pratiques

1. **Gardez vos clés en sécurité** : Ne commitez jamais le fichier `.env` dans Git
2. **Testez avec une clé** : Commencez avec une seule clé pour valider votre script
3. **Surveillez l'utilisation** : Vérifiez le résumé à la fin pour savoir quand renouveler
4. **Planifiez à l'avance** : Si vous savez que vous aurez besoin de > 2500 recherches, préparez plusieurs clés
5. **Utilisez des clés dédiées** : Évitez de partager les mêmes clés entre plusieurs scripts/projets

## Dépannage

### Problème : "No Serper API keys available"

**Solution** : Vérifiez que votre fichier `.env` contient au moins une clé :
```env
SERPER_API_KEY_1=votre_cle_ici
```

### Problème : Les rotations ne fonctionnent pas

**Causes possibles** :
1. Toutes les clés ont atteint leur limite
2. Les clés ne sont pas valides
3. Problème de réseau

**Solution** : Vérifiez les messages de log pour identifier quelle clé échoue et pourquoi.

### Problème : "Serper API returned status 401"

**Solution** : La clé API est invalide. Vérifiez que vous avez copié la clé correctement depuis le dashboard Serper.

## Migration depuis l'ancienne version

Si vous utilisiez l'ancienne version avec `--serper-key` en ligne de commande :

**Avant** :
```powershell
python .\build_esn_list.py --use-serper --serper-key ma_cle_ici
```

**Maintenant** :
```powershell
# 1. Ajoutez la clé dans .env
echo "SERPER_API_KEY_1=ma_cle_ici" >> .env

# 2. Lancez sans --serper-key
python .\build_esn_list.py --use-serper
```

L'argument `--serper-key` est maintenant déprécié mais reste compatible pour la transition.

## Support

Pour toute question ou problème avec le système de fallback :
1. Vérifiez les logs d'exécution
2. Consultez le résumé d'utilisation à la fin
3. Vérifiez votre fichier `.env`
4. Testez avec une seule clé d'abord
