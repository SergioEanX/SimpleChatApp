def get_violation_message(error_msg: str, config: dict) -> str:
    """Get appropriate violation message based on error"""
    error_lower = error_msg.lower()
    messages = config.get("custom_messages", {})
    
    # Check for PII violations first (more specific)
    if "pii" in error_lower or "personal" in error_lower or "detected" in error_lower:
        return messages.get("pii", "Dati personali rilevati.")
    elif "toxic" in error_lower:
        return messages.get("toxic", "Contenuto inappropriato rilevato.")
    elif "profanity" in error_lower:
        return messages.get("profanity", "Linguaggio inappropriato filtrato.")
    elif "topic" in error_lower:
        return messages.get("topic", "Topic non consentito.")
    else:
        return "Validazione fallita. Riprova con contenuto diverso."

def create_response_body(message: str, violation_type: str = "content_violation") -> dict:
    """Create standardized error response"""
    return {
        "error": "Content validation failed",
        "message": message,
        "violation_type": violation_type
    }