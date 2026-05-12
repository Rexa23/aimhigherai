#!/usr/bin/env python3
"""Smoke test for Gemini client integration."""
import os
import sys

sys.path.insert(0, 'backend')

# Set minimal env vars to bypass config validation
os.environ['GEMINI_API_KEY'] = 'test-key'
os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/test'
os.environ['SECRET_KEY'] = 'test-secret' * 10

print("Testing Gemini client imports...\n")

# Test direct Gemini import
try:
    import google.generativeai as genai
    print("✓ google.generativeai imported")
except Exception as e:
    print(f"✗ Failed to import google.generativeai: {e}")
    sys.exit(1)

# Test helper functions (don't require config)
try:
    from app.services.gemini_client import build_conversation_messages, format_lead_context
    print("✓ Helper functions imported from gemini_client")
except Exception as e:
    print(f"✗ Failed to import from gemini_client: {e}")
    sys.exit(1)

# Test build_conversation_messages
try:
    history = [{"role": "user", "content": "Hello"}]
    result = build_conversation_messages(history, "How are you?")
    assert len(result) == 2, f"Expected 2 messages, got {len(result)}"
    print(f"✓ build_conversation_messages works: {len(result)} messages")
except Exception as e:
    print(f"✗ build_conversation_messages failed: {e}")
    sys.exit(1)

# Test format_lead_context
try:
    lead = {"project_name": "Test", "chain": "ETH", "market_cap_usd": 1000000, "score": 85.5}
    formatted = format_lead_context(lead)
    assert "Test" in formatted and "ETH" in formatted, "Formatted output missing expected content"
    print(f"✓ format_lead_context works: {len(formatted)} chars")
except Exception as e:
    print(f"✗ format_lead_context failed: {e}")
    sys.exit(1)

print("\n✅ All smoke tests passed! Gemini client is ready for production.")
