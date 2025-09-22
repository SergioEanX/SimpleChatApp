#!/usr/bin/env python3
"""
session_demo.py - Dimostrazione gestione sessioni multiple
=========================================================

Script per testare la gestione di sessioni multiple con memoria isolata.
Dimostra come gestire conversazioni separate tra diversi utenti/contesti.

Uso:
    python session_demo.py
"""

import asyncio
import httpx
import json
from datetime import datetime


class SessionManager:
    """Manager per testare sessioni multiple"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.sessions = {}
        
    async def create_session(self, name: str) -> str:
        """Crea una nuova sessione"""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/session/new")
            data = response.json()
            session_id = data["session_id"]
            self.sessions[name] = session_id
            print(f"✅ Creata sessione '{name}': {session_id}")
            return session_id
    
    async def send_message(self, session_name: str, message: str, endpoint: str = "query"):
        """Invia messaggio usando sessione specifica"""
        if session_name not in self.sessions:
            print(f"❌ Sessione '{session_name}' non trovata")
            return
        
        session_id = self.sessions[session_name]
        
        async with httpx.AsyncClient() as client:
            payload = {
                "query": message,
                "session_id": session_id
            }
            
            if endpoint == "query":
                response = await client.post(f"{self.base_url}/query", json=payload)
                data = response.json()
                result = data.get("result", "Nessuna risposta")
                print(f"[{session_name}] Query → {result}")
                
            elif endpoint == "chat":
                print(f"[{session_name}] Chat streaming...")
                async with client.stream("POST", f"{self.base_url}/chat", json=payload) as response:
                    accumulated = ""
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                event_data = json.loads(line[6:])
                                if event_data.get("type") == "content":
                                    chunk = event_data.get("chunk", "")
                                    accumulated += chunk
                                elif event_data.get("type") == "complete":
                                    final_content = event_data.get("final_content", accumulated)
                                    print(f"[{session_name}] Chat → {final_content}")
                                    break
                            except json.JSONDecodeError:
                                continue
    
    async def get_conversations(self):
        """Mostra tutte le conversazioni attive"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/conversations")
            data = response.json()
            print(f"📊 Conversazioni attive: {data['active_threads']}")
            return data
    
    async def get_session_info(self, session_name: str):
        """Ottieni info su sessione specifica"""
        if session_name not in self.sessions:
            print(f"❌ Sessione '{session_name}' non trovata")
            return
        
        session_id = self.sessions[session_name]
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/session/{session_id}/info")
                data = response.json()
                print(f"📋 Info sessione '{session_name}': {data['total_messages']} messaggi")
                return data
            except httpx.HTTPStatusError as e:
                print(f"❌ Errore info sessione: {e.response.status_code}")


async def demo_sessioni_multiple():
    """Demo completa gestione sessioni multiple"""
    print("🚀 Demo Gestione Sessioni Multiple")
    print("=" * 50)
    
    manager = SessionManager()
    
    # 1. Crea sessioni per diversi utenti
    print("\n1. 📱 Creazione Sessioni:")
    await manager.create_session("Mario")
    await manager.create_session("Luigi") 
    await manager.create_session("Peach")
    
    # 2. Conversazioni separate
    print("\n2. 💬 Conversazioni Indipendenti:")
    
    # Mario si presenta
    await manager.send_message("Mario", "Mi chiamo Mario e ho 30 anni", "query")
    
    # Luigi si presenta 
    await manager.send_message("Luigi", "Io sono Luigi e ho 28 anni", "query")
    
    # Peach si presenta
    await manager.send_message("Peach", "Ciao, sono la Principessa Peach!", "chat")
    
    # 3. Verifica memoria isolata
    print("\n3. 🧠 Test Memoria Isolata:")
    
    # Mario chiede della sua età
    await manager.send_message("Mario", "Quanti anni ho?", "query")
    
    # Luigi chiede della sua età
    await manager.send_message("Luigi", "Come mi chiamo e quanti anni ho?", "chat")
    
    # Peach chiede di se stessa
    await manager.send_message("Peach", "Chi sono io?", "query")
    
    # 4. Cross-contamination test (non dovrebbero sapersi tra loro)
    print("\n4. 🔒 Test Isolamento:")
    await manager.send_message("Mario", "Conosci Luigi?", "query")
    await manager.send_message("Luigi", "Sai l'età di Mario?", "chat")
    
    # 5. Info sessioni
    print("\n5. 📊 Informazioni Sessioni:")
    await manager.get_session_info("Mario")
    await manager.get_session_info("Luigi")
    await manager.get_session_info("Peach")
    
    # 6. Lista conversazioni globali
    print("\n6. 🌐 Conversazioni Attive:")
    await manager.get_conversations()
    
    print("\n✅ Demo completata!")
    print("\n📚 RISULTATI ATTESI:")
    print("- Ogni sessione ricorda solo le proprie informazioni")
    print("- Mario sa di avere 30 anni, Luigi 28 anni")
    print("- Nessuno conosce informazioni degli altri")
    print("- 3 sessioni separate nell'elenco conversazioni")


if __name__ == "__main__":
    asyncio.run(demo_sessioni_multiple())
