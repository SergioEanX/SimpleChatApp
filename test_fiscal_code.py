#!/usr/bin/env python3
"""Test script for fiscal code processing"""

import requests
import time




def test_fiscal_code():
    """Test the fiscal code query"""
    # Wait for server to start
    time.sleep(5)
    
    url = "http://localhost:8000/query"
    data = {
        "query": "Il mio codice fiscale è RSSMRA85M01H501Z, puoi elaborare questa informazione?"
    }
    
    try:
        print("🧪 Testing fiscal code query...")
        response = requests.post(url, json=data, timeout=30)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📝 Response content: {response.text[:500]}...")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Query successful!")
            print(f"🔍 Session ID: {result.get('session_id')}")
            print(f"📄 Document count: {result.get('document_count', 0)}")
            
            # Check if the query was processed correctly
            if "codice_fiscale" in str(result.get('result', '')):
                print("✅ Fiscal code field detected in query!")
            else:
                print("❌ Fiscal code field NOT detected in query")
                
        else:
            print(f"❌ Query failed: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":

    # Test fiscal code
    test_fiscal_code()
    
