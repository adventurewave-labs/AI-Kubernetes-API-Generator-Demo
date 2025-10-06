#!/usr/bin/env python3
"""
Test different OpenRouter models to find working ones
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_openrouter_models():
    """Test various OpenRouter models to find working ones"""

    # Set API key
    os.environ["OPENROUTER_API_KEY"] = "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"

    print("🧪 Testing OpenRouter Models")
    print("=" * 50)

    # List of free models to test
    models_to_test = [
        "meta-llama/llama-3.1-8b-instruct:free",
        "microsoft/phi-3-medium-128k-free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "google/gemma-2-9b-it:free",
        "anthropic/claude-3-haiku",
        "anthropic/claude-3.5-sonnet:free"
    ]

    working_models = []

    for model in models_to_test:
        print(f"\n🔍 Testing model: {model}")

        try:
            from ai_platform_generator.agent import PlatformExtensionAgent

            agent = PlatformExtensionAgent(
                api_key=os.getenv("OPENROUTER_API_KEY"),
                model=model
            )

            # Try a simple request
            test_result = agent.parse_request("Create a simple API")

            print(f"✅ {model} - WORKING")
            working_models.append(model)

        except Exception as e:
            error_str = str(e)
            if "401" in error_str:
                print(f"❌ {model} - AUTH ERROR")
            elif "502" in error_str or "exhausted all available targets" in error_str:
                print(f"⚠️  {model} - UNAVAILABLE/OVERLOADED")
            else:
                print(f"❌ {model} - ERROR: {error_str}")

    print(f"\n🎯 Summary:")
    print(f"Working models: {len(working_models)}")
    for model in working_models:
        print(f"  ✅ {model}")

    if working_models:
        print(f"\n🚀 Use this command to run with a working model:")
        print(f"export OPENROUTER_MODEL='{working_models[0]}'")
        print(f"./run.sh demo")
    else:
        print(f"\n❌ No working models found. Check your OpenRouter account.")

    return working_models

if __name__ == "__main__":
    test_openrouter_models()