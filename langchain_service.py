"""
langchain_service.py - ConversationalLangChainService
====================================================

Servizio LangChain con ConversationBufferMemory per gestione intelligente
di query MongoDB vs conversazione generale.
"""

from langchain_ollama import OllamaLLM
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain.schema import BaseMessage
from langchain.prompts import PromptTemplate
from typing import Dict, List, Any, Optional
import json
import pandas as pd
from pathlib import Path
from datetime import datetime


class ConversationalLangChainService:
    """
    Servizio LangChain con ConversationBufferMemory per thread isolation.
    Template intelligente che decide se generare JSON MongoDB o risposta generale.
    """

    def __init__(self, model_name: str, base_url: str):
        """
        Inizializza servizio con LLM Ollama e memoria conversazionale.

        Args:
            model_name: Nome modello Ollama
            base_url: URL base Ollama
        """
        self.model_name = model_name
        self.base_url = base_url

        # Inizializza LLM
        self.llm = OllamaLLM(
            model=model_name,
            base_url=base_url,
            temperature=0.1,
            timeout=60
        )

        # Storage ConversationChain per thread
        self._conversation_chains: Dict[str, ConversationChain] = {}

        # Template prompt intelligente
        self.prompt_template = self._create_intelligent_prompt_template()

        # Directory temporanea
        self.temp_dir = Path("temp_results")
        self.temp_dir.mkdir(exist_ok=True)

        print(f"ConversationalLangChainService inizializzato - Modello: {model_name}")

    def _create_intelligent_prompt_template(self) -> PromptTemplate:
        """
        Crea template che decide tra conversazione naturale e query MongoDB.
        """
        template = """Sei un assistente AI chiamato Claude che può aiutare con conversazioni e query MongoDB.

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

Utente: "Chi sei tu?"
Assistente: "Sono Claude, il tuo assistente AI."

MONGODB (genera JSON quando richiesto):
- "Cerca utenti età > 25" → {{"eta": {{"$gt": 25}}}}
- "Trova Mario" → {{"nome": {{"$regex": "Mario"}}}}
- "Tutti i documenti" → {{}}

RICORDA:
- Mantieni sempre la tua identità di assistente
- Ricorda informazioni che l'utente condivide su se stesso
- Rispondi sempre dalla prospettiva di assistente AI

Schema disponibile: {schema}

Conversazione:
{history}

Utente: {input}

Assistente:"""

        return PromptTemplate(
            input_variables=["history", "input", "schema"],
            template=template
        )

    def _get_conversation_chain(self, thread_id: str, schema: dict = None) -> ConversationChain:
        """
        Recupera o crea ConversationChain con BufferMemory per thread.
        """
        if thread_id not in self._conversation_chains:
            # Crea memoria buffer
            memory = ConversationBufferMemory(
                memory_key="history",
                return_messages=False,
                human_prefix="Utente",
                ai_prefix="Assistente"
            )

            # Schema text - format as simple list to avoid template variable conflicts
            if schema:
                schema_fields = [f"- {field}" for field in schema.keys()]
                schema_text = "Campi disponibili:\n" + "\n".join(schema_fields) if schema_fields else "Schema vuoto"
            else:
                schema_text = "Schema non disponibile"

            # Crea ConversationChain con partial variables per schema
            conversation = ConversationChain(
                llm=self.llm,
                memory=memory,
                prompt=self.prompt_template.partial(schema=schema_text),
                verbose=False
            )

            self._conversation_chains[thread_id] = conversation
            print(f"Nuova conversazione per thread: {thread_id}")

        return self._conversation_chains[thread_id]

    async def generate_mongodb_query(
            self,
            thread_id: str,
            user_input: str,
            collection_schema: dict
    ) -> dict:
        """
        Genera query MongoDB o risposta generale usando template intelligente.

        Returns:
            Dict MongoDB query o dict con _type='general_response'
        """
        try:
            # Recupera conversazione
            conversation = self._get_conversation_chain(thread_id, collection_schema)

            print(f"Elaborazione per thread {thread_id}: {user_input}")

            # Genera risposta
            llm_response = await conversation.apredict(input=user_input)

            print(f"LLM response: {llm_response[:150]}...")

            # Processa risposta
            result = self._process_intelligent_response(llm_response, user_input)
            return result

        except Exception as e:
            print(f"Errore elaborazione: {e}")
            return {}

    def _process_intelligent_response(self, llm_response: str, user_input: str) -> dict:
        """
        Processa risposta LLM e determina se e MongoDB query o conversazione generale.
        """
        try:
            # Tenta parse JSON MongoDB
            mongodb_query = self._parse_mongodb_json(llm_response)

            if mongodb_query:
                print(f"Rilevata query MongoDB: {mongodb_query}")
                return mongodb_query

            # Risposta conversazionale
            print("Rilevata risposta conversazionale")
            return {
                "_type": "general_response",
                "_content": llm_response.strip(),
                "_original_query": user_input
            }

        except Exception as e:
            print(f"Errore processing response: {e}")
            return {}

    def _parse_mongodb_json(self, llm_response: str) -> dict:
        """
        Parse risposta LLM in query MongoDB valida.
        """
        try:
            cleaned = llm_response.strip()

            # Rimuovi code blocks
            if "```" in cleaned:
                lines = cleaned.split('\n')
                json_lines = []
                in_code_block = False

                for line in lines:
                    if line.strip().startswith('```'):
                        in_code_block = not in_code_block
                        continue
                    if not line.strip().startswith('```'):
                        json_lines.append(line)

                cleaned = '\n'.join(json_lines).strip()

            # Parse JSON solo se sembra JSON
            if cleaned.startswith('{') and cleaned.endswith('}'):
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    return parsed

            return {}

        except json.JSONDecodeError:
            return {}
        except Exception as e:
            print(f"Parse error: {e}")
            return {}

    async def get_conversation_history(self, thread_id: str) -> List[BaseMessage]:
        """
        Recupera storia conversazione da ConversationBufferMemory.
        """
        if thread_id not in self._conversation_chains:
            return []

        try:
            conversation = self._conversation_chains[thread_id]
            memory = conversation.memory
            messages = memory.chat_memory.messages
            return messages

        except Exception as e:
            print(f"Errore recupero storia: {e}")
            return []

    async def clear_conversation_memory(self, thread_id: str) -> bool:
        """
        Pulisce ConversationBufferMemory per thread.
        """
        if thread_id not in self._conversation_chains:
            return False

        try:
            conversation = self._conversation_chains[thread_id]
            conversation.memory.clear()
            del self._conversation_chains[thread_id]
            print(f"Memoria pulita per thread: {thread_id}")
            return True

        except Exception as e:
            print(f"Errore pulizia memoria: {e}")
            return False

    async def list_active_threads(self) -> List[str]:
        """
        Lista thread con conversazioni attive.
        """
        return list(self._conversation_chains.keys())

    async def save_large_results(
            self,
            documents: List[dict],
            query_text: str,
            thread_id: str
    ) -> str:
        """
        Salva risultati grandi in file Parquet.
        """
        try:
            df = pd.DataFrame(documents)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{thread_id}_{timestamp}.parquet"
            file_path = self.temp_dir / filename

            df.to_parquet(file_path, index=False)
            print(f"Salvati {len(documents)} documenti in {filename}")
            return str(file_path)

        except Exception as e:
            error_msg = f"Errore salvataggio: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    async def test_connection(self) -> bool:
        """
        Test connessione Ollama LLM.
        """
        try:
            response = await self.llm.ainvoke("test connection")
            success = len(response.strip()) > 0
            print(f"Test LLM: {'OK' if success else 'FAILED'}")
            return success
        except Exception as e:
            print(f"Test LLM fallito: {e}")
            return False

    async def health_check(self) -> bool:
        """
        Health check completo servizio.
        """
        try:
            llm_ok = await self.test_connection()
            active_threads = len(self._conversation_chains)
            print(f"Health check: LLM={'OK' if llm_ok else 'FAILED'}, Threads={active_threads}")
            return llm_ok

        except Exception as e:
            print(f"Health check fallito: {e}")
            return False

    async def cleanup(self) -> None:
        """
        Cleanup completo servizio.
        """
        try:
            # Clear conversazioni
            cleared_count = 0
            for thread_id in list(self._conversation_chains.keys()):
                if await self.clear_conversation_memory(thread_id):
                    cleared_count += 1

            print(f"Pulite {cleared_count} conversazioni")

            # Cleanup file temporanei vecchi
            import time
            cutoff = time.time() - (24 * 3600)

            cleaned_files = 0
            for file_path in self.temp_dir.glob("*.parquet"):
                if file_path.stat().st_mtime < cutoff:
                    file_path.unlink()
                    cleaned_files += 1

            if cleaned_files > 0:
                print(f"Rimossi {cleaned_files} file temporanei")

        except Exception as e:
            print(f"Warning durante cleanup: {e}")