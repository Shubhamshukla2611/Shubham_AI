#!/usr/bin/env python
"""Test voice agent system initialization."""

from app.services.voice_agent import VoiceAgent
from app.services.calendar import get_calendar_manager

def main():
    print("=" * 70)
    print("  VOICE AGENT SYSTEM TEST")
    print("=" * 70)
    
    # Test 1: Initialize voice agent
    try:
        agent = VoiceAgent()
        tools = agent.get_tools()
        print(f"\n✓ Voice Agent initialized successfully")
        print(f"  • Tools available: {len(tools)}")
        for tool in tools:
            print(f"    - {tool['name']}")
    except Exception as e:
        print(f"\n✗ Voice Agent failed: {e}")
        return False
    
    # Test 2: Initialize calendar manager
    try:
        cal = get_calendar_manager()
        print(f"\n✓ Calendar Manager initialized")
        print(f"  • Status: {'Configured' if cal.is_available() else 'Not yet configured'}")
    except Exception as e:
        print(f"\n✗ Calendar Manager failed: {e}")
        return False
    
    # Test 3: Check Vapi config
    try:
        config = agent.create_vapi_assistant_config()
        print(f"\n✓ Vapi Assistant Config generated")
        print(f"  • Name: {config.get('name')}")
        print(f"  • Voice Provider: {config['voice']['provider']}")
        print(f"  • Tools registered: {len(config['tools'])}")
    except Exception as e:
        print(f"\n✗ Vapi Config generation failed: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("  ✓ ALL TESTS PASSED - Voice agent system is ready!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Configure GOOGLE_CALENDAR_CREDENTIALS_JSON in .env")
    print("  2. Get VAPI_API_KEY, VAPI_ASSISTANT_ID, VAPI_PHONE_NUMBER_ID")
    print("  3. Restart backend: uvicorn app.main:app --reload")
    print("  4. Test: curl http://localhost:8000/api/voice/phone-number")
    print("  5. Call the phone number provided!")
    print()
    
    return True

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
