"""
Custom Topic Validator - Direct Guardrails Integration
=====================================================
"""

import logging
from guardrails import Guard
from guardrails.validator_base import Validator
from guardrails.errors import ValidationError

logger = logging.getLogger(__name__)

class DirectTopicValidator(Validator):
    """Direct topic validator without @register_validator decorator"""
    
    def __init__(self, on_fail="exception", **kwargs):
        # Initialize parent without using register_validator
        super().__init__(on_fail=on_fail, **kwargs)
        self.rail_alias = "custom_topic"  # Set rail_alias directly
    
    def validate(self, value, metadata=None):
        """Direct validation method"""
        logger.info(f"🔥 DirectTopicValidator.validate() called with value type: {type(value)}")
        logger.info(f"🔥 DirectTopicValidator.validate() value: '{str(value)[:100]}...'")
        
        if not isinstance(value, str):
            logger.warning(f"⚠️ DirectTopicValidator received non-string: {type(value)}")
            return value
            
        text_lower = value.lower()
        
        # Medical advice patterns
        medical_patterns = [
            "suggerisci", "consigli per", "rimedio", "cura per",
            "mal di", "cosa prendo", "farmaco", "medicina"
        ]
        
        # Check for medical advice
        for pattern in medical_patterns:
            if pattern in text_lower:
                # Skip if it's data analysis
                if any(word in text_lower for word in ["analisi", "dati", "database", "query"]):
                    continue
                    
                logger.info(f"🚫 Topic restriction triggered: medical advice detected")
                raise ValidationError(
                    "Sono un sistema AI per database analytics. "
                    "Non posso fornire consigli medici personali. "
                    "Posso aiutarti con query database e analisi dati."
                )
        
        logger.debug(f"✅ Topic validation passed for: {value[:50]}...")
        return value
    
    def to_dict(self):
        """Required by Guardrails interface"""
        return {
            "validator_name": "custom_topic",
            "on_fail": self.on_fail
        }


def create_topic_guard() -> Guard:
    """Create guard with direct topic validator"""
    try:
        logger.info("🔨 Creating DirectTopicValidator...")
        validator = DirectTopicValidator(on_fail="exception")
        logger.info(f"🔨 DirectTopicValidator created: {type(validator).__name__}")
        logger.info(f"🔨 Validator rail_alias: {getattr(validator, 'rail_alias', 'no_alias')}")
        logger.info(f"🔨 Validator on_fail: {getattr(validator, 'on_fail', 'unknown')}")
        
        guard = Guard().use(validator)
        logger.info(f"🔨 Guard created with {len(guard.validators)} validators")
        logger.info("✅ Direct topic validator created successfully")
        return guard
    except Exception as e:
        logger.error(f"❌ Direct topic validator failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Guard()  # Empty guard fallback
