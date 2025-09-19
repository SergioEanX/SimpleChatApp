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
from typing import Dict, Any, TYPE_CHECKING
import uuid
import logging
from starlette.datastructures import State
from typing import cast
from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware

from models import QueryRequest, QueryResponse
from database import MongoDBService
from langchain_service import ConversationalLangChainService

# Guardrails integration
from guardrails_middleware import GuardrailsMiddleware, create_guardrails_config

from guardrails_middleware import analyzer_engine
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.recognizer_registry import RecognizerRegistryProvider
from starlette.datastructures import State

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

# Configurazione Guardrails
GUARDRAILS_CONFIG = create_guardrails_config()


# ================================
# SERVIZI GLOBALI
# ================================

mongodb_service: MongoDBService = None
conversational_service: ConversationalLangChainService = None


# ================================
# LIFESPAN MANAGEMENT
# ================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestisce ciclo di vita applicazione con Guardrails
    """
    # ===== STARTUP =====
    print("🚀 MongoDB Analytics API v2.2 - Con Guardrails")
    print("🛡️ Protezione: Input/Output validation attiva")

    global mongodb_service, conversational_service

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

        print("🛡️ Guardrails middleware attivo")
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
        print("👋 Shutdown completato")
    except Exception as e:
        print(f"⚠️ Warning durante shutdown: {e}")


# ================================
# FASTAPI APP con GUARDRAILS
# ================================
app = FastAPI(
    title="MongoDB Analytics API con Guardrails",
    description="Analytics con ConversationBufferMemory e protezione Guardrails",
    version="2.2.0",
    lifespan=lifespan
)



#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Aggiungi Guardrails middleware
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
app.add_middleware(GuardrailsMiddleware, config=GUARDRAILS_CONFIG)
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# state = cast(State, app.state)
# state.analyzer_engine = analyzer_engine



# Importa ed include le routes separate per migliorare la leggibilità
from routes import router as api_router
app.include_router(api_router)


# ================================
# AVVIO APPLICAZIONE
# ================================

if __name__ == "__main__":
    import uvicorn
    try:
        print("🚀 Avvio MongoDB Analytics API con Guardrails")
        print("🛡️ Protezione input/output attiva")
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