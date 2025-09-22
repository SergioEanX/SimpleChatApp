"""
main.py - FastAPI Application con Guardrails Integration
=======================================================

FastAPI app principale con:
- Guardrails middleware per validazione input/output
- Protezione contro injection, PII, contenuti tossici
- Configurazione endpoint-specific per validazione
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from datetime import datetime
from typing import Dict, Any, TYPE_CHECKING, Union
import uuid
import logging
from starlette.datastructures import State
from typing import cast
from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware

from models import QueryRequest, QueryResponse, StreamingChatRequest
from database import MongoDBService
from langchain_service import ConversationalLangChainService
from langchain_service_stream import StreamingService

# New Guards system
from guards import GuardrailsMiddleware

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ================================
# CONFIGURAZIONE
# ================================
load_dotenv()
MONGODB_URI = os.getenv("MONGO_URI",
                        "mongodb://username:password@localhost:27017/database_name")
DATABASE_NAME = "your_database"
COLLECTION_NAME = "your_collection"
OLLAMA_MODEL = os.getenv("LLM_NAME","gemma3:latest")
OLLAMA_BASE_URL = "http://localhost:11434"

# ================================
# SERVIZI GLOBALI
# ================================

mongodb_service: Union[MongoDBService,None] = None
conversational_service: Union[ConversationalLangChainService,None] = None
streaming_service: Union[StreamingService,None] = None  # NUOVO: Servizio streaming globale


# ================================
# LIFESPAN MANAGEMENT
# ================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestisce ciclo di vita applicazione con Guardrails
    """
    # ===== STARTUP =====
    print("🚀 MongoDB Analytics API v2.3 - Con AsyncGuard Streaming")
    print("🛡️ Protezione: AsyncGuard input/output validation attiva")

    global mongodb_service, conversational_service, streaming_service

    try:

        # MongoDB Service
        print("📊 Connessione MongoDB...")
        mongodb_service = MongoDBService(MONGODB_URI, DATABASE_NAME)
        if await mongodb_service.test_connection():
            print("✅ MongoDB operativo")
        else:
            raise Exception("MongoDB non raggiungibile")

        # Conversational LangChain Service
        print("🧠 Inizializzazione ConversationBufferMemory...")
        conversational_service = ConversationalLangChainService(
            model_name=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL
        )

        if await conversational_service.test_connection():
            print("✅ LangChain + Ollama operativi")
            print(f"🤖 Modello: {OLLAMA_MODEL}")
        else:
            raise Exception("Ollama LLM non disponibile")
        
        # **NUOVO**: Streaming Service con memoria condivisa
        print("🔄 Inizializzazione StreamingService...")
        streaming_service = StreamingService(
            model_name=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL
        )
        
        # **INTEGRAZIONE MEMORIA**: Condividi memory store tra servizi
        if hasattr(conversational_service, '_conversation_chains'):
            # Mappa ConversationChain memory to StreamingService memory
            for thread_id, conversation_chain in conversational_service._conversation_chains.items():
                if hasattr(conversation_chain, 'memory'):
                    streaming_service.conversations[thread_id] = conversation_chain.memory
            print(f"✅ Memoria condivisa: {len(conversational_service._conversation_chains)} conversazioni")
        
        # **HOOK SINCRONIZZAZIONE**: Setup cross-service memory sync
        def setup_memory_sync():
            """Setup hooks per sincronizzazione automatica memoria tra servizi"""
            
            # Patch metodo save_context del ConversationalLangChainService
            original_get_chain = conversational_service._get_conversation_chain
            
            def synced_get_chain(thread_id: str, schema: dict = None):
                """Wrapper che sincronizza memoria con streaming service"""
                chain = original_get_chain(thread_id, schema)
                
                # Sincronizza memoria con streaming service
                if hasattr(chain, 'memory') and streaming_service:
                    streaming_service.conversations[thread_id] = chain.memory
                
                return chain
            
            # Applica patch
            conversational_service._get_conversation_chain = synced_get_chain
            
            # Patch anche StreamingService per sync inverso
            original_setup_memory = streaming_service.__class__.__dict__.get('stream_mongodb_query_alternative')
            if original_setup_memory:
                async def synced_stream_query(self, thread_id: str, user_input: str, collection_schema: dict):
                    """Wrapper che sincronizza memoria con conversational service"""
                    
                    # Assicurati che la memoria sia sincronizzata
                    if thread_id in self.conversations and hasattr(conversational_service, '_conversation_chains'):
                        # Trova o crea conversation chain corrispondente
                        if thread_id not in conversational_service._conversation_chains:
                            # Forza creazione chain nel servizio normale
                            _ = conversational_service._get_conversation_chain(thread_id, collection_schema)
                    
                    # Chiama metodo originale
                    async for chunk in original_setup_memory(self, thread_id, user_input, collection_schema):
                        yield chunk
                        
                        # Sync memoria dopo ogni chunk (per sicurezza)
                        if thread_id in self.conversations and hasattr(conversational_service, '_conversation_chains'):
                            if thread_id in conversational_service._conversation_chains:
                                chain = conversational_service._conversation_chains[thread_id]
                                if hasattr(chain, 'memory'):
                                    chain.memory = self.conversations[thread_id]
                
                # Applica patch
                streaming_service.stream_mongodb_query_alternative = synced_stream_query.__get__(streaming_service, streaming_service.__class__)
            
            print("✅ Memory sync hooks attivati")
        
        # Attiva sincronizzazione
        setup_memory_sync()
        
        if await streaming_service.health_check():
            print("✅ StreamingService operativo e integrato")
        else:
            print("⚠️ StreamingService health check fallito")

        print("🛡️ AsyncGuard middleware attivo")
        print("🎉 API disponibile: http://localhost:8000")

    except Exception as e:
        print(f"❌ Errore avvio: {e}")
        raise

    yield  # App running

    # ===== SHUTDOWN =====
    print("🛑 Chiusura servizi...")
    try:
        if mongodb_service:
            await mongodb_service.close()
        if conversational_service:
            await conversational_service.cleanup()
        if streaming_service:
            # No explicit cleanup needed for streaming_service since it shares memory
            pass
        print("👋 Shutdown completato")
    except Exception as e:
        print(f"⚠️ Warning durante shutdown: {e}")


# ================================
# FASTAPI APP con GUARDRAILS
# ================================
app = FastAPI(
    title="MongoDB Analytics API con AsyncGuard",
    description="Analytics con ConversationBufferMemory e protezione AsyncGuard streaming",
    version="2.3.0",
    lifespan=lifespan
)



#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Guardrails middleware (new system)
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
app.add_middleware(GuardrailsMiddleware)
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



# Importa ed include le routes separate per migliorare la leggibilità
from routes import router as api_router
app.include_router(api_router)


# ================================
# AVVIO APPLICAZIONE
# ================================

if __name__ == "__main__":
    import uvicorn
    try:
        print("🚀 Avvio MongoDB Analytics API con AsyncGuard")
        print("🛡️ Protezione async input/output attiva")
        # uvicorn gestisce SIGINT/SIGTERM ed esegue correttamente il ciclo di vita FastAPI
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info",
            lifespan="on",
        )
    except KeyboardInterrupt:
        # Intercetta CTRL+C per un messaggio pulito; FastAPI "lifespan" esegue lo shutdown
        print("\n🛑 Ricevuto CTRL+C. Arresto del server in corso...")
    finally:
        print("👋 Shutdown completato (graceful)")