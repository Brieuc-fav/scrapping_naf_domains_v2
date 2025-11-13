# Guide Rapide : Configuration Multi-Clés Serper API

## Configuration en 3 étapes

### 1. Créer ou modifier votre fichier .env

Ouvrez (ou créez) le fichier `.env` dans le même dossier que le script et ajoutez vos clés :

```env
SERPER_API_KEY_1=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SERPER_API_KEY_2=sk-yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
SERPER_API_KEY_3=sk-zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
SERPER_API_KEY_4=sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

**Important** : 
- Remplacez les `sk-xxxxx...` par vos vraies clés API Serper
- Vous pouvez ajouter de 1 à 4 clés (ou plus si vous modifiez le code)
- Ne partagez JAMAIS votre fichier .env publiquement

### 2. Tester la configuration

Lancez le script de test pour vérifier que tout fonctionne :

```powershell
python .\test_serper_fallback.py
```

Vous devriez voir :
```
🎉 Tous les tests sont passés!
→ Vous pouvez utiliser le système de fallback en toute confiance
```

### 3. Utiliser le script avec rotation automatique

Lancez votre extraction normalement avec `--use-serper` :

```powershell
python .\build_esn_list.py --use-recherche --use-serper --naf-codes 62.02A,71.12B --max-pages 50 --outfile resultats.csv
```

Le script utilisera automatiquement toutes vos clés en rotation !

## Que faire si une clé est épuisée ?

**Rien !** Le script gère tout automatiquement :

1. La clé #1 traite les 2500 premières requêtes
2. Quand elle atteint la limite, vous verrez : `Rotating to Serper API key #2`
3. La clé #2 prend le relais pour les 2500 requêtes suivantes
4. Et ainsi de suite...

## Vérifier l'utilisation

À la fin de l'exécution, un résumé s'affiche :

```
============================================================
Serper API Usage Summary:
============================================================
  Key #1 (sk-abc12...xyz9): 2500 requests
  Key #2 (sk-def34...uvw8): 1432 requests
  Key #3 (sk-ghi56...rst7): 0 requests
  Key #4 (sk-jkl78...opq6): 0 requests
  Total requests: 3932
============================================================
```

## FAQ

### Q : Combien de clés dois-je créer ?

**R :** Calculez selon vos besoins :
- Nombre d'entreprises à traiter × ~1 requête par entreprise
- Divisez par 2500 (limite par clé)
- Arrondissez au supérieur

Exemple : 8000 entreprises → 8000/2500 = 3.2 → **4 clés minimum**

### Q : Que se passe-t-il si toutes mes clés sont épuisées ?

**R :** Le script continue mais sans utiliser Serper. Il utilisera l'heuristique de base pour deviner les domaines.

### Q : Puis-je mélanger des clés gratuites et payantes ?

**R :** Oui ! Le script ne fait pas de distinction. Il les utilisera dans l'ordre.

### Q : Comment savoir combien de crédits il me reste ?

**R :** 
1. Consultez votre dashboard Serper : https://serper.dev/dashboard
2. Ou utilisez le résumé affiché à la fin de l'exécution

### Q : Je n'ai qu'une seule clé, ça marche quand même ?

**R :** Oui ! Configurez juste `SERPER_API_KEY_1` dans votre .env. Vous aurez 2500 requêtes disponibles.

## Obtenir des clés API Serper

1. Allez sur https://serper.dev/
2. Créez un compte (ou connectez-vous)
3. Dans le dashboard, cliquez sur "API Keys"
4. Créez autant de clés que nécessaire
5. Copiez-collez chaque clé dans votre .env

**Astuce** : Serper offre des crédits gratuits pour commencer. Vous pouvez créer plusieurs comptes si nécessaire pour obtenir plus de clés gratuites.

## Dépannage rapide

| Problème | Solution |
|----------|----------|
| "No Serper API keys available" | Vérifiez que votre .env contient au moins `SERPER_API_KEY_1=...` |
| "Serper API key #X quota exceeded" puis rien | Vous avez épuisé toutes vos clés. Ajoutez-en plus dans .env |
| Les rotations ne marchent pas | Lancez `python test_serper_fallback.py` pour diagnostiquer |
| "401 Unauthorized" | Une ou plusieurs clés sont invalides. Revérifiez-les |

## Support

Besoin d'aide ? Vérifiez dans l'ordre :

1. ✅ Le fichier .env existe et contient vos clés
2. ✅ Les clés sont bien formatées (commencent par `sk-` généralement)
3. ✅ Le test `python test_serper_fallback.py` passe
4. ✅ Vous avez des crédits disponibles sur votre compte Serper

Si tout est ✅ mais ça ne marche toujours pas, consultez `SERPER_FALLBACK.md` pour plus de détails.
