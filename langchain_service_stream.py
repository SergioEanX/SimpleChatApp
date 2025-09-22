"""
langchain_service_stream.py - Streaming Implementation for LangChain Service
===========================================================================

Modulo separato per funzionalità streaming che estende langchain_service.py
senza modificare il codice esistente. Approccio sicuro per rollback rapido.

Author: SimpleChatApp
Version: 1.0.0
"""

import logging
import json
from typing import AsyncGenerator, Optional, Dict, Any, List
from datetime import datetime

# Import delle classi base
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain_community.chat_models import ChatOllama
from langchain.schema import BaseMessage

logger = logging.getLogger(__name__)


class StreamingService:
    """
    Servizio streaming che estende le funzionalità di ConversationalLangChainService
    
    Questo servizio può essere usato standalone o come extension del servizio esistente.
    Mantiene compatibilità completa con ConversationBufferMemory.
    """
    
    def __init__(self, model_name: str = "gemma3:latest", base_url: str = "http://localhost:11434"):
        """
        Inizializza il servizio streaming
        
        Args:
            model_name: Nome del modello Ollama
            base_url: URL base per Ollama
        """
        self.model_name = model_name
        self.base_url = base_url
        
        # Setup LLM con streaming enabled
        self.llm = ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.1,
            streaming=True,  # IMPORTANTE: Abilita streaming
            verbose=True
        )
        
        # Cache per conversazioni (shared con servizio principale se necessario)
        self.conversations: Dict[str, ConversationBufferMemory] = {}
        
        # System prompt per MongoDB analytics E conversazione
        self.system_prompt = """Sei un assistente AI chiamato Claude che può aiutare con conversazioni e query MongoDB.

RUOLO E IDENTITÀ:
- Tu sei l'ASSISTENTE AI
- L'utente è la PERSONA che ti sta parlando
- NON confondere mai i ruoli: tu sei Claude, l'utente è l'utente

COMPORTAMENTO:
1. **CONVERSAZIONE NORMALE**: Rispondi come assistente amichevole
2. **QUERY MONGODB**: Genera JSON solo per richieste esplicite di ricerca dati

ESEMPI RUOLI CORRETTI:
Utente: "Mi chiamo Mario e ho 30 anni"
Assistente: "Piacere Mario! Ho preso nota che ti chiami Mario e hai 30 anni. Come posso aiutarti?"

Utente: "Come mi chiamo?"
Assistente: "Ti chiami Mario, come mi hai detto prima."

MONGODB (genera JSON quando richiesto):
- "Cerca utenti età > 25" → {{"eta": {{"$gt": 25}}}}
- "Trova Mario" → {{"nome": {{"$regex": "Mario"}}}}

RICORDA:
- Mantieni sempre la tua identità di assistente
- Ricorda informazioni che l'utente condivide su se stesso
- Rispondi sempre dalla prospettiva di assistente AI
"""
        
        logger.info(f"✅ StreamingService inizializzato con modello: {model_name}")
    
    async def stream_mongodb_query(
        self, 
        thread_id: str, 
        user_input: str, 
        collection_schema: dict
    ) -> AsyncGenerator[str, None]:
        """
        Versione streaming di generate_mongodb_query usando ConversationChain.astream()
        
        Args:
            thread_id: ID del thread conversazione
            user_input: Input dell'utente
            collection_schema: Schema della collezione MongoDB
            
        Yields:
            str: Chunks di risposta in tempo reale
        """
        try:
            logger.info(f"🔄 Starting streaming for thread {thread_id}")
            
            # Setup memoria conversazionale
            if thread_id not in self.conversations:
                self.conversations[thread_id] = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True
                )
            
            memory = self.conversations[thread_id]
            
            # Crea chain conversazionale
            conversation_chain = ConversationChain(
                llm=self.llm,
                memory=memory,
                prompt=self._create_intelligent_prompt_template(collection_schema),
                verbose=True
            )
            
            accumulated_response = ""
            chunk_count = 0
            
            # **STREAMING REALE** tramite ConversationChain.astream()
            async for chunk in conversation_chain.astream({"input": user_input}):
                chunk_count += 1
                
                # ConversationChain.astream() restituisce dict con chiavi specifiche
                chunk_content = ""
                if isinstance(chunk, dict):
                    # Estrai il contenuto dal chunk
                    if "response" in chunk:
                        chunk_content = chunk["response"]
                    elif "output" in chunk:
                        chunk_content = chunk["output"]
                    elif "text" in chunk:
                        chunk_content = chunk["text"]
                    else:
                        # Prova a estrarre dal primo valore non-vuoto
                        for key, value in chunk.items():
                            if isinstance(value, str) and value.strip():
                                chunk_content = value
                                break
                else:
                    chunk_content = str(chunk)
                
                if chunk_content:
                    accumulated_response += chunk_content
                    logger.debug(f"📦 Chunk {chunk_count}: {len(chunk_content)} chars")
                    yield chunk_content
            
            logger.info(f"✅ Streaming completato per thread {thread_id}: {chunk_count} chunks, {len(accumulated_response)} caratteri")
            
        except Exception as e:
            logger.error(f"❌ Errore durante streaming: {e}")
            error_msg = f"Errore durante elaborazione streaming: {str(e)}"
            yield error_msg

    async def stream_mongodb_query_alternative(
        self, 
        thread_id: str, 
        user_input: str, 
        collection_schema: dict
    ) -> AsyncGenerator[str, None]:
        """
        METODO ALTERNATIVO: Streaming usando direttamente ChatOllama.astream()
        
        Usa questo metodo se ConversationChain.astream() non funziona come aspettato.
        Gestisce manualmente la memoria conversazionale.
        
        Args:
            thread_id: ID del thread conversazione
            user_input: Input dell'utente
            collection_schema: Schema della collezione MongoDB
            
        Yields:
            str: Chunks di risposta in tempo reale
        """
        try:
            logger.info(f"🔄 Starting alternative streaming for thread {thread_id}")
            
            # Setup memoria
            if thread_id not in self.conversations:
                self.conversations[thread_id] = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True
                )
            
            memory = self.conversations[thread_id]
            
            # Recupera storia conversazione
            chat_history = memory.load_memory_variables({}).get("chat_history", [])
            
            # Crea prompt completo manualmente
            full_prompt = self._create_full_prompt_with_history(
                user_input, 
                collection_schema, 
                chat_history
            )
            
            accumulated_response = ""
            chunk_count = 0
            
            # **STREAMING DIRETTO** tramite ChatOllama.astream()
            # MODIFICA: Usa astream con prompt text direttamente
            from langchain.schema import HumanMessage
            
            async for chunk in self.llm.astream([HumanMessage(content=full_prompt)]):
                chunk_count += 1
                
                # Estrai contenuto dal chunk
                chunk_content = ""
                if hasattr(chunk, 'content'):
                    chunk_content = chunk.content
                elif hasattr(chunk, 'text'):
                    chunk_content = chunk.text
                else:
                    chunk_content = str(chunk)
                
                if chunk_content:
                    accumulated_response += chunk_content
                    logger.debug(f"📦 Alt chunk {chunk_count}: {len(chunk_content)} chars")
                    yield chunk_content
            
            # Salva manualmente in memoria dopo streaming
            memory.save_context(
                {"input": user_input},
                {"output": accumulated_response}
            )
            
            logger.info(f"✅ Alternative streaming completato: {chunk_count} chunks, {len(accumulated_response)} caratteri")
            
        except Exception as e:
            logger.error(f"❌ Errore durante alternative streaming: {e}")
            yield f"Errore alternative streaming: {str(e)}"

    def _create_intelligent_prompt_template(self, collection_schema: dict):
        """
        Crea template prompt intelligente per ConversationChain
        
        Args:
            collection_schema: Schema della collezione MongoDB
            
        Returns:
            PromptTemplate configurato per MongoDB analytics
        """
        from langchain.prompts import PromptTemplate
        
        schema_context = self._format_schema_for_prompt(collection_schema)
        
        template = f"""
{self.system_prompt}

SCHEMA COLLEZIONE MONGODB:
{schema_context}

CRONOLOGIA CONVERSAZIONE:
{{chat_history}}

RICHIESTA UTENTE: {{input}}

RISPOSTA:"""
        
        return PromptTemplate(
            input_variables=["chat_history", "input"],
            template=template
        )

    def _create_full_prompt_with_history(
        self, 
        user_input: str, 
        collection_schema: dict, 
        chat_history: List[BaseMessage]
    ) -> str:
        """
        Crea prompt completo con schema e storia conversazione
        
        Args:
            user_input: Input dell'utente
            collection_schema: Schema collezione MongoDB
            chat_history: Lista messaggi conversazione
            
        Returns:
            str: Prompt completo formattato
        """
        # Formatta schema
        schema_context = self._format_schema_for_prompt(collection_schema)
        
        # Formatta storia (ultimi 10 messaggi per non superare context limit)
        history_context = ""
        recent_messages = chat_history[-10:] if len(chat_history) > 10 else chat_history
        
        for message in recent_messages:
            if hasattr(message, 'content') and hasattr(message, 'type'):
                role = "Human" if message.type == "human" else "Assistant"
                content = message.content[:500]  # Limit message length
                history_context += f"{role}: {content}\n"
        
        # Prompt completo
        full_prompt = f"""
{self.system_prompt}

SCHEMA COLLEZIONE MONGODB:
{schema_context}

CRONOLOGIA CONVERSAZIONE:
{history_context}

RICHIESTA UTENTE: {user_input}

RISPOSTA:"""
        
        return full_prompt

    def _format_schema_for_prompt(self, collection_schema: dict) -> str:
        """
        Formatta schema MongoDB per inclusione nel prompt
        
        Args:
            collection_schema: Schema della collezione
            
        Returns:
            str: Schema formattato per prompt
        """
        if not collection_schema:
            return "Schema non disponibile - usa query generiche"
        
        schema_lines = []
        for field, details in collection_schema.items():
            if isinstance(details, dict):
                field_type = details.get('type', 'unknown')
                field_desc = details.get('description', '')
                line = f"- {field}: {field_type}"
                if field_desc:
                    line += f" ({field_desc})"
                schema_lines.append(line)
            else:
                schema_lines.append(f"- {field}: {str(details)}")
        
        return "\n".join(schema_lines)

    async def get_conversation_memory(self, thread_id: str) -> Optional[ConversationBufferMemory]:
        """
        Recupera memoria conversazione per thread ID
        
        Args:
            thread_id: ID del thread
            
        Returns:
            ConversationBufferMemory o None se non esiste
        """
        return self.conversations.get(thread_id)

    async def clear_conversation_memory(self, thread_id: str) -> bool:
        """
        Pulisce memoria per thread specifico
        
        Args:
            thread_id: ID del thread da pulire
            
        Returns:
            bool: True se pulito con successo
        """
        if thread_id in self.conversations:
            del self.conversations[thread_id]
            logger.info(f"🧹 Memoria conversazione pulita per thread: {thread_id}")
            return True
        return False

    async def health_check(self) -> bool:
        """
        Verifica stato del servizio streaming
        
        Returns:
            bool: True se servizio disponibile
        """
        try:
            # Test semplice con LLM
            test_prompt = "Test connection"
            response_received = False
            
            async for chunk in self.llm.astream(test_prompt):
                response_received = True
                break  # Basta il primo chunk per confermare connessione
            
            logger.info("✅ StreamingService health check passed")
            return response_received
            
        except Exception as e:
            logger.error(f"❌ StreamingService health check failed: {e}")
            return False

    def get_stats(self) -> dict:
        """
        Statistiche del servizio streaming
        
        Returns:
            dict: Statistiche correnti
        """
        return {
            "service": "StreamingService",
            "model": self.model_name,
            "base_url": self.base_url,
            "active_conversations": len(self.conversations),
            "conversation_threads": list(self.conversations.keys()),
            "streaming_enabled": True,
            "created_at": datetime.now().isoformat()
        }


# Factory function per facilità d'uso
async def create_streaming_service(
    model_name: str = "gemma3:latest", 
    base_url: str = "http://localhost:11434"
) -> StreamingService:
    """
    Factory per creare istanza StreamingService
    
    Args:
        model_name: Nome modello Ollama
        base_url: URL Ollama
        
    Returns:
        StreamingService: Istanza configurata
    """
    service = StreamingService(model_name, base_url)
    
    # Test connessione
    if await service.health_check():
        logger.info(f"✅ StreamingService creato e testato con successo")
        return service
    else:
        logger.warning(f"⚠️ StreamingService creato ma health check fallito")
        return service


# Utility per integrazione con servizio esistente
def integrate_with_existing_service(existing_service, streaming_service):
    """
    Integra StreamingService con ConversationalLangChainService esistente
    
    Args:
        existing_service: Istanza di ConversationalLangChainService
        streaming_service: Istanza di StreamingService
    """
    # Condividi conversazioni se compatibile
    if hasattr(existing_service, 'conversations'):
        streaming_service.conversations = existing_service.conversations
        logger.info("🔗 Conversazioni condivise tra servizi")
    
    # Condividi configurazione LLM
    if hasattr(existing_service, 'llm'):
        if existing_service.llm.model == streaming_service.llm.model:
            logger.info("✅ Configurazione LLM compatibile")
        else:
            logger.warning("⚠️ Configurazione LLM diversa tra servizi")


if __name__ == "__main__":
    # Test standalone del servizio
    import asyncio
    
    async def test_streaming():
        """Test rapido del servizio streaming"""
        print("🧪 Testing StreamingService...")
        
        service = await create_streaming_service()
        
        # Test streaming
        test_query = "Crea una query per trovare tutti i documenti"
        test_schema = {"name": {"type": "string"}, "age": {"type": "number"}}
        
        print("📤 Test query:", test_query)
        print("📥 Streaming response:")
        
        async for chunk in service.stream_mongodb_query("test_thread", test_query, test_schema):
            print(f"  📦 {chunk}", end="", flush=True)
        
        print("\n✅ Test completato")
        print("📊 Stats:", service.get_stats())
    
    asyncio.run(test_streaming())
