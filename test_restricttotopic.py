#!/usr/bin/env python3
"""
Test script for RestrictToTopic integration
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from guards import Guard
from guards.hub import RestrictToTopic

def test_restricttotopic():
    """Test RestrictToTopic validator with valid and invalid topics"""
    
    # Create a guard with RestrictToTopic
    guard = Guard().use(
        RestrictToTopic(
            valid_topics=["technology", "programming", "database", "analytics", "data analysis", "mongodb", "chat", "conversation"],
            on_fail="exception"
        )
    )
    
    print("🧪 Testing RestrictToTopic validator...")
    
    # Test valid topics
    valid_tests = [
        "How can I optimize my MongoDB queries?",
        "What are the best practices for database design?",
        "Can you help me with Python programming?",
        "I need help with data analysis techniques.",
        "How do I set up a chat application?",
    ]
    
    # Test invalid topics
    invalid_tests = [
        "What's the weather like today?",
        "Can you recommend a good restaurant?",
        "Tell me about sports news",
        "What's the latest celebrity gossip?",
    ]
    
    print("\n✅ Testing VALID topics:")
    for i, test_input in enumerate(valid_tests, 1):
        try:
            result = guard.validate(test_input)
            print(f"  {i}. PASS: '{test_input[:50]}...' - Validation successful")
        except Exception as e:
            print(f"  {i}. FAIL: '{test_input[:50]}...' - Unexpected error: {e}")
    
    print("\n❌ Testing INVALID topics (should be blocked):")
    for i, test_input in enumerate(invalid_tests, 1):
        try:
            result = guard.validate(test_input)
            print(f"  {i}. FAIL: '{test_input[:50]}...' - Should have been blocked but passed")
        except Exception as e:
            print(f"  {i}. PASS: '{test_input[:50]}...' - Correctly blocked: {type(e).__name__}")
    
    print("\n🎉 RestrictToTopic test completed!")

if __name__ == "__main__":
    test_restricttotopic()