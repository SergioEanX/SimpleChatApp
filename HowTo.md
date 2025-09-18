# MongoDB Analytics API - Guida Utilizzo

API per analytics MongoDB con memoria conversazionale intelligente.

## 🚀 Avvio Rapido

```bash
# 1. Installa dipendenze



# Modelli spacy
uv pip install -U spacy
spacy validate
spacy download en_core_web_lg
spacy download it_core_news_lg

# Suggerimento: se spacy validate segnala mismatch, o aggiorna i modelli 
# (comando di download) o blocca la versione di spaCy al ramo per cui i modelli 
# sono stati addestrati (ad esempio pip install "spacy==3.7.*"). 
# L’importante è che versione di spaCy e modelli coincidano.

# 2. Configura MongoDB URI in main.py
MONGODB_URI = "mongodb://username:password@localhost:27017/database_name"

# 3. Avvia API
uvicorn main:app --reload

# 4. Verifica stato
curl "http://localhost:8000/health" | jq
```

---

## 📋 Endpoints Disponibili

### **🔍 Query Intelligente**
**POST** `/query` - Esegue query MongoDB o risponde conversazionalmente

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
  "result": "string o JSON",
  "data_saved": false,
  "file_path": null,
  "document_count": 0,
  "created_at": "2024-01-01T12:00:00"
}
```

### **💭 Gestione Conversazioni**
- **GET** `/conversation/{thread_id}/history` - Storia conversazione
- **GET** `/conversations` - Lista thread attivi
- **DELETE** `/conversation/{thread_id}` - Cancella conversazione

### **🩺 Sistema**
- **GET** `/health` - Stato servizi
- **GET** `/` - Info API e endpoints

---

## 🧪 Esempi di Test

### **1. Domanda Generale**
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "cosa è RAG?"}' | jq
```

**Risultato:** Spiegazione testuale di RAG

### **2. Query MongoDB**
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "mostra tutti i documenti"}' | jq
```

**Risultato:** Esecuzione query `{}` su MongoDB

### **3. Conversazione con Memoria**

**Passo 1** - Prima query:
```bash
RESPONSE=$(curl -s -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "ciao, mi chiamo Marco e sono un developer"}')

THREAD_ID=$(echo $RESPONSE | jq -r '.session_id')
echo "Thread ID: $THREAD_ID"
```

**Passo 2** - Query che usa memoria:
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"come mi chiamo e che lavoro faccio?\", \"session_id\": \"$THREAD_ID\"}" | jq -r '.result'
```

**Risultato:** "Ti chiami Marco e sei un developer" (usa memoria!)

### **4. Mix MongoDB + Conversazione**
```bash
THREAD_ID="thread_test_123"

# Query dati
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "utenti con età > 25", "session_id": "'$THREAD_ID'"}' | jq

# Domanda generale nello stesso thread  
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "spiegami MongoDB", "session_id": "'$THREAD_ID'"}' | jq

# Query che usa contesto precedente
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "ordina per data decrescente", "session_id": "'$THREAD_ID'"}' | jq
```

---

## 📊 Gestione Thread e Memoria

### **Lista Thread Attivi**
```bash
curl "http://localhost:8000/conversations" | jq
```

**Response:**
```json
{
  "active_threads": ["thread_abc123", "thread_def456"],
  "total_count": 2,
  "memory_approach": "ConversationBufferMemory"
}
```

### **Storia Conversazione Specifica**
```bash
curl "http://localhost:8000/conversation/thread_abc123/history" | jq
```

**Response:**
```json
{
  "thread_id": "thread_abc123",
  "total_messages": 4,
  "conversation_history": [
    {
      "type": "human",
      "content": "ciao, mi chiamo Marco",
      "full_length": 20
    },
    {
      "type": "ai", 
      "content": "Ciao Marco! Come posso aiutarti?",
      "full_length": 32
    }
  ]
}
```

### **Cancellare Conversazione**
```bash
curl -X DELETE "http://localhost:8000/conversation/thread_abc123" | jq
```

---

## 🎯 Template Intelligente

L'API decide automaticamente come rispondere:

### **🗄️ Richieste Dati → JSON MongoDB**
- "mostra tutti i documenti" → `{}`
- "utenti con età > 30" → `{"età": {"$gt": 30}}`
- "ordina per data" → `{"$sort": {"data": -1}}`
- "primi 10 risultati" → `{"$limit": 10}`

### **💬 Domande Generali → Risposta Testuale**
- "cosa è RAG?" → Spiegazione Retrieval-Augmented Generation
- "come funziona MongoDB?" → Spiegazione database NoSQL
- "differenza tra SQL e NoSQL?" → Confronto dettagliato

---

## 🔧 Troubleshooting

### **Verifica Stato Sistema**
```bash
curl "http://localhost:8000/health" | jq
```

**Stato Sano:**
```json
{
  "status": "healthy",
  "services": {
    "mongodb": "✅ Healthy",
    "ollama_llm": "✅ Healthy"  
  },
  "memory": {
    "active_conversations": 3,
    "threads": ["thread_1", "thread_2", "thread_3"]
  }
}
```

### **Problemi Comuni**

**1. MongoDB non connesso:**
```json
{"status": "degraded", "services": {"mongodb": "❌ Issues"}}
```
→ Verifica URI e credenziali in `main.py`

**2. Ollama non disponibile:**
```json
{"status": "degraded", "services": {"ollama_llm": "❌ Issues"}}
```
→ Avvia Ollama: `ollama serve`  
→ Scarica modello: `ollama pull gemma2:latest`

**3. Risposta troncata:**
→ Il modello ha limiti di token, configurabili in `langchain_service.py`

---

## 📚 Script di Test Completo

```bash
#!/bin/bash
echo "🧪 Test Completo MongoDB Analytics API"

# Test Health
echo "1. Health Check..."
curl -s "http://localhost:8000/health" | jq -r '.status'

# Test Conversazione Generale
echo "2. Test Domanda Generale..."
curl -s -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "cosa è machine learning?"}' | jq -r '.result' | head -1

# Test MongoDB Query  
echo "3. Test Query MongoDB..."
curl -s -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "mostra documenti"}' | jq -r '.document_count'

# Test Memoria
echo "4. Test Memoria Conversazionale..."
RESP=$(curl -s -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "mi chiamo Alice"}')
THREAD=$(echo $RESP | jq -r '.session_id')

curl -s -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"come mi chiamo?\", \"session_id\": \"$THREAD\"}" | jq -r '.result'

# Lista Thread
echo "5. Thread Attivi:"
curl -s "http://localhost:8000/conversations" | jq -r '.active_threads[]'

echo "✅ Test completati!"
```

---

## 🎉 Caratteristiche

- ✅ **Template Intelligente**: Decide automaticamente MongoDB vs conversazione
- ✅ **Memoria Thread-based**: Ogni conversazione isolata
- ✅ **ConversationBufferMemory**: Standard LangChain
- ✅ **File Parquet**: Salvataggio automatico risultati grandi
- ✅ **Health Monitoring**: Stato sistema e thread attivi
- ✅ **Error Handling**: Gestione robusta errori

**API pronta per produzione con memoria conversazionale intelligente!** 🚀