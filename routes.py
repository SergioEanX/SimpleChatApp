"""
routes.py - Endpoint definitions separated from main app for readability.
This module defines an APIRouter with all API endpoints originally in main.py.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime
from typing import Dict, Any, AsyncGenerator
import uuid
import logging
import json

from models import QueryRequest, QueryResponse, StreamingChatRequest

# Logger setup consistent with main
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


# Dependency for logging requests
async def log_request_info(request_data: QueryRequest):
    """Dependency per logging informazioni richiesta"""
    logger.info(f"Query request: {request_data.query[:50]}{'...' if len(request_data.query) > 50 else ''}")
    return request_data


# ================================
# ENDPOINTS PROTETTI DA GUARDRAILS
# ================================

@router.post("/chat")
async def streaming_chat(request: StreamingChatRequest = Depends(log_request_info)):
    """
    Streaming chat endpoint - Real-time response chunks
    
    🛡️ Protetto da AsyncGuard:
    - Input: Controllo PII, Topic, Toxic, Profanity (pre-stream)
    - Output: Validazione contenuto accumulato (post-stream)
    """
    try:
        # Thread ID management
        thread_id = request.session_id or f"thread_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"🔄 Streaming chat - Thread: {thread_id}")
        logger.info(f"📝 User input: {request.query}")
        
        # Return streaming response
        return StreamingResponse(
            stream_chat_response(thread_id, request.query, request.collection),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "X-Thread-ID": thread_id
            }
        )
        
    except Exception as e:
        error_msg = f"Errore durante streaming chat: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


async def stream_chat_response(thread_id: str, user_query: str, collection: str = None) -> AsyncGenerator[str, None]:
    """
    Generator function for streaming chat response
    
    Args:
        thread_id: Session identifier
        user_query: User's input query
        collection: MongoDB collection name
        
    Yields:
        Server-Sent Events formatted strings
    """
    try:
        # Import main per accesso ai servizi
        import main  # type: ignore
        
        # Setup iniziale
        collection = collection or main.COLLECTION_NAME
        
        # Yield initial connection event
        yield f"""data: {json.dumps({
            'type': 'connection',
            'thread_id': thread_id,
            'timestamp': datetime.now().isoformat(),
            'message': 'Connessione streaming stabilita'
        })}\n\n"""
        
        # TODO: Qui andrà l'integrazione con langchain_service streaming
        # Per ora, simuliamo una risposta di test
        
        # Yield start event
        yield f"""data: {json.dumps({
            'type': 'start',
            'thread_id': thread_id,
            'message': 'Elaborazione richiesta iniziata...'
        })}\n\n"""
        
        # Simulate streaming chunks (placeholder)
        test_chunks = [
            "Sto ",
            "elaborando ",
            "la tua ",
            "richiesta ",
            "per ",
            "il thread ",
            f"{thread_id}. ",
            "Questa è ",
            "una risposta ",
            "di test ",
            "per verificare ",
            "il funzionamento ",
            "dello streaming."
        ]
        
        accumulated_content = ""
        
        for i, chunk in enumerate(test_chunks):
            accumulated_content += chunk
            
            # Yield content chunk
            yield f"""data: {json.dumps({
                'type': 'content',
                'thread_id': thread_id,
                'chunk': chunk,
                'chunk_index': i,
                'accumulated_length': len(accumulated_content)
            })}\n\n"""
            
            # Small delay per simulare real streaming
            import asyncio
            await asyncio.sleep(0.1)
        
        # Yield completion event
        yield f"""data: {json.dumps({
            'type': 'complete',
            'thread_id': thread_id,
            'final_content': accumulated_content,
            'total_chunks': len(test_chunks),
            'timestamp': datetime.now().isoformat()
        })}\n\n"""
        
        # Yield final done event
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
    except Exception as e:
        # Yield error event
        yield f"""data: {json.dumps({
            'type': 'error',
            'thread_id': thread_id,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })}\n\n"""
        
        logger.error(f"Errore durante streaming: {e}")


@router.post("/query", response_model=QueryResponse)
async def conversational_query(request: QueryRequest = Depends(log_request_info)):
    """
    Esegue query MongoDB usando ConversationBufferMemory per contesto

    🛡️ Protetto da Guardrails:
    - Input: Controllo PII, profanità, injection attempts
    - Output: Validazione contenuti tossici, formato JSON
    """
    try:
        # Local import to avoid circular dependency and access globals defined in main
        import main  # type: ignore

        # Thread ID management
        thread_id = request.session_id or f"thread_{uuid.uuid4().hex[:8]}"
        collection = request.collection or main.COLLECTION_NAME

        logger.info(f"🔍 Query conversazionale - Thread: {thread_id}")
        logger.info(f"📝 User input: {request.query}")

        # 1. Recupera schema collezione per contesto LLM
        schema = await main.mongodb_service.get_collection_schema(collection)
        logger.info(f"📋 Schema caricato: {len(schema)} campi")

        # 2. Usa ConversationChain con template intelligente
        # Guardrails ha già validato l'input nel middleware
        intelligent_result = await main.conversational_service.generate_mongodb_query(
            thread_id=thread_id,
            user_input=request.query,
            collection_schema=schema
        )

        logger.info(f"🧠 Risultato template intelligente: {type(intelligent_result)}")

        # 3. Gestisci risposta basata sul tipo
        if intelligent_result.get("_type") == "general_response":
            # È una risposta conversazionale generale
            logger.info("💬 Risposta conversazionale generale")

            return QueryResponse(
                session_id=thread_id,
                result=intelligent_result["_content"],  # Sarà validato da Guardrails output
                data_saved=False,
                file_path=None,
                document_count=0,
                created_at=datetime.now()
            )

        elif intelligent_result:
            # È una query MongoDB valida
            logger.info(f"🎯 Query MongoDB: {intelligent_result}")
            mongodb_query = intelligent_result

        else:
            # Fallback query vuota
            logger.info("⚠️ Fallback query vuota")
            mongodb_query = {}

        # 4. Esegui query MongoDB (solo se non è risposta generale)
        documents = await main.mongodb_service.execute_query(collection, mongodb_query)
        doc_count = len(documents)

        logger.info(f"📊 Documenti recuperati: {doc_count}")

        # 5. Gestione response size (salvataggio file se necessario)
        response_size_estimate = len(str(documents))
        size_limit = 50000  # 50KB

        if response_size_estimate > size_limit or doc_count > 25:
            # Salva risultati grandi su file
            file_path = await main.conversational_service.save_large_results(
                documents=documents,
                query_text=request.query,
                thread_id=thread_id
            )

            result_content = (
                f"✅ Query eseguita con successo!\n"
                f"📊 {doc_count} documenti trovati\n"
                f"💾 Risultati salvati su file (dimensioni > {size_limit/1000}KB)\n"
                f"📁 File: {file_path}\n"
                f"⬇️ Usa endpoint /download/{thread_id} per scaricare"
            )
            data_saved = True

        else:
            # Risultati piccoli - mostra direttamente
            import json
            result_content = json.dumps(documents, default=str, indent=2)
            data_saved = False
            file_path = None

        response = QueryResponse(
            session_id=thread_id,
            result=result_content,  # Output sarà validato da Guardrails
            data_saved=data_saved,
            file_path=file_path,
            document_count=doc_count,
            created_at=datetime.now()
        )

        return response

    except Exception as e:
        error_msg = f"Errore durante query conversazionale: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/conversation/{thread_id}/history")
async def get_conversation_history(thread_id: str):
    """
    Recupera storia conversazione usando ConversationBufferMemory

    🛡️ Protetto da Guardrails: Output validation per contenuti storia
    """
    try:
        import main  # type: ignore
        history = await main.conversational_service.get_conversation_history(thread_id)

        # Formatta storia per response
        formatted_messages = []
        for msg in history:
            formatted_messages.append({
                'type': msg.type,  # 'human' o 'ai'
                'content': msg.content[:300] + "..." if len(msg.content) > 300 else msg.content,
                'full_length': len(msg.content)
            })

        return {
            'thread_id': thread_id,
            'total_messages': len(history),
            'conversation_history': formatted_messages,  # Validato da Guardrails
            'memory_type': 'ConversationBufferMemory',
            'guardrails_protected': True
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore recupero storia: {str(e)}"
        )


# ================================
# ENDPOINTS NON PROTETTI (Sistema)
# ================================

@router.get("/conversations")
async def list_active_conversations():
    """Lista conversazioni attive (non protetto da Guardrails)"""
    try:
        import main  # type: ignore
        active_threads = await main.conversational_service.list_active_threads()

        return {
            'active_threads': active_threads,
            'total_count': len(active_threads),
            'memory_approach': 'ConversationBufferMemory',
            'guardrails_protection': 'input/output validation active'
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore listing: {str(e)}")


@router.delete("/conversation/{thread_id}")
async def clear_conversation_memory(thread_id: str):
    """
    Cancella ConversationBufferMemory per thread specifico
    """
    try:
        import main  # type: ignore
        cleared = await main.conversational_service.clear_conversation_memory(thread_id)

        return {
            'thread_id': thread_id,
            'memory_cleared': cleared,
            'status': 'success' if cleared else 'thread_not_found',
            'message': 'ConversationBufferMemory pulita' if cleared else 'Thread inesistente'
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore clear: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check con info memoria e Guardrails"""
    try:
        import main  # type: ignore
        # Test servizi
        mongo_healthy = await main.mongodb_service.health_check()
        llm_healthy = await main.conversational_service.health_check()

        # Info memoria
        active_conversations = await main.conversational_service.list_active_threads()

        overall_status = 'healthy' if (mongo_healthy and llm_healthy) else 'degraded'

        return {
            'status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'services': {
                'mongodb': '✅ Healthy' if mongo_healthy else '❌ Issues',
                'ollama_llm': '✅ Healthy' if llm_healthy else '❌ Issues',
                'guardrails': '✅ Active'
            },
            'memory': {
                'type': 'ConversationBufferMemory',
                'active_conversations': len(active_conversations),
                'threads': active_conversations[:5] if len(active_conversations) > 5 else active_conversations
            },
            'protection': {
                'guardrails_middleware': True,
                'input_validation': ['PII_detection', 'toxicity_filter', 'injection_protection'],
                'output_validation': ['content_filter', 'JSON_validation', 'toxicity_filter']
            },
            'config': {
                'ollama_model': main.OLLAMA_MODEL,
                'database': main.DATABASE_NAME,
                'default_collection': main.COLLECTION_NAME
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/guardrails/status")
async def guardrails_status():
    """Endpoint per monitorare stato Guardrails"""
    try:
        import main  # type: ignore
        return {
            'guardrails_active': True,
            'protected_endpoints': ['/query', '/conversation/{thread_id}/history'],
            'input_validators': [
                'ToxicLanguage',
                'ProfanityFree',
                'DetectPII'
            ],
            'output_validators': [
                'ToxicLanguage',
                'ProfanityFree',
                'NoInvalidJSON'
            ],
            'config': main.GUARDRAILS_CONFIG
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def root():
    """Root endpoint con info API e Guardrails"""
    try:
        import main  # type: ignore
        return {
            'name': 'MongoDB Analytics API con Guardrails',
            'version': '2.2.0',
            'memory_approach': 'ConversationBufferMemory',
            'protection': 'Guardrails Input/Output Validation',
            'description': 'API per analytics MongoDB con memoria conversazionale protetta',
            'endpoints': {
                'query': 'POST /query - Esegui query conversazionale [PROTETTO]',
                'history': 'GET /conversation/{thread_id}/history - Storia thread [PROTETTO]',
                'conversations': 'GET /conversations - Lista thread attivi',
                'clear': 'DELETE /conversation/{thread_id} - Pulisci memoria',
                'health': 'GET /health - Status servizi + Guardrails',
                'guardrails': 'GET /guardrails/status - Stato protezioni',
                'docs': 'GET /docs - Documentazione OpenAPI'
            },
            'security_features': [
                'PII Detection & Blocking',
                'Toxic Content Filtering',
                'SQL/NoSQL Injection Protection',
                'Profanity Filtering',
                'Output Content Validation',
                'JSON Format Validation'
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
