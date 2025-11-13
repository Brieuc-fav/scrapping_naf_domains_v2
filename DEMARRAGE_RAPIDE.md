# 🚀 Configuration Rapide - Multi-Clés Serper API

## Méthode 1 : Script Automatique (Recommandé)

```powershell
.\setup_serper_keys.ps1
```

Suivez les instructions à l'écran !

## Méthode 2 : Manuelle

1. Copiez `.env.example` vers `.env` :
```powershell
Copy-Item .env.example .env
```

2. Ouvrez `.env` et ajoutez vos clés :
```env
SERPER_API_KEY_1=votre_premiere_cle_ici
SERPER_API_KEY_2=votre_deuxieme_cle_ici
SERPER_API_KEY_3=votre_troisieme_cle_ici
SERPER_API_KEY_4=votre_quatrieme_cle_ici
```

## Test

```powershell
python .\test_serper_fallback.py
```

## Utilisation

```powershell
python .\build_esn_list.py --use-serper --use-recherche --naf-codes 62.02A,71.12B --max-pages 50 --outfile resultats.csv
```

## Capacité par nombre de clés

| Clés | Capacité |
|------|----------|
| 1    | 2 500    |
| 2    | 5 000    |
| 3    | 7 500    |
| 4    | 10 000   |

## Documentation Complète

- **Guide rapide** : `GUIDE_RAPIDE.md`
- **Documentation technique** : `SERPER_FALLBACK.md`
- **Résumé des changements** : `CHANGELOG.md`

## Avantages

✅ Rotation automatique quand une clé atteint sa limite
✅ Aucune intervention manuelle nécessaire  
✅ Suivi détaillé de l'utilisation
✅ Compatible avec l'ancienne version (1 seule clé)

---

**C'est tout ! Vous êtes prêt à traiter des milliers d'entreprises !** 🎉
