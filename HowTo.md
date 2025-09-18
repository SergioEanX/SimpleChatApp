# MongoDB Analytics API con Guardrails - HowTo

## 🚀 Panoramica Applicazione

**MongoDB Analytics API con Guardrails v2.2.0** è un'API FastAPI avanzata che combina:

- **MongoDB Analytics**: Query intelligenti con supporto conversazionale
- **LangChain + Ollama**: Memoria conversazionale (ConversationBufferMemory) 
- **Guardrails AI**: Protezione input/output con validazione contenuti
- **Presidio**: Rilevamento e protezione PII multilingua (EN/IT)
- **Architettura Modulare**: Routes separate, middleware personalizzato, configurazione YAML

### 🛡️ Funzionalità di Sicurezza

- **Rilevamento PII**: Protegge dati personali (nomi, email, indirizzi, codici fiscali, ecc.)
- **Filtro Tossicità**: Blocca contenuti tossici e inappropriati
- **Filtro Profanità**: Rimuove o blocca linguaggio volgare
- **Protezione Injection**: Previene SQL/NoSQL injection attacks
- **Validazione JSON**: Garantisce formato corretto delle risposte
- **Validazione Output**: Controlla qualità e sicurezza delle risposte generate

---

## 📦 Installazione e Setup

### 1. Dipendenze di Sistema

```bash
# Installa Python 3.11+ e UV package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clona e setup progetto
cd SimpleChatApp
uv sync
```

### 2. Modelli spaCy per Presidio

```bash
# Attiva l'ambiente virtuale
source .venv/bin/activate  # Linux/Mac
# oppure .venv\Scripts\activate  # Windows

# Installa/aggiorna spaCy
uv pip install -U spacy

# Scarica modelli multilingua
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg

# Verifica compatibilità
python -m spacy validate
```

> **⚠️ Importante**: Se `spacy validate` segnala mismatch, aggiorna i modelli o fixa la versione di spaCy:
> ```bash
> pip install "spacy==3.7.*"  # Se necessario per compatibilità modelli
> ```

### 3. Configurazione MongoDB

Modifica le variabili in `main.py` o crea file `.env`:

```bash
# File .env (opzionale)
MONGO_URI="mongodb://username:password@localhost:27017/database_name"
LLM_NAME="llama3:latest"
```

### 4. Setup Ollama (LLM)

```bash
# Installa Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Scarica modello (esempio)
ollama pull llama3:latest
# oppure
ollama pull gemma2:9b

# Verifica servizio
ollama serve  # Default: http://localhost:11434
```

### 5. Avvio Applicazione

```bash
# Avvio normale
python main.py

# Avvio con uvicorn (più opzioni)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Verifica salute servizi
curl http://localhost:8000/health | jq
```

---

## 📋 Endpoints Completi

### 🔐 Endpoints Protetti da Guardrails

#### **POST /query** - Query Conversazionale Intelligente
Esegue query MongoDB usando ConversationBufferMemory per mantenere il contesto.

**🛡️ Protezioni Attive**:
- **Input**: PII detection, toxicity filter, profanity filter, injection protection
- **Output**: Content validation, JSON validation, toxicity filter

**Request:**
```json
{
  "query": "string",
  "session_id": "string (opzionale)",
  "collection": "string (opzionale)"
}
```

**Response:**
```json
{
  "session_id": "thread_abc123",
  "result": "string o JSON data",
  "data_saved": false,
  "file_path": null,
  "document_count": 0,
  "created_at": "2024-01-01T12:00:00"
}
```

#### **GET /conversation/{thread_id}/history** - Storia Conversazione
Recupera la cronologia completa di una conversazione.

**🛡️ Protezioni Attive**:
- **Output**: Content validation, toxicity filter

**Response:**
```json
{
  "thread_id": "thread_abc123",
  "total_messages": 10,
  "conversation_history": [
    {
      "type": "human",
      "content": "Messaggio utente...",
      "full_length": 150
    },
    {
      "type": "ai", 
      "content": "Risposta AI...",
      "full_length": 300
    }
  ],
  "memory_type": "ConversationBufferMemory",
  "guardrails_protected": true
}
```

### 📊 Endpoints Sistema

#### **GET /conversations** - Lista Thread Attivi
```json
{
  "active_threads": ["thread_abc123", "thread_def456"],
  "total_count": 2,
  "memory_approach": "ConversationBufferMemory",
  "guardrails_protection": "input/output validation active"
}
```

#### **DELETE /conversation/{thread_id}** - Cancella Memoria
```json
{
  "thread_id": "thread_abc123",
  "memory_cleared": true,
  "status": "success",
  "message": "ConversationBufferMemory pulita"
}
```

#### **GET /health** - Status Completo Sistema
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00",
  "services": {
    "mongodb": "✅ Healthy",
    "ollama_llm": "✅ Healthy", 
    "guardrails": "✅ Active"
  },
  "memory": {
    "type": "ConversationBufferMemory",
    "active_conversations": 2,
    "threads": ["thread_abc123", "thread_def456"]
  },
  "protection": {
    "guardrails_middleware": true,
    "input_validation": ["PII_detection", "toxicity_filter", "injection_protection"],
    "output_validation": ["content_filter", "JSON_validation", "toxicity_filter"]
  },
  "config": {
    "ollama_model": "llama3:latest",
    "database": "your_database", 
    "default_collection": "your_collection"
  }
}
```

#### **GET /guardrails/status** - Status Protezioni
```json
{
  "guardrails_active": true,
  "protected_endpoints": ["/query", "/conversation/{thread_id}/history"],
  "input_validators": ["ToxicLanguage", "ProfanityFree", "DetectPII"],
  "output_validators": ["ToxicLanguage", "ProfanityFree", "NoInvalidJSON"],
  "config": {
    "input_validation": {
      "toxic_threshold": 0.8,
      "enable_pii_detection": true,
      "enable_profanity_filter": true,
      "enable_injection_protection": true
    },
    "output_validation": {
      "toxic_threshold": 0.9,
      "enable_profanity_filter": true,
      "enable_json_validation": true
    }
  }
}
```

#### **GET /** - Root API Info
```json
{
  "name": "MongoDB Analytics API con Guardrails",
  "version": "2.2.0",
  "memory_approach": "ConversationBufferMemory",
  "protection": "Guardrails Input/Output Validation",
  "description": "API per analytics MongoDB con memoria conversazionale protetta",
  "endpoints": {
    "query": "POST /query - Esegui query conversazionale [PROTETTO]",
    "history": "GET /conversation/{thread_id}/history - Storia thread [PROTETTO]",
    "conversations": "GET /conversations - Lista thread attivi",
    "clear": "DELETE /conversation/{thread_id} - Pulisci memoria", 
    "health": "GET /health - Status servizi + Guardrails",
    "guardrails": "GET /guardrails/status - Stato protezioni",
    "docs": "GET /docs - Documentazione OpenAPI"
  },
  "security_features": [
    "PII Detection & Blocking",
    "Toxic Content Filtering", 
    "SQL/NoSQL Injection Protection",
    "Profanity Filtering",
    "Output Content Validation",
    "JSON Format Validation"
  ]
}
```

#### **GET /docs** - Documentazione OpenAPI
Interfaccia Swagger UI per testare tutti gli endpoints interattivamente.

---

## 🧪 Test delle Protezioni Guardrails

### 1. Test Rilevamento PII (Presidio)

#### 🇮🇹 Test PII Italiano
```bash
# Codice fiscale italiano - DOVREBBE essere bloccato/rimosso
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Il mio codice fiscale è RSSMRA85M01H501Z, puoi elaborare questa informazione?"
  }'

# Email e telefono - DOVREBBE essere bloccato/rimosso  
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Contattami su mario.rossi@email.com oppure al numero 339-1234567"
  }'

# Nome e indirizzo - DOVREBBE essere bloccato/rimosso
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Mario Rossi abita in Via Roma 123, Milano MI 20121"
  }'
```

#### 🇺🇸 Test PII Inglese  
```bash
# SSN americano - DOVREBBE essere bloccato/rimosso
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "My SSN is 123-45-6789, can you help me with my account?"
  }'

# Credit card - DOVREBBE essere bloccato/rimosso
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "My credit card number is 4532-1234-5678-9012, expiry 12/25"
  }'
```

### 2. Test Filtro Tossicità

```bash
# Contenuto tossico/offensivo - DOVREBBE essere bloccato
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "I hate this stupid system and everyone who uses it"
  }'

# Linguaggio aggressivo - DOVREBBE essere bloccato
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "You are all idiots and this API is garbage"
  }'
```

### 3. Test Filtro Profanità

```bash
# Linguaggio volgare - DOVREBBE essere filtrato
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "This damn API is not working properly, what the hell is going on?"
  }'

# Profanità multilingua
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Questa merda di API non funziona per niente bene"
  }'
```

### 4. Test Protezione Injection

```bash
# MongoDB injection attempt - DOVREBBE essere bloccato
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Find users where $where: function() { return true; }"
  }'

# Command injection attempt - DOVREBBE essere bloccato
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me data; drop collection users; --"
  }'

# JavaScript injection in MongoDB context - DOVREBBE essere bloccato
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Find documents with eval(malicious_code)"
  }'
```

### 5. Test Query Legittime (DOVREBBERO passare)

```bash
# Query normale - DOVREBBE passare
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me the latest 10 documents in the collection"
  }'

# Conversazione normale - DOVREBBE passare
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the total count of documents created this month?",
    "session_id": "test_session_123"
  }'

# Query analitica - DOVREBBE passare
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Group documents by category and show the count for each"
  }'
```

### 6. Verifica Risposte di Violazione

Quando Guardrails rileva una violazione, la risposta sarà simile a:

```json
{
  "error": "Content validation failed",
  "details": "Input validation failed: ToxicLanguage validation failed",
  "violation_type": "content_violation"
}
```

Tipi di violazione possibili:
- `format_error`: JSON malformato
- `injection_attempt`: Tentativo di injection rilevato
- `content_violation`: Contenuto tossico/inappropriato
- `output_content_violation`: Output non conforme ai standard
- `encoding_error`: Encoding della richiesta non valido

---

## ⚙️ Configurazione Avanzata

### Presidio NLP (nlp_config.yml)
```yaml
nlp_engine_name: spacy
models:
  - lang_code: en
    model_name: en_core_web_lg
  - lang_code: it
    model_name: it_core_news_lg

model_to_presidio_entity_mapping:
  PERSON: PERSON
  ORG: ORGANIZATION
  GPE: LOCATION
  LOC: LOCATION
  DATE: DATE_TIME
  EMAIL: EMAIL_ADDRESS

low_score_entity_names: []
labels_to_ignore: []
ner_model_configuration: {}
```

### Guardrails Thresholds
Modificabili in `guardrails_middleware.py`:

```python
# Input validation thresholds
ToxicLanguage(threshold=0.8, validation_method="sentence", on_fail="exception")
ProfanityFree(on_fail="filter")

# Output validation thresholds  
ToxicLanguage(threshold=0.9, on_fail="exception")
ValidJson(on_fail="reask")
```

### Endpoints Protetti
Configurazione endpoint protetti:
```python
protected_endpoints = {
    "/query": {"input": True, "output": True},
    "/conversation": {"input": False, "output": True},
    "/conversation/{thread_id}/history": {"input": False, "output": True}
}
```

---

## 🐛 Troubleshooting

### Errori Comuni

#### 1. Presidio: "Misconfigured engine, supported languages have to be consistent"
```bash
# Verifica modelli spaCy installati
python -c "import spacy; print(spacy.util.is_package('en_core_web_lg'), spacy.util.is_package('it_core_news_lg'))"

# Reinstalla modelli se necessario
python -m spacy download en_core_web_lg --force
python -m spacy download it_core_news_lg --force
```

#### 2. Ollama Connection Error
```bash
# Verifica Ollama sia in esecuzione
curl http://localhost:11434/api/tags

# Riavvia Ollama se necessario
ollama serve
```

#### 3. MongoDB Connection Issues
```bash
# Test connessione MongoDB
mongosh "mongodb://username:password@localhost:27017/database_name"
```

#### 4. Guardrails Validation Errors
- Controlla i log dell'applicazione per dettagli specifici
- Verifica che i contenuti rispettino le policy di sicurezza
- Testa con contenuti "puliti" per isolare il problema

### Log Debugging

I log dell'applicazione mostrano:
```
INFO:guardrails_middleware:AnalyzerEngine inizializzato da nlp_config.yml con supporto ['en', 'it']
INFO:guardrails_middleware:GuardrailsMiddleware inizializzato
INFO:guardrails_middleware:Guardrails validation completed for /query: 0.245s
```

---

## 📚 Risorse Aggiuntive

### Documentazione Tecnica
- **FastAPI Docs**: http://localhost:8000/docs
- **Guardrails AI Hub**: https://hub.guardrailsai.com/
- **Presidio Documentation**: https://microsoft.github.io/presidio/
- **LangChain Memory**: https://python.langchain.com/docs/modules/memory/

### Architettura del Codice
- `main.py`: App FastAPI principale e configurazione
- `routes.py`: Definizione endpoint separata
- `guardrails_middleware.py`: Middleware sicurezza e validazione
- `database.py`: Servizio MongoDB
- `langchain_service.py`: Servizio conversazionale
- `models.py`: Modelli Pydantic request/response
- `nlp_config.yml`: Configurazione Presidio multilingua

### Performance & Monitoring
- Health check: `GET /health`
- Guardrails status: `GET /guardrails/status` 
- Conversation memory: Gestione automatica thread con ConversationBufferMemory
- Risultati grandi: Auto-salvataggio file in `temp_results/`

---

**🔐 Sicurezza First**: L'API è progettata con protezioni multiple a livelli per garantire sicurezza e qualità dei contenuti in ogni interazione.