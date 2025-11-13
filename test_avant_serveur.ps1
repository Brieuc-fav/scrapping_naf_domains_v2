# test_avant_serveur.ps1
# Script de validation automatique avant déploiement serveur

param(
    [switch]$Quick,  # Tests rapides uniquement (5 min)
    [switch]$Full    # Tests complets (30 min)
)

$ErrorActionPreference = "Continue"

function Write-TestHeader {
    param($Title)
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host "   $Title" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

function Write-TestResult {
    param($TestName, $Success, $Message = "")
    $status = if ($Success) { "✅ PASS" } else { "❌ FAIL" }
    $color = if ($Success) { "Green" } else { "Red" }
    Write-Host "$status : $TestName" -ForegroundColor $color
    if ($Message) {
        Write-Host "         $Message" -ForegroundColor Gray
    }
}

# Initialisation
Write-Host "`n🧪 TESTS DE VALIDATION AVANT DÉPLOIEMENT SERVEUR" -ForegroundColor Yellow
Write-Host "================================================`n" -ForegroundColor Yellow

$startTime = Get-Date
$results = @()

# ============================================================
# TEST 1 : Vérification du fichier .env
# ============================================================
Write-TestHeader "TEST 1 : Configuration .env"

$envExists = Test-Path .env
$results += [PSCustomObject]@{Test="Fichier .env existe"; Success=$envExists}
Write-TestResult "Fichier .env existe" $envExists

if ($envExists) {
    $envContent = Get-Content .env -Raw
    $hasKey1 = $envContent -match "SERPER_API_KEY_1\s*=\s*.+"
    $results += [PSCustomObject]@{Test="Clé API 1 configurée"; Success=$hasKey1}
    Write-TestResult "SERPER_API_KEY_1 configurée" $hasKey1 "Fichier .env doit contenir au moins une clé"
    
    # Compter les clés
    $keyCount = 0
    1..10 | ForEach-Object {
        if ($envContent -match "SERPER_API_KEY_$_\s*=\s*.+") {
            $keyCount++
        }
    }
    Write-Host "         Nombre de clés détectées: $keyCount" -ForegroundColor Gray
    Write-Host "         Capacité totale estimée: $($keyCount * 2500) requêtes" -ForegroundColor Gray
} else {
    Write-Host "❌ Créez un fichier .env avec vos clés API Serper" -ForegroundColor Red
    Write-Host "   Copiez .env.example vers .env et remplissez vos clés" -ForegroundColor Yellow
}

# ============================================================
# TEST 2 : Dépendances Python
# ============================================================
Write-TestHeader "TEST 2 : Dépendances Python"

$pipList = pip list 2>&1
$dependencies = @("requests", "beautifulsoup4", "tldextract", "pandas", "python-dotenv")
$allInstalled = $true

foreach ($dep in $dependencies) {
    $installed = $pipList -match $dep
    $results += [PSCustomObject]@{Test="Dépendance $dep"; Success=$installed}
    Write-TestResult "$dep installé" $installed
    if (-not $installed) { $allInstalled = $false }
}

if (-not $allInstalled) {
    Write-Host "`n⚠ Installez les dépendances manquantes:" -ForegroundColor Yellow
    Write-Host "   pip install -r requirements.txt" -ForegroundColor Cyan
}

# ============================================================
# TEST 3 : Tests unitaires
# ============================================================
Write-TestHeader "TEST 3 : Tests Unitaires"

$testOutput = python .\test_serper_fallback.py 2>&1
$testPassed = $LASTEXITCODE -eq 0
$results += [PSCustomObject]@{Test="Tests unitaires"; Success=$testPassed}
Write-TestResult "Tests unitaires du système de fallback" $testPassed

if (-not $testPassed) {
    Write-Host "`n📋 Sortie du test:" -ForegroundColor Yellow
    $testOutput | Select-Object -Last 20
}

# ============================================================
# TEST 4 : Test minimal (1 entreprise)
# ============================================================
Write-TestHeader "TEST 4 : Test Minimal (1 entreprise)"

Write-Host "⏳ Exécution du test minimal..." -ForegroundColor Gray
Remove-Item test_minimal.csv -ErrorAction SilentlyContinue

$testCmd = "python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 1 --per-page 1 --outfile test_minimal.csv --sleep 0.3"
$output = Invoke-Expression $testCmd 2>&1

$csvExists = Test-Path test_minimal.csv
$results += [PSCustomObject]@{Test="Extraction minimale"; Success=$csvExists}
Write-TestResult "Extraction d'1 entreprise" $csvExists

if ($csvExists) {
    $data = Import-Csv test_minimal.csv
    $hasData = $data.Count -gt 0
    Write-Host "         Lignes extraites: $($data.Count)" -ForegroundColor Gray
    
    if ($hasData) {
        $firstRow = $data[0]
        Write-Host "         SIREN: $($firstRow.siren)" -ForegroundColor Gray
        Write-Host "         Nom: $($firstRow.nom)" -ForegroundColor Gray
        Write-Host "         Site: $(if($firstRow.site){$firstRow.site}else{'non trouvé'})" -ForegroundColor Gray
        Write-Host "         Source: $($firstRow.site_source)" -ForegroundColor Gray
    }
}

# ============================================================
# TEST 5 : Test avec 5 entreprises (si pas Quick)
# ============================================================
if (-not $Quick) {
    Write-TestHeader "TEST 5 : Test 5 Entreprises"
    
    Write-Host "⏳ Exécution du test avec 5 entreprises..." -ForegroundColor Gray
    Remove-Item test_5.csv -ErrorAction SilentlyContinue
    
    $testCmd = "python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 1 --per-page 5 --outfile test_5.csv --sleep 0.3"
    $output = Invoke-Expression $testCmd 2>&1
    
    $csvExists = Test-Path test_5.csv
    $results += [PSCustomObject]@{Test="Extraction 5 entreprises"; Success=$csvExists}
    Write-TestResult "Extraction de 5 entreprises" $csvExists
    
    if ($csvExists) {
        $data = Import-Csv test_5.csv
        Write-Host "         Lignes extraites: $($data.Count)" -ForegroundColor Gray
        
        # Statistiques
        $withSite = ($data | Where-Object { $_.site -ne "" }).Count
        Write-Host "         Avec site trouvé: $withSite / $($data.Count)" -ForegroundColor Gray
        
        $bySources = $data | Group-Object site_source | ForEach-Object { "$($_.Name): $($_.Count)" }
        Write-Host "         Sources: $($bySources -join ', ')" -ForegroundColor Gray
    }
}

# ============================================================
# TEST 6 : Test avec 20 entreprises (si Full)
# ============================================================
if ($Full) {
    Write-TestHeader "TEST 6 : Test 20 Entreprises (complet)"
    
    Write-Host "⏳ Exécution du test avec 20 entreprises (peut prendre 5-10 min)..." -ForegroundColor Gray
    Remove-Item test_20.csv -ErrorAction SilentlyContinue
    
    $testCmd = "python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A,71.12B --max-pages 2 --per-page 10 --outfile test_20.csv --sleep 0.5"
    $output = Invoke-Expression $testCmd 2>&1
    
    $csvExists = Test-Path test_20.csv
    $results += [PSCustomObject]@{Test="Extraction 20 entreprises"; Success=$csvExists}
    Write-TestResult "Extraction de 20 entreprises" $csvExists
    
    if ($csvExists) {
        $data = Import-Csv test_20.csv
        Write-Host "         Lignes extraites: $($data.Count)" -ForegroundColor Gray
        
        # Statistiques détaillées
        $withSite = ($data | Where-Object { $_.site -ne "" }).Count
        $avgScore = ($data | Measure-Object -Property score -Average).Average
        
        Write-Host "         Avec site trouvé: $withSite / $($data.Count) ($([math]::Round($withSite*100/$data.Count, 1))%)" -ForegroundColor Gray
        Write-Host "         Score moyen: $([math]::Round($avgScore, 2))" -ForegroundColor Gray
        
        # Top 3 scores
        $top3 = $data | Sort-Object -Property score -Descending | Select-Object -First 3
        Write-Host "         Top 3 scores:" -ForegroundColor Gray
        $top3 | ForEach-Object { Write-Host "           - $($_.nom): $($_.score)" -ForegroundColor DarkGray }
    }
}

# ============================================================
# RÉSUMÉ FINAL
# ============================================================
Write-TestHeader "RÉSUMÉ DES TESTS"

$passed = ($results | Where-Object { $_.Success }).Count
$total = $results.Count
$percentPass = [math]::Round($passed * 100 / $total, 1)

Write-Host "`n📊 Résultats:" -ForegroundColor White
$results | Format-Table -AutoSize

Write-Host "✅ Tests réussis : $passed / $total ($percentPass%)" -ForegroundColor $(if($percentPass -ge 80){"Green"}else{"Yellow"})

$duration = (Get-Date) - $startTime
Write-Host "⏱️  Durée totale  : $([math]::Round($duration.TotalMinutes, 1)) minutes`n" -ForegroundColor Gray

# ============================================================
# DÉCISION FINALE
# ============================================================
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   DÉCISION FINALE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if ($percentPass -ge 100) {
    Write-Host "`n🎉 EXCELLENT ! Tous les tests sont passés !" -ForegroundColor Green
    Write-Host "✅ Vous pouvez déployer sur le serveur en toute confiance.`n" -ForegroundColor Green
    
    Write-Host "📦 Fichiers à copier sur le serveur:" -ForegroundColor Yellow
    Write-Host "   - build_esn_list.py" -ForegroundColor White
    Write-Host "   - requirements.txt" -ForegroundColor White
    Write-Host "   - .env (avec vos vraies clés)" -ForegroundColor White
    
    Write-Host "`n🚀 Commandes serveur (Linux):" -ForegroundColor Yellow
    Write-Host "   pip install -r requirements.txt" -ForegroundColor Cyan
    Write-Host "   python build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 10 --outfile resultats.csv" -ForegroundColor Cyan
    
} elseif ($percentPass -ge 80) {
    Write-Host "`n⚠️  BON, mais quelques tests ont échoué" -ForegroundColor Yellow
    Write-Host "Vérifiez les tests échoués ci-dessus avant le déploiement." -ForegroundColor Yellow
    
    Write-Host "`n📋 Tests échoués:" -ForegroundColor Red
    $results | Where-Object { -not $_.Success } | ForEach-Object {
        Write-Host "   - $($_.Test)" -ForegroundColor Red
    }
    
} else {
    Write-Host "`n❌ ATTENTION ! Trop de tests ont échoué" -ForegroundColor Red
    Write-Host "Ne déployez PAS sur le serveur avant de corriger les erreurs.`n" -ForegroundColor Red
    
    Write-Host "📋 Actions recommandées:" -ForegroundColor Yellow
    Write-Host "   1. Vérifiez votre fichier .env" -ForegroundColor White
    Write-Host "   2. Installez les dépendances : pip install -r requirements.txt" -ForegroundColor White
    Write-Host "   3. Vérifiez que vos clés API Serper sont valides" -ForegroundColor White
    Write-Host "   4. Relancez ce script : .\test_avant_serveur.ps1" -ForegroundColor White
}

Write-Host "`n============================================================`n" -ForegroundColor Cyan

# Nettoyage optionnel
$cleanup = Read-Host "Voulez-vous supprimer les fichiers de test CSV ? (o/N)"
if ($cleanup -eq "o" -or $cleanup -eq "O") {
    Remove-Item test_*.csv -ErrorAction SilentlyContinue
    Write-Host "✅ Fichiers de test supprimés" -ForegroundColor Green
}

# Code de sortie
exit $(if ($percentPass -ge 80) { 0 } else { 1 })
