#!/usr/bin/env python3
"""
Script per verificare se i validator hub supportano async
"""

import sys
sys.path.append('/home/eanx/PycharmProjects/SimpleChatApp')

import asyncio
import inspect
from guardrails.hub import ToxicLanguage, ProfanityFree

def check_async_support():
    """Controlla se i validator hub supportano async"""
    
    print("=== CONTROLLO ASYNC SUPPORT VALIDATOR HUB ===")
    
    # Test ToxicLanguage
    toxic = ToxicLanguage(threshold=0.8, on_fail="exception")
    print(f"\nToxicLanguage:")
    print(f"  - Classe: {type(toxic)}")
    print(f"  - Ha validate: {hasattr(toxic, 'validate')}")
    print(f"  - Ha validate_async: {hasattr(toxic, 'validate_async')}")
    
    if hasattr(toxic, 'validate'):
        validate_method = getattr(toxic, 'validate')
        print(f"  - validate è async: {inspect.iscoroutinefunction(validate_method)}")
    
    if hasattr(toxic, 'validate_async'):
        validate_async_method = getattr(toxic, 'validate_async')
        print(f"  - validate_async è async: {inspect.iscoroutinefunction(validate_async_method)}")
    
    # Test ProfanityFree
    profanity = ProfanityFree(on_fail="filter")
    print(f"\nProfanityFree:")
    print(f"  - Classe: {type(profanity)}")
    print(f"  - Ha validate: {hasattr(profanity, 'validate')}")
    print(f"  - Ha validate_async: {hasattr(profanity, 'validate_async')}")
    
    if hasattr(profanity, 'validate'):
        validate_method = getattr(profanity, 'validate')
        print(f"  - validate è async: {inspect.iscoroutinefunction(validate_method)}")
    
    if hasattr(profanity, 'validate_async'):
        validate_async_method = getattr(profanity, 'validate_async')
        print(f"  - validate_async è async: {inspect.iscoroutinefunction(validate_async_method)}")
    
    # Test con AsyncGuard
    print(f"\n=== TEST ASYNCGUARD ===")
    try:
        from guardrails import AsyncGuard
        print("✅ AsyncGuard import successful")
        
        # Prova a creare AsyncGuard con validator hub
        try:
            async_guard = AsyncGuard().use_many(
                ToxicLanguage(threshold=0.8, on_fail="exception"),
                ProfanityFree(on_fail="filter")
            )
            print("✅ AsyncGuard con validator hub creato con successo")
            print(f"   - Numero validators: {len(async_guard.validators) if hasattr(async_guard, 'validators') else 'N/A'}")
        except Exception as e:
            print(f"❌ Errore creando AsyncGuard con validator hub: {e}")
            
    except ImportError as e:
        print(f"❌ AsyncGuard non disponibile: {e}")

if __name__ == "__main__":
    check_async_support()
