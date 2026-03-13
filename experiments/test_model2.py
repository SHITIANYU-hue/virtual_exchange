#!/usr/bin/env python3
import os
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Try newer naming patterns
models_to_test = [
    "claude-3-5-sonnet-20240620",
    "claude-3-5-sonnet-v2-20240620",
    "claude-sonnet-3-5-20240620",
    "claude-3-haiku-20240307",  # We know this works
    "claude-3-opus-4-20250514",
    "claude-4-opus-20250514",
]

for model in models_to_test:
    try:
        message = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"✓ {model} - WORKS")
    except Exception as e:
        error_msg = str(e)[:100]
        print(f"✗ {model} - {error_msg}")
