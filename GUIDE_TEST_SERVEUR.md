# 🧪 Guide de Test Complet - Avant Déploiement Serveur

## Checklist de Validation Complète

### ✅ Étape 1 : Configuration des Clés API

**1.1 Éditer le fichier .env**

```powershell
notepad .env
```

Remplacez les placeholders par vos vraies clés :
```env
SERPER_API_KEY_1=sk-votre-vraie-cle-1
SERPER_API_KEY_2=sk-votre-vraie-cle-2
SERPER_API_KEY_3=sk-votre-vraie-cle-3
SERPER_API_KEY_4=sk-votre-vraie-cle-4
```

**1.2 Vérifier que le fichier .env existe**

```powershell
Test-Path .env
# Doit retourner: True
```

### ✅ Étape 2 : Tests Unitaires

**2.1 Test de chargement des clés**

```powershell
python .\test_serper_fallback.py
```

**Résultat attendu** :
```
✓ PASS: Chargement des clés
✓ PASS: Import du module
✓ PASS: Rotation des clés
✓ PASS: Simulation API

Total: 4/4 tests réussis

🎉 Tous les tests sont passés!
```

❌ **Si ça échoue** : Vérifiez que vos clés sont bien dans le .env

### ✅ Étape 3 : Test Minimal (1 entreprise)

**3.1 Test avec 1 seule page**

```powershell
python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 1 --per-page 1 --outfile test_minimal.csv --sleep 0.5
```

**Ce test vérifie** :
- ✅ La connexion à l'API Serper fonctionne
- ✅ Les clés sont valides
- ✅ Le script peut extraire et traiter les données
- ✅ Le CSV est généré correctement

**Résultat attendu** :
- Le script s'exécute sans erreur
- Un fichier `test_minimal.csv` est créé
- Un résumé d'utilisation s'affiche :
```
============================================================
Serper API Usage Summary:
============================================================
  Key #1 (sk-abc12...xyz9): 1 requests
  Key #2 (sk-def34...uvw8): 0 requests
  ...
============================================================
```

### ✅ Étape 4 : Test de Rotation (Simulation)

**4.1 Créer un script de test de rotation**

Créez `test_rotation.py` :

```python
import os
from dotenv import load_dotenv
load_dotenv()

# Importer le module
import build_esn_list as esn

print("Test de rotation des clés Serper\n")
print(f"Nombre de clés chargées: {len(esn.SERPER_API_KEYS)}")

if len(esn.SERPER_API_KEYS) >= 2:
    print("\nTest de rotation:")
    for i in range(min(4, len(esn.SERPER_API_KEYS))):
        key = esn.get_next_serper_key()
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        print(f"  Index {esn.CURRENT_SERPER_KEY_INDEX}: {masked}")
        if i < len(esn.SERPER_API_KEYS) - 1:
            esn.rotate_serper_key()
    print("\n✅ Rotation fonctionne correctement!")
else:
    print("\n⚠ Ajoutez plus de clés pour tester la rotation")
```

**4.2 Exécuter le test**

```powershell
python test_rotation.py
```

### ✅ Étape 5 : Test Petit Volume (10 entreprises)

**5.1 Test avec 10 entreprises**

```powershell
python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 1 --per-page 10 --outfile test_10.csv --sleep 0.5
```

**Ce test vérifie** :
- ✅ Le script fonctionne sur plusieurs entreprises
- ✅ Les requêtes Serper sont bien comptabilisées
- ✅ Pas de crash ou d'erreur réseau

**Vérifications** :
```powershell
# Vérifier que le CSV contient bien 10 lignes (ou moins)
(Import-Csv test_10.csv).Count

# Afficher les premières lignes
Import-Csv test_10.csv | Select-Object -First 3 | Format-Table
```

### ✅ Étape 6 : Test de Gestion d'Erreur 429

**6.1 Vérifier le comportement en cas de quota dépassé**

Pour simuler cela, vous pouvez :

**Option A** : Utiliser une clé déjà épuisée
- Ajoutez une clé épuisée comme `SERPER_API_KEY_1`
- Ajoutez une clé valide comme `SERPER_API_KEY_2`
- Lancez le test, vous devriez voir :
```
Rotating to Serper API key #2
```

**Option B** : Tester avec le vrai quota
- Lancez une extraction qui utilisera environ 2500 requêtes
- Observez la rotation automatique

### ✅ Étape 7 : Test Moyen Volume (100 entreprises)

**7.1 Test avec 100 entreprises**

```powershell
python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 5 --per-page 20 --outfile test_100.csv --sleep 0.5
```

**Ce test vérifie** :
- ✅ Performance sur un volume moyen
- ✅ Stabilité du script
- ✅ Gestion mémoire correcte

**Temps estimé** : 5-10 minutes

### ✅ Étape 8 : Vérification des Fichiers de Sortie

**8.1 Vérifier la qualité des données**

```powershell
# Importer le CSV
$data = Import-Csv test_100.csv

# Vérifier les colonnes importantes
$data | Select-Object -First 3 | Format-List siren, nom, site, score, site_source

# Compter combien ont un site trouvé
($data | Where-Object { $_.site -ne "" }).Count

# Compter par source de site
$data | Group-Object site_source | Select-Object Name, Count
```

### ✅ Étape 9 : Test de Performance et Mémoire

**9.1 Surveiller l'utilisation mémoire**

```powershell
# Lancer le script en arrière-plan
$job = Start-Job -ScriptBlock {
    python c:\Users\brieu\Documents\HEC_AI\scrapping_naf_domains_v2\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 2 --per-page 25 --outfile test_perf.csv
}

# Surveiller pendant quelques secondes
while ($job.State -eq "Running") {
    $pythonProcess = Get-Process python -ErrorAction SilentlyContinue | Sort-Object CPU -Descending | Select-Object -First 1
    if ($pythonProcess) {
        Write-Host "CPU: $([math]::Round($pythonProcess.CPU, 2))s | Mémoire: $([math]::Round($pythonProcess.WorkingSet64/1MB, 2))MB"
    }
    Start-Sleep -Seconds 2
}

# Récupérer le résultat
Receive-Job $job
```

### ✅ Étape 10 : Validation Finale Avant Serveur

**10.1 Checklist finale**

```powershell
# Script de validation finale
Write-Host "=== VALIDATION FINALE ===" -ForegroundColor Cyan

# 1. Fichier .env existe et contient des clés
$envExists = Test-Path .env
Write-Host "1. Fichier .env existe: $envExists" -ForegroundColor $(if($envExists){"Green"}else{"Red"})

# 2. Tests unitaires passent
$testResult = python .\test_serper_fallback.py
$testPassed = $LASTEXITCODE -eq 0
Write-Host "2. Tests unitaires: $(if($testPassed){'✅ PASS'}else{'❌ FAIL'})" -ForegroundColor $(if($testPassed){"Green"}else{"Red"})

# 3. Test minimal fonctionne
Remove-Item test_validation.csv -ErrorAction SilentlyContinue
python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 1 --per-page 3 --outfile test_validation.csv --sleep 0.3 2>&1 | Out-Null
$csvExists = Test-Path test_validation.csv
Write-Host "3. Extraction fonctionne: $csvExists" -ForegroundColor $(if($csvExists){"Green"}else{"Red"})

# 4. Vérifier le CSV généré
if ($csvExists) {
    $rowCount = (Import-Csv test_validation.csv).Count
    Write-Host "4. Données extraites: $rowCount lignes" -ForegroundColor Green
} else {
    Write-Host "4. Pas de données" -ForegroundColor Red
}

Write-Host "`n=== RÉSULTAT ===" -ForegroundColor Cyan
if ($envExists -and $testPassed -and $csvExists) {
    Write-Host "🎉 PRÊT POUR LE DÉPLOIEMENT !" -ForegroundColor Green
    Write-Host "Vous pouvez déployer sur le serveur en toute confiance." -ForegroundColor Green
} else {
    Write-Host "⚠ PAS PRÊT - Corrigez les erreurs ci-dessus" -ForegroundColor Red
}
```

### ✅ Étape 11 : Test Simulation Serveur (Local)

**11.1 Simuler un environnement serveur**

```powershell
# Créer un dossier de test serveur
New-Item -ItemType Directory -Force -Path .\test_server

# Copier les fichiers nécessaires
Copy-Item build_esn_list.py, requirements.txt, .env .\test_server\

# Aller dans le dossier
cd .\test_server

# Créer un environnement virtuel (comme sur serveur)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Installer les dépendances
pip install -r requirements.txt

# Tester
python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 1 --per-page 5 --outfile test_server.csv

# Revenir au dossier principal
deactivate
cd ..
```

## 📊 Résumé des Tests à Effectuer

| # | Test | Durée | Critique |
|---|------|-------|----------|
| 1 | Configuration .env | 2 min | ✅ OUI |
| 2 | Tests unitaires | 1 min | ✅ OUI |
| 3 | Test minimal (1 entrée) | 1 min | ✅ OUI |
| 4 | Test rotation | 1 min | ⚠️ Recommandé |
| 5 | Test 10 entreprises | 2 min | ✅ OUI |
| 6 | Test erreur 429 | 5 min | ⚠️ Optionnel |
| 7 | Test 100 entreprises | 10 min | ⚠️ Recommandé |
| 8 | Vérification données | 2 min | ✅ OUI |
| 9 | Test performance | 5 min | ⚠️ Optionnel |
| 10 | Validation finale | 3 min | ✅ OUI |
| 11 | Simulation serveur | 10 min | ⚠️ Recommandé |

**Temps total minimum** : ~15 minutes (tests critiques uniquement)
**Temps total recommandé** : ~45 minutes (tous les tests)

## 🚨 Erreurs Courantes et Solutions

### Erreur : "No Serper API keys available"
**Solution** : Éditez le .env et ajoutez vos clés

### Erreur : "429 Too Many Requests"
**Solution** : C'est normal ! Vérifiez que le message "Rotating to Serper API key #2" apparaît

### Erreur : "ModuleNotFoundError"
**Solution** : Installez les dépendances :
```powershell
pip install -r requirements.txt
```

### Le CSV est vide
**Solution** : 
- Vérifiez que --use-recherche est bien présent
- Essayez un autre code NAF
- Augmentez --max-pages

## 📦 Préparation pour le Serveur

### Fichiers à copier sur le serveur :
```
✅ build_esn_list.py
✅ requirements.txt
✅ .env (avec vos vraies clés)
✅ README.md (optionnel)
```

### Fichiers à NE PAS copier :
```
❌ test_*.csv
❌ __pycache__/
❌ venv/
❌ .git/
```

### Commandes serveur (Linux/Ubuntu) :

```bash
# Installation
pip install -r requirements.txt

# Test rapide
python build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 1 --per-page 5 --outfile test.csv

# Vérifier le résultat
wc -l test.csv
head test.csv
```

## ✅ Validation Finale

Avant de déployer, assurez-vous que :

- [ ] Tous les tests critiques passent
- [ ] Le fichier .env contient vos vraies clés
- [ ] Vous avez testé avec au moins 10 entreprises
- [ ] Le CSV généré contient les bonnes colonnes
- [ ] Le résumé d'utilisation s'affiche correctement
- [ ] Vous avez noté combien de clés vous utilisez
- [ ] Vous savez combien de requêtes vous pouvez faire (nb_clés × 2500)

**Si tout est ✅, vous êtes prêt pour le serveur !** 🚀
