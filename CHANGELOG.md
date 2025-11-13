# 🎯 Système de Fallback Multi-Clés Serper API - Résumé des Modifications

## ✅ Modifications Apportées

### 1. Code Principal (`build_esn_list.py`)

#### Nouvelles Variables Globales
```python
# Support de plusieurs clés API Serper (jusqu'à 4 par défaut)
SERPER_API_KEYS = []  # Liste de toutes les clés chargées
CURRENT_SERPER_KEY_INDEX = 0  # Index de la clé actuellement utilisée
SERPER_KEY_USAGE = {}  # Compteur d'utilisation par clé
```

#### Nouvelles Fonctions
- `get_next_serper_key()` : Récupère la clé API actuellement active
- `rotate_serper_key()` : Effectue la rotation vers la clé suivante
- `print_serper_usage_summary()` : Affiche un résumé de l'utilisation à la fin

#### Fonction Modifiée
- `serper_find_domain()` : 
  - Accepte maintenant `api_key=None` pour utiliser le système de rotation
  - Détecte automatiquement les erreurs 429 (quota dépassé)
  - Effectue la rotation automatique vers la clé suivante
  - Gère les erreurs avec retry automatique

### 2. Configuration

#### Nouveau Format de Clés dans `.env`
```env
# Nouveau format recommandé (jusqu'à 4 clés)
SERPER_API_KEY_1=votre_premiere_cle
SERPER_API_KEY_2=votre_deuxieme_cle
SERPER_API_KEY_3=votre_troisieme_cle
SERPER_API_KEY_4=votre_quatrieme_cle

# Format legacy (toujours supporté)
SERPER_API_KEY=votre_cle_unique
```

### 3. Documentation

#### Nouveaux Fichiers Créés
1. **`.env.example`** : Template de configuration avec toutes les clés API
2. **`SERPER_FALLBACK.md`** : Documentation technique complète du système
3. **`GUIDE_RAPIDE.md`** : Guide de démarrage rapide en français
4. **`test_serper_fallback.py`** : Script de test du système de fallback
5. **`CHANGELOG.md`** : Ce fichier (résumé des modifications)

#### Fichiers Mis à Jour
- **`README.md`** : Section "Recherche du site avec serper.dev" entièrement réécrite avec les nouvelles instructions

## 🚀 Nouvelles Fonctionnalités

### 1. Rotation Automatique
- Détection automatique du dépassement de quota (HTTP 429)
- Basculement transparent vers la clé suivante
- Messages de log clairs : `"Rotating to Serper API key #2"`

### 2. Suivi d'Utilisation
- Compteur de requêtes par clé
- Résumé affiché en fin d'exécution
- Masquage partiel des clés pour la sécurité

### 3. Capacité Étendue
- **1 clé** : 2 500 requêtes
- **2 clés** : 5 000 requêtes  
- **3 clés** : 7 500 requêtes
- **4 clés** : 10 000 requêtes
- **Extensible** : Modifiable pour supporter plus de clés

### 4. Gestion d'Erreurs Améliorée
- Retry automatique avec la clé suivante
- Messages d'erreur détaillés
- Fallback gracieux si toutes les clés sont épuisées

## 📊 Impact sur l'Utilisation

### Avant (Version Précédente)
```powershell
# Une seule clé, 2500 requêtes max
python .\build_esn_list.py --use-serper --serper-key MA_CLE --naf-codes 62.02A
# ❌ S'arrête après 2500 entreprises
```

### Après (Nouvelle Version)
```powershell
# Configuration dans .env avec 4 clés
python .\build_esn_list.py --use-serper --naf-codes 62.02A,71.12B --max-pages 100
# ✅ Peut traiter jusqu'à 10 000 entreprises automatiquement
```

## 🔄 Compatibilité

### Rétrocompatibilité Complète
- ✅ L'ancien format `SERPER_API_KEY` fonctionne toujours
- ✅ L'argument `--serper-key` est toujours accepté (déprécié)
- ✅ Le comportement par défaut reste inchangé avec une seule clé

### Migration Recommandée
```bash
# Ancien .env
SERPER_API_KEY=ma_cle

# Nouveau .env (recommandé)
SERPER_API_KEY_1=ma_cle
SERPER_API_KEY_2=nouvelle_cle_2
SERPER_API_KEY_3=nouvelle_cle_3
SERPER_API_KEY_4=nouvelle_cle_4
```

## 🧪 Tests

### Script de Test Fourni
```powershell
python .\test_serper_fallback.py
```

Vérifie :
- ✅ Chargement correct des clés depuis .env
- ✅ Import et initialisation du module
- ✅ Fonctionnement de la rotation
- ✅ Signature des fonctions modifiées

## 📈 Exemple de Sortie

### Pendant l'Exécution
```
[1/100] Processing SIREN 123456789 - EXEMPLE SSII
   Rotating to Serper API key #2
[2/100] Processing SIREN 987654321 - AUTRE ESN
...
```

### À la Fin
```
============================================================
Serper API Usage Summary:
============================================================
  Key #1 (sk-abc12...xyz9): 2500 requests
  Key #2 (sk-def34...uvw8): 2500 requests
  Key #3 (sk-ghi56...rst7): 1234 requests
  Key #4 (sk-jkl78...opq6): 0 requests
  Total requests: 6234
============================================================
```

## 🛠️ Extensibilité

### Ajouter Plus de 4 Clés

1. Modifier `build_esn_list.py` (ligne ~70) :
```python
# Était : for i in range(1, 5)
# Devient (pour 10 clés) :
for i in range(1, 11):
```

2. Ajouter dans `.env` :
```env
SERPER_API_KEY_5=...
SERPER_API_KEY_6=...
# etc.
```

## 📝 Checklist de Migration

- [ ] Créer/mettre à jour le fichier `.env` avec les nouvelles clés
- [ ] Copier `.env.example` vers `.env` si nécessaire
- [ ] Tester avec `python test_serper_fallback.py`
- [ ] Lancer un petit test : `--max-pages 1`
- [ ] Vérifier le résumé d'utilisation en fin d'exécution
- [ ] Lancer votre extraction complète

## 🎓 Ressources

### Documentation
1. **Démarrage rapide** : Lire `GUIDE_RAPIDE.md`
2. **Documentation technique** : Consulter `SERPER_FALLBACK.md`
3. **Configuration** : Voir `.env.example`
4. **Tests** : Utiliser `test_serper_fallback.py`

### Commandes Utiles
```powershell
# Tester la configuration
python .\test_serper_fallback.py

# Petit test avec rotation
python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 5 --outfile test.csv

# Extraction complète avec 4 clés (10 000 requêtes)
python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A,71.12B --max-pages 100 --outfile full_extract.csv
```

## 🔒 Sécurité

### Bonnes Pratiques Implémentées
- ✅ Fichier `.env` exclu de Git (via `.gitignore`)
- ✅ Clés masquées dans les logs (affichage partiel uniquement)
- ✅ Exemple `.env.example` sans vraies clés
- ✅ Documentation claire sur la protection des clés

### À Faire de Votre Côté
- ⚠️ Ne jamais commiter le fichier `.env`
- ⚠️ Ne jamais partager vos clés API publiquement
- ⚠️ Utiliser des clés dédiées par projet si possible
- ⚠️ Révoquer et régénérer les clés en cas de fuite

## 🐛 Dépannage

### Problèmes Courants et Solutions

| Symptôme | Cause | Solution |
|----------|-------|----------|
| "No Serper API keys available" | Pas de clé dans .env | Ajouter `SERPER_API_KEY_1=...` dans .env |
| Rotation ne se déclenche pas | Une seule clé configurée | Ajouter d'autres clés (_2, _3, _4) |
| "429 Too Many Requests" continu | Toutes les clés épuisées | Ajouter plus de clés ou attendre le renouvellement |
| "401 Unauthorized" | Clé invalide | Vérifier la clé sur serper.dev/dashboard |
| Tests échouent | Module non trouvé | Vérifier que vous êtes dans le bon dossier |

## 📞 Support

En cas de problème :
1. Consulter `GUIDE_RAPIDE.md` pour les bases
2. Lire `SERPER_FALLBACK.md` pour les détails techniques
3. Exécuter `python test_serper_fallback.py` pour diagnostiquer
4. Vérifier les logs d'exécution du script principal
5. Consulter le résumé d'utilisation en fin d'exécution

## 🎉 Conclusion

Le système de fallback multi-clés Serper API est maintenant opérationnel !

**Bénéfices** :
- ✅ Capacité multipliée par le nombre de clés
- ✅ Rotation automatique sans intervention
- ✅ Suivi détaillé de l'utilisation
- ✅ Rétrocompatibilité totale
- ✅ Extensible facilement

**Prochaines étapes recommandées** :
1. Tester avec une petite extraction
2. Vérifier le résumé d'utilisation
3. Ajuster le nombre de clés selon vos besoins
4. Lancer vos extractions complètes en toute confiance !

---
*Date de création : Novembre 2025*
*Version : 2.0 - Système de Fallback Multi-Clés*
