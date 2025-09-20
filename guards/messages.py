def get_violation_message(error_msg: str, config: dict) -> str:
    """Get appropriate violation message based on error"""
    error_lower = error_msg.lower()
    messages = config.get("custom_messages", {})
    
    # Check for specific validator messages (in order of priority)
    if "dati personali sensibili" in error_msg or "informazioni personali identificabili" in error_msg:
        return messages.get("pii", "Ho rilevato dati personali sensibili nella tua richiesta (nomi, email, codici fiscali, ecc.). Per motivi di sicurezza e privacy, non posso elaborare informazioni personali identificabili.")
    elif "sistema ai per analytics" in error_lower or "non posso fornire" in error_lower:
        return messages.get("topic", "Sono un sistema AI per database analytics. Non posso fornire consigli personali.")
    elif "toxic" in error_lower:
        return messages.get("toxic", "Non posso elaborare contenuti inappropriati. Ti prego di riformulare.")
    elif "profanity" in error_lower:
        return messages.get("profanity", "Linguaggio inappropriato rimosso dalla richiesta.")
    else:
        return "Validazione fallita. Riprova con contenuto diverso."

def create_response_body(message: str, violation_type: str = "content_violation") -> dict:
    """Create standardized error response"""
    return {
        "error": "Content validation failed",
        "message": message,
        "violation_type": violation_type
    }