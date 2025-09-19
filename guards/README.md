"""
Guards System - LLM-based Topic Classification
=============================================

## 🚀 QUICK START

In your main.py:

```python
# Replace old guardrails import:
from guards import GuardrailsMiddleware
app.add_middleware(GuardrailsMiddleware)
```

## ✨ FEATURES

✅ **ToxicLanguage detection** - Blocks inappropriate content
✅ **Profanity filtering** - Sanitizes bad language  
✅ **LLM-based topic restriction** - Semantic understanding via Ollama
✅ **Async/Stream handling** - Proper FastAPI middleware
✅ **Auto-configuration** - Works out of the box
✅ **Custom messages** - User-friendly error responses

## 🤖 LLM TOPIC CLASSIFICATION

The system uses your local Ollama instance for intelligent topic classification:

**BLOCKED TOPICS:**
- Personal medical advice ("Ho mal di testa, cosa prendo?")
- Political opinions ("Cosa pensi di Meloni?") 
- Financial advice ("Conviene comprare Bitcoin?")
- Inappropriate content

**ALLOWED TOPICS:**
- Database queries ("Trova utenti nel database")
- Data analysis ("Analizza trend vendite")
- Programming help ("Come fare query MongoDB?")
- General conversation ("Ciao, come stai?")

## ⚙️ CONFIGURATION

Edit `guards/config.py`:

```python
DEFAULT_CONFIG = {
    "enable_topic_restriction": True,  # Enable LLM classification
    "ollama_url": "http://localhost:11434",
    "ollama_model": "gemma2:2b",  # Fast model for classification
    "llm_timeout": 5.0,
}
```

## 🧪 TESTING

```bash
# Should be BLOCKED (medical advice):
curl -X POST "http://localhost:8000/query" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "Ho mal di testa, cosa dovrei prendere?"}'

# Should be ALLOWED (data analysis):
curl -X POST "http://localhost:8000/query" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "Analizza i dati sui mal di testa nel database"}'
```

## 📁 FILE STRUCTURE

```
guards/
├── __init__.py      # Main export
├── middleware.py    # Core middleware (150 lines)
├── config.py        # Configuration 
├── validators.py    # Basic guardrails
├── custom.py        # LLM topic validator (100 lines)
├── messages.py      # Custom error messages
├── utils.py         # Helper functions
└── README.md        # This file
```

## 🔧 DEPENDENCIES

Required: `httpx>=0.27.0` for fast Ollama API calls

## 🎯 PERFORMANCE

- **LLM calls**: ~200-500ms for classification
- **Cache hits**: ~1ms (repeated queries)
- **Fail-safe**: Allows requests if LLM unavailable
- **Quick patterns**: Fast keyword pre-filtering

## 💡 CUSTOMIZATION

Add new blocked topics in `custom.py`:

```python
self.blocked_topics = [
    "consigli medici personali",
    "opinioni politiche", 
    "consigli finanziari personali",
    "your_custom_topic"  # Add here
]
```

The system combines keyword-based fast filtering with LLM semantic understanding for the best balance of speed and accuracy.
"""