# LangChain Service - Guida Tecnica Completa

Spiegazione dettagliata di `langchain_service.py` e implementazione ConversationBufferMemory.

## 🎯 Panoramica e Flusso Logico Generale

### **Architettura Complessiva**

Il `ConversationalLangChainService` implementa un sistema ibrido che:

1. **Analizza automaticamente** le richieste dell'utente
2. **Decide il tipo di risposta** (MongoDB JSON vs conversazione generale)
3. **Mantiene memoria** per ogni thread di conversazione
4. **Gestisce risultati grandi** salvandoli su file

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Utente    │───▶│  Template        │───▶│   Ollama LLM    │
│   Input     │    │  Intelligente    │    │   (gemma3)      │
└─────────────┘    └──────────────────┘    └─────────────────┘
│                        │
▼                        ▼
┌─────────────────┐    ┌─────────────────┐
│ ConversationBuf │    │ Risposta        │
│ ferMemory       │    │ Processata      │
│ (per thread)    │    └─────────────────┘
└─────────────────┘              │
│                       ▼
│              ┌─────────────────┐
│              │ MongoDB Query   │
│              │ o Testo         │
└──────────────│ Conversazionale │
└─────────────────┘
```

### **Flusso Logico Passo-Passo**

#### **1. Inizializzazione**
```python
service = ConversationalLangChainService("gemma2:latest", "http://localhost:11434")
```
- Crea istanza LLM Ollama
- Prepara template "intelligente"
- Inizializza cache per ConversationChain

#### **2. Prima Richiesta (Nuovo Thread)**
```python
result = await service.generate_mongodb_query("thread_123", "ciao mi chiamo Marco", schema)
```
- Crea nuovo thread `thread_123`
- Istanza `ConversationBufferMemory` dedicata
- Crea `ConversationChain` (LLM + Memory + Prompt)
- Template analizza: "È conversazione generale"
- Restituisce: `{"_type": "general_response", "_content": "Ciao Marco!"}`

#### **3. Richiesta Successiva (Thread Esistente)**
```python
result = await service.generate_mongodb_query("thread_123", "mostra utenti attivi", schema)
```
- Recupera `ConversationChain` esistente per `thread_123`
- Memory automaticamente include storia: "Utente: ciao mi chiamo Marco, Assistente: Ciao Marco!"
- Template analizza con contesto: "È richiesta dati"
- Restituisce: `{"status": "attivo"}`

### **Template Intelligente - Logica Decisionale**

Il template contiene istruzioni che guidano il modello:

```
COMPORTAMENTO:
- Se richiesta riguarda dati/database/query: genera SOLO JSON MongoDB valido
- Se domanda generale: rispondi in linguaggio naturale
```

**Esempi di decisioni:**
- `"cosa è RAG?"` → Conversazione generale → Risposta testuale
- `"mostra utenti"` → Richiesta dati → JSON MongoDB `{}`
- `"ordina per data"` (con contesto) → Richiesta dati → `{"$sort": {"data": -1}}`

---

## 🏗️ Spiegazione della Classe e Metodi

### **Classe ConversationalLangChainService**

```python
class ConversationalLangChainService:
    """
    Servizio che espone conversazioni thread-based con template intelligente
    """
```

#### **Attributi Principali**

| Attributo | Tipo | Descrizione |
|-----------|------|-------------|
| `llm` | `OllamaLLM` | Istanza LLM Ollama configurata |
| `_conversation_chains` | `Dict[str, ConversationChain]` | Cache chains per thread |
| `prompt_template` | `PromptTemplate` | Template intelligente condiviso |
| `temp_dir` | `Path` | Directory file Parquet temporanei |

### **📋 Metodi Principali**

#### **`__init__(model_name: str, base_url: str)`**
**Scopo:** Inizializzazione completa del servizio

```python
def __init__(self, model_name: str, base_url: str):
    # Configura LLM Ollama
    self.llm = OllamaLLM(
        model=model_name,
        base_url=base_url,
        temperature=0.1,      # Bassa per determinismo
        timeout=180,          # 3 minuti timeout
        num_predict=4096,     # Max tokens risposta
        stop=None,           # Nessun troncamento
    )

    # Cache conversation chains
    self._conversation_chains: Dict[str, ConversationChain] = {}

    # Template intelligente
    self.prompt_template = self._create_intelligent_prompt_template()
```

**Dettagli configurazione LLM:**
- `temperature=0.1`: Risposte più deterministiche (meno creative)
- `num_predict=4096`: Token massimi per evitare troncamento
- `timeout=180`: 3 minuti per risposte complesse
- `stop=None`: Evita interruzioni premature

#### **`_create_intelligent_prompt_template() → PromptTemplate`**
**Scopo:** Crea template che decide autonomamente il tipo di risposta

```python
template = """Sei un assistente intelligente con expertise MongoDB e conoscenza generale.

COMPORTAMENTO:
- Se richiesta riguarda dati/database/query: genera SOLO JSON MongoDB valido
- Se domanda generale: rispondi in linguaggio naturale

OPERATORI MONGODB:
- Filtro: campo uguale valore
- Confronto: eta maggiore di 30 usa $gt
- Ordinamento: $sort con campo -1 per decrescente
- Limite: $limit con numero

Schema: {schema}
Storia: {history}
Richiesta: {input}

Rispondi:"""
```

**Caratteristiche chiave:**
- **Input variables:** `["history", "input", "schema"]`
- **Esempi semplificati:** Evita `{}` che confondono LangChain
- **Istruzioni chiare:** Decisione binaria tra JSON e testo
- **Schema dinamico:** Inserito via `.partial()` method

#### **`_get_conversation_chain(thread_id: str, schema: dict) → ConversationChain`**
**Scopo:** Pattern Factory per ConversationChain thread-specifiche

```python
def _get_conversation_chain(self, thread_id: str, schema: dict = None) -> ConversationChain:
    if thread_id in self._conversation_chains:
        return self._conversation_chains[thread_id]  # Cache hit

    # Crea nuova memoria buffer
    memory = ConversationBufferMemory(
        memory_key="history",           # Chiave per template
        return_messages=False,          # String format per template
        human_prefix="Utente",          # Prefisso messaggi utente
        ai_prefix="Assistente"          # Prefisso risposte AI
    )

    # Schema come partial variable (evita problemi template)
    schema_text = json.dumps(schema or {}, indent=2, default=str)

    # Crea ConversationChain completa
    conversation = ConversationChain(
        llm=self.llm,
        memory=memory,
        prompt=self.prompt_template.partial(schema=schema_text),
        verbose=False
    )

    # Cache per riuso
    self._conversation_chains[thread_id] = conversation
    return conversation
```

**Dettagli ConversationBufferMemory:**
- **`memory_key="history"`**: Nome variabile nel template
- **`return_messages=False`**: Formatta come stringa, non lista BaseMessage
- **Thread isolation**: Ogni thread ha la sua memoria indipendente
- **Prefissi custom**: "Utente:" e "Assistente:" per chiarezza

#### **`generate_mongodb_query(thread_id, user_input, collection_schema) → dict`**
**Scopo:** Metodo principale - orchestrazione completa

```python
async def generate_mongodb_query(self, thread_id: str, user_input: str, collection_schema: dict) -> dict:
    try:
        # 1. Recupera/crea ConversationChain
        conversation = self._get_conversation_chain(thread_id, collection_schema)

        # 2. Esegue chain (LLM + Memory + Prompt automaticamente)
        llm_response = await conversation.apredict(input=user_input)

        # 3. Analizza e classifica risposta
        result = self._process_intelligent_response(llm_response, user_input)

        return result
    except Exception as e:
        return {}  # Fallback sicuro
```

**Flusso interno `conversation.apredict()`:**
1. **Memory loading**: `ConversationBufferMemory` recupera storia
2. **Template population**: Sostituisce `{history}` e `{input}`
3. **LLM invocation**: Invia prompt completo a Ollama
4. **Memory saving**: Salva automaticamente user input e AI response
5. **Return response**: Restituisce risposta LLM raw

#### **`_process_intelligent_response(llm_response: str, user_input: str) → dict`**
**Scopo:** Classificazione e parsing della risposta LLM

```python
def _process_intelligent_response(self, llm_response: str, user_input: str) -> dict:
    # Tenta parsing JSON MongoDB
    mongodb_query = self._parse_mongodb_json(llm_response)

    if mongodb_query:  # È JSON valido
        return mongodb_query  # Query MongoDB diretta

    # Altrimenti è conversazione generale
    return {
        "_type": "general_response",
        "_content": llm_response.strip(),
        "_original_query": user_input
    }
```

**Logica di classificazione:**
1. **Prima prova parsing JSON**: Se riesce → è query MongoDB
2. **Se fallisce parsing**: È risposta conversazionale generale
3. **Formato speciale**: `_type` permette a `main.py` di distinguere

#### **`_parse_mongodb_json(llm_response: str) → dict`**
**Scopo:** Parser robusto per JSON MongoDB da testo LLM

```python
def _parse_mongodb_json(self, llm_response: str) -> dict:
    cleaned = llm_response.strip()

    # Rimuovi code blocks (```json ... ```)
    if "```" in cleaned:
    # ... codice per estrarre contenuto tra backticks

    # Parse solo se sembra JSON
    if cleaned.startswith('{') and cleaned.endswith('}'):
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    return {}  # Non è JSON valido
```

**Robustezza parser:**
- **Code block handling**: Rimuove ``` automaticamente
- **Validation**: Verifica sia dict valido
- **Safe fallback**: Return `{}` invece di exception
- **Format detection**: Parse solo se "sembra" JSON

#### **`get_conversation_history(thread_id: str) → List[BaseMessage]`**
**Scopo:** Accesso diretto alla memoria conversazionale

```python
async def get_conversation_history(self, thread_id: str) -> List[BaseMessage]:
    if thread_id not in self._conversation_chains:
        return []

    conversation = self._conversation_chains[thread_id]
    messages = conversation.memory.chat_memory.messages
    return messages
```

**Struttura memoria:**
- `ConversationBufferMemory.chat_memory.messages` → `List[BaseMessage]`
- Ogni `BaseMessage` ha `type` ("human"/"ai") e `content`
- Storia completa mantenuta fino a clear

#### **`save_large_results(documents, query_text, thread_id) → str`**
**Scopo:** Persistenza risultati grandi su file system

```python
async def save_large_results(self, documents: List[dict], query_text: str, thread_id: str) -> str:
    df = pd.DataFrame(documents)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{thread_id}_{timestamp}.parquet"
    file_path = self.temp_dir / filename

    df.to_parquet(file_path, index=False)
    return str(file_path)
```

**Vantaggi Parquet:**
- **Compressione efficiente**: ~70% più piccolo di JSON
- **Schema preservato**: Tipi dati mantenuti
- **Velocità lettura**: Ottimizzato per analytics
- **Compatibilità**: Pandas, Spark, DuckDB

### **🔧 Metodi di Utilità**

#### **Gestione Thread**
```python
# Lista thread attivi
async def list_active_threads(self) -> List[str]

# Pulizia memoria thread  
async def clear_conversation_memory(self, thread_id: str) -> bool

# Cleanup generale (memoria + file)
async def cleanup(self) -> None
    ```

#### **Health & Monitoring**
```python
# Test connessione LLM
async def test_connection(self) -> bool

# Health check completo
async def health_check(self) -> bool
    ```

---

## 🎯 Note Finali e Possibili Miglioramenti

### **🚀 Punti di Forza Attuali**

#### **1. Template Intelligente**
- **Decisione automatica**: Nessuna configurazione manuale
- **Contesto conversazionale**: Usa storia per decisioni migliori
- **Robustezza**: Gestisce edge cases e parsing failures

#### **2. Memoria Thread-Based**  
- **Isolamento perfetto**: Thread indipendenti
- **Standard LangChain**: ConversationBufferMemory ufficiale
- **Gestione automatica**: Save/load trasparente

#### **3. Scalabilità**
- **Cache efficiente**: ConversationChain riutilizzate
- **File management**: Salvataggio automatico risultati grandi
- **Resource cleanup**: Gestione memoria e file temporanei

### **🔧 Possibili Miglioramenti**

#### **1. Persistenza Database**
**Problema attuale:** Memoria in RAM, persa al riavvio
```python
# Attuale: in-memory
self._conversation_chains: Dict[str, ConversationChain] = {}

# Miglioramento: database persistence
from langchain.memory import SQLChatMessageHistory

memory = ConversationBufferMemory(
    memory_key="history",
    chat_memory=SQLChatMessageHistory(
        session_id=thread_id,
        connection_string="sqlite:///conversations.db"
    )
)
```

#### **2. Memory Strategies Avanzate**
**Problema attuale:** ConversationBufferMemory mantiene tutto
```python
# Attuale: buffer infinito (fino a clear)
memory = ConversationBufferMemory(...)

# Miglioramento: memory con limiti intelligenti
from langchain.memory import ConversationSummaryBufferMemory

memory = ConversationSummaryBufferMemory(
    llm=self.llm,
    max_token_limit=2000,  # Summarize quando supera limite
    return_messages=False
)
```

#### **3. Template Versioning e A/B Testing**
**Problema attuale:** Template fisso
```python
# Miglioramento: template multipli con versioning
class TemplateManager:
    def get_template(self, version: str, user_context: dict) -> PromptTemplate:
        if version == "v2_detailed":
            return self._create_detailed_template()
        elif user_context.get("expertise") == "advanced":
            return self._create_technical_template()
        return self._create_standard_template()
```

#### **4. Monitoring e Metrics**
**Problema attuale:** Log semplici
```python
# Miglioramento: metrics strutturate
import structlog
from prometheus_client import Counter, Histogram

query_counter = Counter('queries_total', ['type', 'thread'])
response_time = Histogram('query_duration_seconds', ['type'])

async def generate_mongodb_query(self, ...):
    with response_time.labels(type='mongodb').time():
        # ... logica esistente
        query_counter.labels(type='mongodb', thread=thread_id).inc()
```

#### **5. Caching Intelligente**
**Problema attuale:** Nessun cache delle risposte
```python
# Miglioramento: cache con TTL per query simili
from cachetools import TTLCache
import hashlib

class CachedConversationalService(ConversationalLangChainService):
    def __init__(self, ...):
        super().__init__(...)
        self._response_cache = TTLCache(maxsize=1000, ttl=3600)

    async def generate_mongodb_query(self, ...):
        cache_key = hashlib.md5(f"{user_input}_{schema}".encode()).hexdigest()
        if cache_key in self._response_cache:
            return self._response_cache[cache_key]

        result = await super().generate_mongodb_query(...)
        self._response_cache[cache_key] = result
        return result
```

#### **6. Schema Evolution Handling**
**Problema attuale:** Schema statico per conversation
```python
# Miglioramento: schema versioning e migration
class SchemaVersionManager:
    def migrate_schema(self, old_schema: dict, new_schema: dict) -> dict:
        # Logica per gestire cambiamenti schema MongoDB
        # Aggiorna template dinamicamente
        pass

    def get_schema_diff(self, v1: dict, v2: dict) -> dict:
        # Identifica cambiamenti che richiedono context update
        pass
```

#### **7. Multi-LLM Support**
**Problema attuale:** Solo Ollama
```python
# Miglioramento: factory pattern per LLM multipli
class LLMFactory:
    @staticmethod
    def create_llm(provider: str, model: str, **kwargs):
        if provider == "ollama":
            return OllamaLLM(model=model, **kwargs)
        elif provider == "openai":
            return OpenAI(model=model, **kwargs)
        elif provider == "anthropic":
            return ChatAnthropic(model=model, **kwargs)
        raise ValueError(f"Unsupported provider: {provider}")
```

#### **8. Error Recovery e Fallback**
**Problema attuale:** Fallback semplice a `{}`
```python
# Miglioramento: recovery strategies
class ErrorRecoveryManager:
    async def handle_llm_failure(self, error: Exception, context: dict):
        if isinstance(error, TimeoutError):
            return await self._try_simpler_model(context)
        elif "context_length" in str(error):
            return await self._summarize_and_retry(context)
        return self._get_default_fallback(context)
```

### **📈 Roadmap Suggerita**

#### **Fase 1 (Quick Wins):**
1. **Logging strutturato** con metrics
2. **Response caching** per query comuni
3. **Memory limits** per evitare memory leaks

#### **Fase 2 (Scalabilità):**
1. **Database persistence** per conversazioni
2. **Multi-LLM support** per resilienza
3. **Template versioning** per miglioramenti iterativi

#### **Fase 3 (Advanced):**
1. **Schema evolution** handling automatico
2. **A/B testing** framework per template
3. **Advanced memory strategies** (summary, vector)

---

## 🎊 Conclusione

Il `ConversationalLangChainService` implementa un sistema elegante che bilancia:

- **Semplicità**: ConversationBufferMemory standard
- **Intelligenza**: Template che decide autonomamente
- **Robustezza**: Error handling e fallback sicuri
- **Scalabilità**: Thread isolation e file management

È una **base solida** per un sistema di analytics conversazionale che può evolversi gradualmente verso funzionalità più avanzate mantenendo la semplicità dell'interfaccia attuale.

**Perfect for production** con possibilità di enhancement incrementali! 🚀