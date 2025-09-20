"""
Custom LLM-based Topic Validator using Ollama via requests (sync)
======================================================
"""

import json
import logging
import requests
from typing import Optional, List, cast, Any, Callable
from guardrails import register_validator, OnFailAction
from guardrails.validator_base import Validator, FailResult, PassResult
from guardrails import Guard
from guards.utils import on_fail_exc, on_fail_filter

logger = logging.getLogger(__name__)


@register_validator("custom/llm_topic", data_type="string")
class LLMTopicValidator(Validator):
    """LLM-based topic validator using Ollama for semantic classification (sync)"""

    def __init__(
        self,
        blocked_topics: Optional[List[str]] = None,
        ollama_url: str = "http://localhost:11434",
        model: str = "gemma3:latest",
        timeout: float = 5.0,
        on_fail: OnFailAction = on_fail_exc
    ):
        super().__init__(on_fail=on_fail)
        self.blocked_topics = blocked_topics or [
            "consigli medici personali",
            "opinioni politiche",
            "consigli finanziari personali", 
            "contenuti inappropriati"
        ]
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._cache = {}  # Simple cache for performance
    
    def _create_system_prompt(self) -> str:
        """Create system prompt for topic classification"""
        blocked_str = ", ".join(self.blocked_topics)
        
        return f"""Sei un classificatore di contenuti. Il tuo compito è determinare se una richiesta utente rientra in topic VIETATI.

TOPIC VIETATI: {blocked_str}

REGOLE:
1. Se la richiesta chiede CONSIGLI PERSONALI su salute, medicina, investimenti, politica → VIETATO
2. Se la richiesta riguarda ANALISI DATI o QUERY DATABASE su qualsiasi argomento → CONSENTITO  
3. Se è conversazione educata generale (saluti, ringraziamenti) → CONSENTITO
4. Se non sei sicuro → CONSENTITO (fail-safe)

ESEMPI:
- "Ho mal di testa, cosa prendo?" → VIETATO (consiglio medico)
- "Analizza i dati sui mal di testa nella popolazione" → CONSENTITO (analisi dati)
- "Per chi votare alle elezioni?" → VIETATO (consiglio politico)  
- "Query sui risultati elettorali del database" → CONSENTITO (query database)
- "Conviene comprare Bitcoin?" → VIETATO (consiglio finanziario)
- "Mostra trend Bitcoin dal database" → CONSENTITO (analisi dati)

Rispondi SOLO con: CONSENTITO oppure VIETATO"""

    def _create_user_prompt(self, user_input: str) -> str:
        """Create user prompt for classification"""
        return f"RICHIESTA UTENTE: \"{user_input}\"\n\nCLASSIFICAZIONE:"

    def _classify_with_llm(self, text: str) -> bool:
        """Classify text using Ollama LLM via requests (sync)"""
        
        # Check cache first
        cache_key = text.lower().strip()[:100]  # Limit key length
        if cache_key in self._cache:
            logger.debug(f"Using cached result for: {text[:50]}...")
            return self._cache[cache_key]
        
        try:
            system_prompt = self._create_system_prompt()
            user_prompt = self._create_user_prompt(text)
            
            payload = {
                "model": self.model,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Deterministic for classification
                    "num_predict": 10,   # Short response
                    "stop": ["\n", ".", ","]  # Stop at first word
                }
            }
            
            logger.debug(f"Making sync LLM request for: {text[:50]}...")
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            llm_output = result.get("response", "").strip().upper()
            
            # Parse LLM response
            is_allowed = "CONSENTITO" in llm_output
            
            # Cache result (limit cache size)
            if len(self._cache) < 100:
                self._cache[cache_key] = is_allowed
            
            logger.info(f"LLM classification for '{text[:50]}...': {llm_output} -> {'ALLOWED' if is_allowed else 'BLOCKED'}")
            return is_allowed
                
        except (requests.Timeout, requests.RequestException) as e:
            logger.warning(f"LLM request failed: {e}")
            return True  # Fail-open: allow if LLM unavailable
        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            return True  # Fail-open
    
    def validate(self, value: str, metadata: dict = None):
        """Validate topic using ONLY LLM classification (sync)"""
        
        logger.debug(f"Starting LLM topic validation for: {value[:50]}...")
        
        try:
            # Use LLM for semantic classification (sync)
            is_allowed = self._classify_with_llm(value)
            
            if not is_allowed:
                blocked_topics_str = ", ".join(self.blocked_topics)
                logger.info(f"Topic blocked by LLM: {value[:50]}...")
                return FailResult(
                    error_message=(
                        f"Sono un sistema AI per analytics di database. Non posso fornire {blocked_topics_str}. "
                        f"Posso aiutarti con query database, analisi dati e programmazione."
                    ),
                    fix_value=""
                )
            
            logger.debug(f"Topic validation passed by LLM: {value[:50]}...")
            return PassResult()
            
        except Exception as e:
            logger.warning(f"Topic validation technical error: {e}")
            # Log the full traceback for debugging
            import traceback
            logger.debug(f"Topic validation traceback: {traceback.format_exc()}")
            return PassResult()  # Fail-open on technical errors



def add_topic_restriction(config: dict) -> Guard:
    """Add topic restriction to guard using LLM-based validator"""
    try:
        logger.info("🔧 Creating LLMTopicValidator...")
        validator = LLMTopicValidator(on_fail=on_fail_exc)
        logger.info(f"🔧 Created validator: {type(validator).__name__}")
        
        guard = Guard().use(validator)
        logger.info(f"🔧 Guard created with {len(guard.validators)} validators")
        logger.info("Using LLM-based topic validator")
        return guard
        
    except Exception as e:
        logger.error(f"LLM topic validator failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Guard()  # Empty guard as fallback
