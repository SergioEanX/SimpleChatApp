"""
Custom LLM-based Topic Validator using Ollama via httpx
======================================================
"""

import asyncio
import json
import logging
import httpx
from typing import Optional, List
from guardrails import register_validator
from guardrails.validator_base import Validator
from guardrails.errors import ValidationError
from guardrails import Guard

logger = logging.getLogger(__name__)

@register_validator("custom/llm_topic", data_type="string")
class LLMTopicValidator(Validator):
    """LLM-based topic validator using Ollama for semantic classification"""
    
    def __init__(
        self,
        blocked_topics: Optional[List[str]] = None,
        ollama_url: str = "http://localhost:11434",
        model: str = "gemma3:latest",
        timeout: float = 5.0,
        on_fail: str = "exception"
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

    async def _classify_with_llm(self, text: str) -> bool:
        """Classify text using Ollama LLM via httpx"""
        
        # Check cache first
        cache_key = text.lower().strip()[:100]  # Limit key length
        if cache_key in self._cache:
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
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                
                result = response.json()
                llm_output = result.get("response", "").strip().upper()
                
                # Parse LLM response
                is_allowed = "CONSENTITO" in llm_output
                
                # Cache result (limit cache size)
                if len(self._cache) < 100:
                    self._cache[cache_key] = is_allowed
                
                logger.debug(f"LLM classification for '{text[:50]}...': {llm_output} -> {'ALLOWED' if is_allowed else 'BLOCKED'}")
                return is_allowed
                
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning(f"LLM request failed: {e}")
            return True  # Fail-open: allow if LLM unavailable
        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            return True  # Fail-open
    
    def validate(self, value: str, metadata: dict = None) -> str:
        """Validate topic using LLM classification"""
        
        # Quick keyword-based pre-filtering for obvious cases
        obvious_blocked = self._quick_keyword_check(value)
        if obvious_blocked:
            raise ValidationError(f"Topic vietato rilevato: {obvious_blocked}")
        
        # Use LLM for semantic classification
        try:
            # Simplified async handling - use asyncio.run directly
            is_allowed = asyncio.run(self._classify_with_llm(value))
            
            if not is_allowed:
                blocked_topics_str = ", ".join(self.blocked_topics)
                raise ValidationError(
                    f"Sono un sistema AI per analytics di database. Non posso fornire {blocked_topics_str}. "
                    f"Posso aiutarti con query database, analisi dati e programmazione."
                )
            
            return value
            
        except ValidationError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.warning(f"Topic validation technical error: {e}")
            # Log the full traceback for debugging
            import traceback
            logger.debug(f"Topic validation traceback: {traceback.format_exc()}")
            return value  # Fail-open on technical errors
    
    def _quick_keyword_check(self, text: str) -> Optional[str]:
        """Quick keyword-based check for obvious violations"""
        text_lower = text.lower()
        
        # Medical advice patterns
        medical_patterns = [
            ("mal di", "consigli medici"),
            ("cosa prendo", "consigli medici"), 
            ("farmaco per", "consigli medici"),
            ("devo prendere", "consigli medici"),
            ("cosa consigli per", "consigli medici"),  # Added this
            ("mi consigli per", "consigli medici"),   # Added this
            ("rimedio per", "consigli medici"),       # Added this
            ("cura per", "consigli medici"),          # Added this
            ("suggerisci", "consigli medici")         # Added this
        ]
        
        # Political opinion patterns  
        political_patterns = [
            ("cosa pensi di meloni", "opinioni politiche"),
            ("cosa pensi di salvini", "opinioni politiche"),
            ("per chi votare", "opinioni politiche"),
            ("meglio il governo", "opinioni politiche")
        ]
        
        # Financial advice patterns
        financial_patterns = [
            ("conviene comprare", "consigli finanziari"),
            ("devo investire", "consigli finanziari"),
            ("migliore investimento", "consigli finanziari")
        ]
        
        all_patterns = medical_patterns + political_patterns + financial_patterns
        
        for pattern, category in all_patterns:
            if pattern in text_lower:
                # Check if it's analysis context
                if any(analysis_word in text_lower for analysis_word in ["analisi", "dati", "database", "query", "report"]):
                    continue  # It's data analysis, not personal advice
                return category
                
        return None


def add_topic_restriction(config: dict) -> Guard:
    """Add topic restriction to guard - ultra simple version"""
    try:
        # Use ultra simple validator following exact docs pattern
        from .ultra_simple import UltraSimpleTopicValidator
        
        logger.info("🔧 Creating UltraSimpleTopicValidator...")
        validator = UltraSimpleTopicValidator(on_fail="exception")
        logger.info(f"🔧 Created validator: {type(validator).__name__}")
        
        guard = Guard().use(validator)
        logger.info(f"🔧 Guard created with {len(guard.validators)} validators")
        logger.info("Using ultra simple topic validator (exact docs pattern)")
        return guard
        
    except Exception as e:
        logger.error(f"Ultra simple topic validator failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Guard()  # Empty guard as fallback
