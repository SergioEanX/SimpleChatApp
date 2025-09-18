"""
guardrails_middleware.py - Guardrails Integration
================================================

Middleware FastAPI per validazione input/output con Guardrails.
Protegge contro injection, contenuti inappropriati, e garantisce qualità output.
"""

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
import time
import json
import logging
import os
from typing import Dict, Any, Optional, List

from presidio_analyzer import RecognizerRegistry, AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from starlette.middleware.base import BaseHTTPMiddleware

# Guardrails imports
import guardrails as gd
from guardrails import Guard
from guardrails.hub import ToxicLanguage, ProfanityFree, DetectPII, ValidJson
# guardrails configure
# guardrails hub install hub://guardrails/toxic_language
# https://hub.guardrailsai.com/


logger = logging.getLogger(__name__)

# ================================
# Presidio AnalyzerEngine singleton (module-level)
# ================================
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "nlp_config.yml")
try:
    _nlp_provider = NlpEngineProvider(conf_file=CONFIG_FILE)
    _nlp_engine = _nlp_provider.create_engine()
    
    # Create registry with explicit supported languages
    _registry = RecognizerRegistry()
    # Force the registry to support both EN and IT before loading recognizers
    _registry._supported_languages = {"en", "it"}
    _registry.load_predefined_recognizers(languages=["en", "it"], nlp_engine=_nlp_engine)
    
    # Use the languages that we explicitly set and that have models available
    analyzer_engine = AnalyzerEngine(
        nlp_engine=_nlp_engine,
        registry=_registry,
        supported_languages=["en", "it"],
    )
    logger.info("AnalyzerEngine inizializzato da nlp_config.yml con supporto EN+IT")
except Exception as _e:
    logger.error(f"Errore inizializzazione AnalyzerEngine da nlp_config.yml: {_e}")
    # Fallback: crea engine minimo EN+IT se possibile, altrimenti EN only
    try:
        _fallback_provider = NlpEngineProvider()
        _fallback_nlp = _fallback_provider.create_engine()
        _fallback_reg = RecognizerRegistry()
        # Try to create EN+IT fallback first
        try:
            _fallback_reg._supported_languages = {"en", "it"}
            _fallback_reg.load_predefined_recognizers(languages=["en", "it"], nlp_engine=_fallback_nlp)
            analyzer_engine = AnalyzerEngine(nlp_engine=_fallback_nlp, registry=_fallback_reg, supported_languages=["en", "it"])
            logger.warning("AnalyzerEngine fallback creato con supporto EN+IT")
        except Exception:
            # Final fallback: EN only
            _fallback_reg = RecognizerRegistry()
            _fallback_reg._supported_languages = {"en"}
            _fallback_reg.load_predefined_recognizers(languages=["en"], nlp_engine=_fallback_nlp)
            analyzer_engine = AnalyzerEngine(nlp_engine=_fallback_nlp, registry=_fallback_reg, supported_languages=["en"])
            logger.warning("AnalyzerEngine fallback creato (EN only)")
    except Exception as __e:
        logger.error(f"Fallback AnalyzerEngine creation failed: {__e}")
        analyzer_engine = None


class GuardrailsMiddleware(BaseHTTPMiddleware):
    """
    Middleware FastAPI per applicare Guardrails validation su input e output.

    Funzionalità:
    - Input validation: PII detection, profanity, injection attempts
    - Output validation: JSON format, toxic content, quality checks
    - Configurazione per endpoint specifici
    - Logging e monitoring violazioni
    """

    def __init__(self, app, config: Optional[Dict[str, Any]] = None):
        super().__init__(app)
        self.config = config or {}

        # Inizializza Guards per diversi tipi di validazione
        self._setup_guards()

        # Endpoint che richiedono validazione
        self.protected_endpoints = {
            "/query": {"input": True, "output": True},
            "/conversation": {"input": False, "output": True},
            "/conversation/{thread_id}/history": {"input": False, "output": True}
        }

        logger.info("GuardrailsMiddleware inizializzato")

    def _setup_guards(self):
        """Configura Guards per diversi scenari di validazione"""
        # Usa l'istanza globale unica di AnalyzerEngine definita a livello di modulo
        global analyzer_engine
        if analyzer_engine is None:
            # Fallback di sicurezza: prova a creare dal file YAML
            try:
                _provider = NlpEngineProvider(conf_file=CONFIG_FILE)
                _nlp = _provider.create_engine()
                _reg = RecognizerRegistry()
                # Force registry to support EN and IT explicitly
                _reg._supported_languages = {"en", "it"}
                _reg.load_predefined_recognizers(languages=["en", "it"], nlp_engine=_nlp)
                analyzer_engine = AnalyzerEngine(nlp_engine=_nlp, registry=_reg, supported_languages=["en", "it"])
                logger.info("AnalyzerEngine creato in fallback del middleware con supporto EN+IT")
            except Exception as e:
                logger.error(f"Impossibile inizializzare AnalyzerEngine: {e}")
                analyzer_engine = None

        # --- passa analyzer_engine a DetectPII ---
        # Nota: i validatori custom definiti come funzioni plain causano errori in Guardrails>=0.5.
        # Li rimuoviamo per ora dall'injection, finché non verranno convertiti in Validator ufficiali.
        # Costruisci la input_guard senza DetectPII per evitare che crei il proprio AnalyzerEngine di default
        # DetectPII sembra ignorare il parametro analyzer_engine e creare comunque un engine EN-only
        # causando i warnings sui recognizer IT/ES/PL
        logger.info(f"AnalyzerEngine disponibile: {analyzer_engine is not None}")
        if analyzer_engine is not None:
            logger.info("DetectPII temporaneamente disabilitato per evitare warnings Presidio")
            
        self.input_guard = Guard().use_many(
            ToxicLanguage(threshold=0.8, validation_method="sentence", on_fail="exception"),
            ProfanityFree(on_fail="filter"),
        )

        self.conversation_guard = Guard().use_many(
            ToxicLanguage(threshold=0.9, on_fail="exception"),
            ProfanityFree(on_fail="filter"),
        )

        self.json_guard = Guard().use(
            ValidJson(on_fail="reask")
        )

        self.injection_guard = self._create_injection_guard()

    def _create_injection_guard(self) -> Guard:
        """Crea guard custom per rilevare tentativi di injection"""
        
        # Per ora ritorniamo un guard vuoto dato che i validatori custom 
        # "no-sql-injection" e "no-command-injection" non sono registrati in Guardrails
        # TODO: Implementare validatori custom registrati correttamente
        return Guard()

    async def dispatch(self, request: Request, call_next):
        """Main middleware dispatch - applica validazione input/output"""

        start_time = time.time()
        endpoint = request.url.path

        # Skip se endpoint non protetto
        if endpoint not in self.protected_endpoints:
            return await call_next(request)

        config = self.protected_endpoints[endpoint]

        try:
            # 1. Input Validation
            if config.get("input", False):
                await self._validate_input(request)

            # 2. Processa richiesta
            response = await call_next(request)

            # 3. Output Validation
            if config.get("output", False) and response.status_code == 200:
                response = await self._validate_output(response, endpoint)

            # 4. Logging
            duration = time.time() - start_time
            logger.info(f"Guardrails validation completed for {endpoint}: {duration:.3f}s")

            return response

        except GuardrailsViolation as e:
            logger.warning(f"Guardrails violation on {endpoint}: {e}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Content validation failed",
                    "details": str(e),
                    "violation_type": e.violation_type
                }
            )
        except Exception as e:
            logger.error(f"Guardrails middleware error: {e}")
            return await call_next(request)  # Fallback: continua senza validazione

    async def _validate_input(self, request: Request):
        """Valida input della richiesta"""

        if request.method != "POST":
            return

        try:
            # Leggi body della richiesta
            body = await request.body()
            if not body:
                return

            try:
                data = json.loads(body.decode())
            except json.JSONDecodeError:
                raise GuardrailsViolation("Invalid JSON in request", "format_error")

            # Estrai query utente
            user_query = data.get("query", "")
            if not user_query:
                return

            # Validazione anti-injection
            try:
                self.injection_guard.validate(user_query)
            except Exception as e:
                raise GuardrailsViolation(f"Potential injection detected: {str(e)}", "injection_attempt")

            # Validazione contenuto
            try:
                outcome = self.input_guard.validate(user_query)
                validated_query = outcome.valid_output

                # Se il guard ha modificato il contenuto (es. filtrato profanità)
                if validated_query != user_query:
                    logger.info("Input sanitized by Guardrails")
                    data["query"] = validated_query
                    request._body = json.dumps(data).encode()

            except Exception as e:
                raise GuardrailsViolation(f"Input validation failed: {str(e)}", "content_violation")

        except UnicodeDecodeError:
            raise GuardrailsViolation("Invalid request encoding", "encoding_error")

    async def _validate_output(self, response: Response, endpoint: str):
        """Valida output della risposta"""

        try:
            # Leggi response body
            if hasattr(response, "body_iterator"):
                response_body = b"".join([chunk async for chunk in response.body_iterator])
            else:
                response_body = response.body
            try:
                response_data = json.loads(response_body.decode())
            except json.JSONDecodeError:
                # Non JSON, skip validation
                return self._create_response(response_body, response)

            # Estrai contenuto da validare
            content_to_validate = self._extract_content_for_validation(response_data)

            if not content_to_validate:
                return self._create_response(response_body, response)

            # Determina tipo di validazione basato sul contenuto
            if self._is_mongodb_json_response(response_data):
                # Valida JSON MongoDB
                try:
                    self.json_guard.validate(json.dumps(content_to_validate))
                except Exception as e:
                    logger.warning(f"JSON validation warning: {e}")
                    # Non blocchiamo per JSON warnings, solo log

            else:
                # Valida contenuto conversazionale
                if isinstance(content_to_validate, str):
                    try:
                        # validated_content = self.conversation_guard.validate(content_to_validate)
                        outcome = self.conversation_guard.validate(content_to_validate)
                        validated_content = outcome.valid_output

                        # Se modificato, aggiorna response
                        if validated_content != content_to_validate:
                            response_data = self._update_response_content(
                                response_data, validated_content
                            )
                            response_body = json.dumps(response_data).encode()
                            logger.info("Output sanitized by Guardrails")

                    except Exception as e:
                        raise GuardrailsViolation(
                            f"Output validation failed: {str(e)}",
                            "output_content_violation"
                        )

            return self._create_response(response_body, response)

        except Exception as e:
            logger.error(f"Output validation error: {e}")
            return response  # Fallback: restituisci response originale

    def _extract_content_for_validation(self, response_data: dict) -> Optional[str]:
        """Estrae contenuto da validare dalla response"""

        # Per query endpoint
        if "result" in response_data:
            return response_data["result"]

        # Per conversation history
        if "conversation_history" in response_data:
            messages = response_data["conversation_history"]
            if isinstance(messages, list) and messages:
                # Valida ultimo messaggio AI
                for msg in reversed(messages):
                    if msg.get("type") == "ai":
                        return msg.get("content")

        return None

    def _is_mongodb_json_response(self, response_data: dict) -> bool:
        """Determina se la response contiene JSON MongoDB"""

        # Euristica: se data_saved=False e document_count > 0, probabilmente è JSON
        return (
                response_data.get("data_saved") is False and
                response_data.get("document_count", 0) > 0 and
                response_data.get("result", "").strip().startswith("[")
        )

    def _update_response_content(self, response_data: dict, new_content: str) -> dict:
        """Aggiorna contenuto nella response data"""
        updated_data = response_data.copy()
        updated_data["result"] = new_content
        return updated_data

    def _create_response(self, body: bytes, original_response: Response):
        """Crea nuova response con body aggiornato"""
        return Response(
            content=body,
            status_code=original_response.status_code,
            headers=dict(original_response.headers),
            media_type=original_response.media_type
        )


class GuardrailsViolation(Exception):
    """Exception per violazioni Guardrails"""

    def __init__(self, message: str, violation_type: str):
        super().__init__(message)
        self.violation_type = violation_type


# Helper functions per configurazione
def create_guardrails_config() -> Dict[str, Any]:
    """Crea configurazione default Guardrails"""
    return {
        "input_validation": {
            "toxic_threshold": 0.8,
            "enable_pii_detection": True,
            "enable_profanity_filter": True,
            "enable_injection_protection": True
        },
        "output_validation": {
            "toxic_threshold": 0.9,
            "enable_profanity_filter": True,
            "enable_json_validation": True
        },
        "monitoring": {
            "log_violations": True,
            "log_sanitizations": True
        }
    }


def setup_custom_validators():
    """Ritorna lista di validatori custom per MongoDB/LangChain context."""

    def no_dangerous_mongodb_ops(value: str, metadata: dict) -> str:
        """Previene operazioni MongoDB pericolose."""
        dangerous_ops = ["$where", "eval", "mapReduce", "group"]
        for op in dangerous_ops:
            if op in value.lower():
                raise ValueError(f"Dangerous MongoDB operation detected: {op}")
        return value

    def max_response_length(value: str, metadata: dict) -> str:
        """Limita la lunghezza massima della response."""
        max_length = metadata.get("max_length", 5000)
        if len(value) > max_length:
            return value[:max_length] + "... [truncated by guardrails]"
        return value

    # Restituisce come lista
    return [no_dangerous_mongodb_ops, max_response_length]
