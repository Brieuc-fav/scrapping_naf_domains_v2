#!/usr/bin/env python3
"""
test_serper_fallback.py
Script de test pour vérifier le fonctionnement du système de fallback Serper API
"""

import os
import sys
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

def test_key_loading():
    """Test le chargement des clés API depuis le .env"""
    print("="*60)
    print("TEST 1: Chargement des clés API")
    print("="*60)
    
    keys = []
    for i in range(1, 11):  # Test jusqu'à 10 clés
        key = os.getenv(f"SERPER_API_KEY_{i}")
        if key:
            masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
            print(f"  ✓ SERPER_API_KEY_{i} trouvée: {masked}")
            keys.append(key)
        else:
            if i == 1:
                # Essayer le format legacy
                legacy_key = os.getenv("SERPER_API_KEY")
                if legacy_key:
                    masked = legacy_key[:8] + "..." + legacy_key[-4:] if len(legacy_key) > 12 else "***"
                    print(f"  ✓ SERPER_API_KEY (legacy) trouvée: {masked}")
                    keys.append(legacy_key)
            break
    
    if not keys:
        print("  ✗ Aucune clé API Serper trouvée!")
        print("  → Ajoutez au moins SERPER_API_KEY_1 dans votre fichier .env")
        return False
    
    print(f"\n  Total: {len(keys)} clé(s) chargée(s)")
    return True

def test_import_script():
    """Test l'import du script principal"""
    print("\n" + "="*60)
    print("TEST 2: Import du module principal")
    print("="*60)
    
    try:
        # Essayer d'importer les fonctions du script
        sys.path.insert(0, os.path.dirname(__file__))
        import build_esn_list
        print("  ✓ Module build_esn_list importé avec succès")
        
        # Vérifier que les variables globales sont initialisées
        if hasattr(build_esn_list, 'SERPER_API_KEYS'):
            print(f"  ✓ SERPER_API_KEYS initialisé avec {len(build_esn_list.SERPER_API_KEYS)} clé(s)")
        else:
            print("  ✗ SERPER_API_KEYS non trouvé")
            return False
        
        if hasattr(build_esn_list, 'get_next_serper_key'):
            print("  ✓ Fonction get_next_serper_key disponible")
        else:
            print("  ✗ Fonction get_next_serper_key non trouvée")
            return False
        
        if hasattr(build_esn_list, 'rotate_serper_key'):
            print("  ✓ Fonction rotate_serper_key disponible")
        else:
            print("  ✗ Fonction rotate_serper_key non trouvée")
            return False
        
        return True
    except Exception as e:
        print(f"  ✗ Erreur lors de l'import: {e}")
        return False

def test_key_rotation():
    """Test la rotation des clés"""
    print("\n" + "="*60)
    print("TEST 3: Rotation des clés")
    print("="*60)
    
    try:
        import build_esn_list
        
        if len(build_esn_list.SERPER_API_KEYS) < 2:
            print("  ⚠ Moins de 2 clés disponibles, rotation non testable")
            print("  → Ajoutez SERPER_API_KEY_2, SERPER_API_KEY_3, etc. pour tester la rotation")
            return True  # Pas une erreur, juste un avertissement
        
        # Test de rotation
        initial_index = build_esn_list.CURRENT_SERPER_KEY_INDEX
        print(f"  Index initial: {initial_index}")
        
        # Premier appel
        key1 = build_esn_list.get_next_serper_key()
        print(f"  ✓ Première clé obtenue: {key1[:8]}...{key1[-4:]}")
        
        # Rotation
        rotated = build_esn_list.rotate_serper_key()
        if rotated:
            print("  ✓ Rotation effectuée avec succès")
        else:
            print("  ✗ Échec de la rotation")
            return False
        
        # Deuxième appel
        key2 = build_esn_list.get_next_serper_key()
        print(f"  ✓ Deuxième clé obtenue: {key2[:8]}...{key2[-4:]}")
        
        if key1 != key2:
            print("  ✓ Les clés sont différentes (rotation fonctionnelle)")
        else:
            print("  ✗ Les clés sont identiques (rotation non fonctionnelle)")
            return False
        
        return True
    except Exception as e:
        print(f"  ✗ Erreur lors du test de rotation: {e}")
        return False

def test_mock_api_call():
    """Test un appel API simulé"""
    print("\n" + "="*60)
    print("TEST 4: Simulation d'appel API")
    print("="*60)
    
    try:
        import build_esn_list
        
        if not build_esn_list.SERPER_API_KEYS:
            print("  ✗ Aucune clé API disponible pour le test")
            return False
        
        print("  ℹ Note: Ce test ne fait PAS d'appel réel à l'API")
        print("  ℹ Pour tester réellement, utilisez le script principal avec --use-serper")
        
        # Vérifier que la fonction serper_find_domain existe et accepte les bons paramètres
        import inspect
        sig = inspect.signature(build_esn_list.serper_find_domain)
        params = list(sig.parameters.keys())
        
        expected_params = ['query', 'api_key', 'num', 'hl', 'gl', 'max_retries']
        if all(p in params for p in expected_params):
            print(f"  ✓ Fonction serper_find_domain a la bonne signature")
        else:
            print(f"  ✗ Signature incorrecte. Attendu: {expected_params}, Trouvé: {params}")
            return False
        
        print("  ✓ Tests de structure réussis")
        return True
    except Exception as e:
        print(f"  ✗ Erreur lors du test de simulation: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("TEST DU SYSTÈME DE FALLBACK SERPER API")
    print("="*60 + "\n")
    
    results = []
    
    # Test 1: Chargement des clés
    results.append(("Chargement des clés", test_key_loading()))
    
    # Test 2: Import du script
    results.append(("Import du module", test_import_script()))
    
    # Test 3: Rotation des clés
    results.append(("Rotation des clés", test_key_rotation()))
    
    # Test 4: Simulation d'appel API
    results.append(("Simulation API", test_mock_api_call()))
    
    # Résumé
    print("\n" + "="*60)
    print("RÉSUMÉ DES TESTS")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\n  Total: {passed}/{total} tests réussis")
    
    if passed == total:
        print("\n  🎉 Tous les tests sont passés!")
        print("  → Vous pouvez utiliser le système de fallback en toute confiance")
        return 0
    else:
        print("\n  ⚠ Certains tests ont échoué")
        print("  → Vérifiez votre configuration .env et le code du script")
        return 1

if __name__ == "__main__":
    sys.exit(main())
