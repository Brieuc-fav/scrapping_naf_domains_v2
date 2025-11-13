# setup_serper_keys.ps1
# Script PowerShell pour configurer facilement les clés API Serper

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Configuration des clés API Serper pour le fallback" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

# Vérifier si .env existe déjà
$envFile = ".env"
$envExists = Test-Path $envFile

if ($envExists) {
    Write-Host "⚠ Un fichier .env existe déjà." -ForegroundColor Yellow
    $overwrite = Read-Host "Voulez-vous le mettre à jour ? (o/N)"
    if ($overwrite -ne "o" -and $overwrite -ne "O") {
        Write-Host "`n✋ Opération annulée. Fichier .env non modifié." -ForegroundColor Yellow
        exit
    }
    Write-Host ""
}

Write-Host "📝 Entrez vos clés API Serper" -ForegroundColor Green
Write-Host "   (Appuyez sur Entrée sans rien taper pour terminer)`n" -ForegroundColor Gray

$keys = @()
$keyNumber = 1

while ($true) {
    $key = Read-Host "Clé API #$keyNumber"
    
    if ([string]::IsNullOrWhiteSpace($key)) {
        if ($keyNumber -eq 1) {
            Write-Host "`n❌ Erreur : Vous devez entrer au moins une clé API !" -ForegroundColor Red
            continue
        } else {
            break
        }
    }
    
    $keys += $key
    $keyNumber++
    
    if ($keyNumber -gt 10) {
        Write-Host "`n⚠ Maximum de 10 clés atteint." -ForegroundColor Yellow
        break
    }
}

# Créer ou mettre à jour le fichier .env
Write-Host "`n📄 Création du fichier .env..." -ForegroundColor Green

$envContent = @"
# INSEE API Configuration
SIRENE_API_KEY=
SIRENE_CLIENT_ID=
SIRENE_CLIENT_SECRET=
SIRENE_TOKEN_URL=https://api.insee.fr/token
SIRENE_API_BASE=https://api.insee.fr/api-sirene/3.11

# SerpAPI Configuration (optional)
SERPAPI_KEY=

# Serper API Configuration - Multiple keys for fallback rotation
"@

for ($i = 0; $i -lt $keys.Count; $i++) {
    $envContent += "`nSERPER_API_KEY_$($i + 1)=$($keys[$i])"
}

# Sauvegarder le fichier
$envContent | Out-File -FilePath $envFile -Encoding UTF8

Write-Host "✅ Fichier .env créé avec succès !`n" -ForegroundColor Green

# Résumé
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Résumé de la configuration" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Nombre de clés configurées : $($keys.Count)" -ForegroundColor White
Write-Host "   Capacité totale           : $($keys.Count * 2500) requêtes" -ForegroundColor White
Write-Host "   Fichier créé              : .env" -ForegroundColor White
Write-Host "============================================================`n" -ForegroundColor Cyan

# Masquer les clés dans l'affichage
Write-Host "Clés configurées :" -ForegroundColor Green
for ($i = 0; $i -lt $keys.Count; $i++) {
    $k = $keys[$i]
    $masked = if ($k.Length -gt 12) {
        $k.Substring(0, 8) + "..." + $k.Substring($k.Length - 4)
    } else {
        "***"
    }
    Write-Host "  Clé #$($i + 1): $masked" -ForegroundColor Gray
}

Write-Host "`n📋 Prochaines étapes :" -ForegroundColor Yellow
Write-Host "   1. Testez votre configuration :" -ForegroundColor White
Write-Host "      python .\test_serper_fallback.py`n" -ForegroundColor Cyan
Write-Host "   2. Lancez un petit test :" -ForegroundColor White
Write-Host "      python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A --max-pages 1 --outfile test.csv`n" -ForegroundColor Cyan
Write-Host "   3. Consultez GUIDE_RAPIDE.md pour plus d'informations`n" -ForegroundColor White

Write-Host "🎉 Configuration terminée !`n" -ForegroundColor Green
