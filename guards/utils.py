from typing import Optional, Dict, Any

def extract_query_from_request(data: dict) -> Optional[str]:
    """Extract user query from request data"""
    return data.get("query", "") if data else None

def extract_content_from_response(response_data: dict) -> Optional[str]:
    """Extract content for validation from response"""
    if "result" in response_data:
        return response_data["result"]
    
    # Conversation history
    if "conversation_history" in response_data:
        messages = response_data["conversation_history"]
        if isinstance(messages, list) and messages:
            for msg in reversed(messages):
                if msg.get("type") == "ai":
                    return msg.get("content")
    return None

def is_protected_endpoint(path: str, endpoints: Dict[str, Any]) -> bool:
    """Check if endpoint needs protection"""
    return path in endpoints or any(path.startswith(ep.split('{')[0]) for ep in endpoints.keys())

def should_validate_input(path: str, endpoints: Dict[str, Any]) -> bool:
    """Check if endpoint needs input validation"""
    for endpoint, config in endpoints.items():
        if path == endpoint or path.startswith(endpoint.split('{')[0]):
            return config.get("input", False)
    return False