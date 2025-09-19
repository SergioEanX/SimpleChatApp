#!/usr/bin/env python3
"""
Test PII Detection - Italiano ed Inglese
========================================
"""

import requests
import json

BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/query"

def test_pii_case(description: str, query: str, should_be_blocked: bool):
    """Test single PII case"""
    print(f"\n🧪 TEST: {description}")
    print(f"📝 Query: \"{query}\"")
    
    try:
        response = requests.post(
            ENDPOINT,
            json={"query": query},
            timeout=10
        )
        
        if should_be_blocked:
            if response.status_code == 400:
                print("✅ CORRETTO: Bloccato come previsto")
                error_data = response.json()
                print(f"📄 Messaggio: {error_data.get('message', 'N/A')}")
            else:
                print(f"❌ ERRORE: Doveva essere bloccato, ma ha passato (HTTP {response.status_code})")
        else:
            if response.status_code == 200:
                print("✅ CORRETTO: Passato come previsto")
            else:
                print(f"❌ ERRORE: Doveva passare, ma è stato bloccato (HTTP {response.status_code})")
                
    except requests.exceptions.RequestException as e:
        print(f"❌ ERRORE CONNESSIONE: {e}")

def main():
    """Esegui tutti i test PII"""
    print("🛡️ TEST PII DETECTION - Italiano + Inglese")
    print("=" * 60)
    
    # Test Codici Fiscali Italiani
    test_pii_case(
        "Codice Fiscale IT (dovrebbe essere bloccato)",
        "Il mio codice fiscale è RSSMRA85M01H501Z, puoi cercarlo nel database?",
        should_be_blocked=True
    )
    
    # Test Email
    test_pii_case(
        "Email address (dovrebbe essere bloccato)",
        "Contattami su mario.rossi@email.com per i risultati",
        should_be_blocked=True
    )
    
    # Test Nomi Propri
    test_pii_case(
        "Nome persona (dovrebbe essere bloccato)",
        "Cerca informazioni su Mario Rossi nel sistema",
        should_be_blocked=True
    )
    
    # Test Telefono
    test_pii_case(
        "Numero telefono (dovrebbe essere bloccato)", 
        "Il mio numero è 339-1234567, chiamami",
        should_be_blocked=True
    )
    
    # Test Carta di Credito
    test_pii_case(
        "Numero carta credito (dovrebbe essere bloccato)",
        "La mia carta è 4532-1234-5678-9012 scadenza 12/25",
        should_be_blocked=True
    )
    
    # Test IBAN
    test_pii_case(
        "IBAN italiano (dovrebbe essere bloccato)",
        "Il mio IBAN è IT60 X054 2811 1010 0000 0123 456",
        should_be_blocked=True
    )
    
    # Test Query Legittime (dovrebbero passare)
    test_pii_case(
        "Query database generica (dovrebbe passare)",
        "Mostra tutti gli utenti con età maggiore di 30",
        should_be_blocked=False
    )
    
    test_pii_case(
        "Query analytics (dovrebbe passare)",
        "Analizza i trend di vendita del Q3",
        should_be_blocked=False
    )
    
    test_pii_case(
        "Query con parole simili ma non PII (dovrebbe passare)",
        "Trova documenti con campo 'nome_prodotto' uguale a 'Mario Bros Game'",
        should_be_blocked=False
    )
    
    # Test Misti (PII + Query legittima)
    test_pii_case(
        "Query mista con PII (dovrebbe essere bloccato)",
        "Cerca nel database l'utente con email mario.rossi@test.com",
        should_be_blocked=True
    )
    
    print("\n" + "=" * 60)
    print("🏁 Test PII completati!")
    print("\nℹ️  Note:")
    print("- I test bloccati dovrebbero mostrare HTTP 400")
    print("- I test passati dovrebbero mostrare HTTP 200") 
    print("- Messaggi di errore dovrebbero essere in italiano")

if __name__ == "__main__":
    main()
