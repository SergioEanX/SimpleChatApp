"""
Custom Italian PII Validator using spaCy
=======================================
"""

import re
import logging
from typing import List, Optional
from guardrails import register_validator
from guardrails.validator_base import Validator, FailResult, PassResult
# Remove ValidationError import - using FailResult instead
# from guardrails.errors import ValidationError

logger = logging.getLogger(__name__)

@register_validator("custom/italian_pii", data_type="string")
class ItalianPIIValidator(Validator):
    """Custom PII validator with Italian support using regex patterns"""
    
    def __init__(self, on_fail: str = "exception"):
        super().__init__(on_fail=on_fail)
        
        # Italian fiscal code pattern
        self.fiscal_code_pattern = re.compile(
            r'\b[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]\b'
        )
        
        # Email pattern
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
        
        # Italian phone pattern
        self.phone_pattern = re.compile(
            r'\b(?:\+39|0039)?[\s\-]?3[0-9]{2}[\s\-]?[0-9]{6,7}\b|'
            r'\b(?:\+39|0039)?[\s\-]?0[0-9]{2,3}[\s\-]?[0-9]{6,8}\b'
        )
        
        # Credit card pattern
        self.credit_card_pattern = re.compile(
            r'\b(?:[0-9]{4}[\s\-]?){3}[0-9]{4}\b'
        )
        
        # IBAN pattern 
        self.iban_pattern = re.compile(
            r'\bIT[0-9]{2}[\s]?[A-Z][0-9]{3}[\s]?[0-9]{4}[\s]?[0-9]{4}[\s]?[0-9]{4}[\s]?[0-9]{3}\b'
        )
    
    def validate(self, value: str, metadata: dict = None):
        """Validate for Italian PII patterns"""
        
        detected_pii = []
        
        # Check fiscal code
        if self.fiscal_code_pattern.search(value):
            detected_pii.append("codice fiscale")
        
        # Check email
        if self.email_pattern.search(value):
            detected_pii.append("email")
        
        # Check phone
        if self.phone_pattern.search(value):
            detected_pii.append("telefono")
        
        # Check credit card
        if self.credit_card_pattern.search(value):
            detected_pii.append("carta di credito")
        
        # Check IBAN
        if self.iban_pattern.search(value):
            detected_pii.append("IBAN")
        
        if detected_pii:
            pii_types = ", ".join(detected_pii)
            return FailResult(
                error_message=(
                    f"Rilevati dati personali sensibili: {pii_types}. "
                    f"Per motivi di sicurezza e privacy, non posso elaborare "
                    f"informazioni personali identificabili."
                ),
                fix_value=""
            )
        
        return PassResult()
