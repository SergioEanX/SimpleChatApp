from typing import Dict, List, Any

# Default guardrails configuration
DEFAULT_CONFIG = {
    "toxic_threshold": 0.8,
    "profanity_filter": True,
    "enable_topic_restriction": True,  # Set True to enable LLM topic filtering
    "use_llm_topic": True,            # Set True to use LLM-based topic validator
    "enable_pii_detection": True,     # Set True to enable PII detection
    "use_italian_pii": True,          # Use custom Italian PII validator
    
    # Ollama LLM configuration for topic classification
    "ollama_url": "http://localhost:11434",
    "ollama_model": "gemma2:2b",  # Fast model for classification
    "llm_timeout": 5.0,
    
    "custom_messages": {
        "toxic": "Non posso elaborare contenuti inappropriati. Ti prego di riformulare.",
        "profanity": "Linguaggio inappropriato rimosso dalla richiesta.",
        "topic": "Sono un sistema AI per database analytics. Non posso fornire consigli personali.",
        "pii": "Ho rilevato dati personali sensibili nella tua richiesta (nomi, email, codici fiscali, ecc.). Per motivi di sicurezza e privacy, non posso elaborare informazioni personali identificabili."
    }
}

# Protected endpoints configuration
PROTECTED_ENDPOINTS = {
    "/query": {"input": True, "output": True},
    "/conversation": {"input": False, "output": True},
    "/conversation/{thread_id}/history": {"input": False, "output": True}
}

def load_config() -> Dict[str, Any]:
    """Load configuration from file or return defaults"""
    # try:
    #     # TODO: Load from guardrails_config.yml if needed
    #     return DEFAULT_CONFIG.copy()
    # except Exception:
    return DEFAULT_CONFIG.copy()