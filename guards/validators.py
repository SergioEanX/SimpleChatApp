import logging
from guardrails import Guard
from guardrails.hub import ToxicLanguage, ProfanityFree, DetectPII
from guards.utils import on_fail_exc, on_fail_filter

logger = logging.getLogger(__name__)

from guards.utils import OnFailAction
from guardrails import AsyncGuard

def create_input_guard(config: dict) -> AsyncGuard:
    """Create async input validation guard with PII detection and topic restriction"""
    try:
        validators = []
        
        # Add PII detection if enabled
        if config.get("enable_pii_detection", True):
            try:
                # Try Italian PII validator first
                if config.get("use_italian_pii", True):
                    from .italian_pii import ItalianPIIValidator
                    pii_validator = ItalianPIIValidator(on_fail="exception")
                    logger.info("✅ Italian PII detection enabled (fiscal codes, IBAN, etc.)")
                else:
                    # Fallback to default DetectPII (EN only)
                    pii_validator = DetectPII(on_fail="exception")
                    logger.info("✅ PII detection enabled (default entities)")
                
                validators.append(pii_validator)
            except Exception as e:
                logger.warning(f"PII validator failed: {e}")
        
        # Add topic restriction if enabled
        if config.get("enable_topic_restriction", False) and config.get("use_llm_topic", False):
            try:
                from .custom import LLMTopicValidator
                topic_validator = LLMTopicValidator(on_fail="exception")
                validators.append(topic_validator)
                logger.info("✅ LLM Topic restriction enabled")
            except Exception as e:
                logger.warning(f"Topic validator failed: {e}")
        
        # Add toxic language detection
        validators.append(
            ToxicLanguage(threshold=config.get("toxic_threshold", 0.8), on_fail="exception")
        )
        
        # Add profanity filter
        validators.append(
            ProfanityFree(on_fail="filter")
        )
        
        return AsyncGuard().use_many(*validators)
        
    except Exception as e:
        logger.warning(f"Async input guard creation failed: {e}")
        return AsyncGuard().use(ProfanityFree(on_fail="filter"))

def create_output_guard(config: dict) -> Guard:
    """Create output validation guard"""
    try:
        return Guard().use_many(
            ToxicLanguage(threshold=config.get("toxic_threshold", 0.9), on_fail=on_fail_exc),
            ProfanityFree(on_fail=on_fail_filter)
        )
    except Exception as e:
        logger.warning(f"Output guard creation failed: {e}")
        return Guard()