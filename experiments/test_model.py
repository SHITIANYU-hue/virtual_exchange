#!/usr/bin/env python3
import os
from anthropic import Anthropic

# Test which model names work
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

models_to_test = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20250131",
    "claude-3-5-sonnet-latest",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307"
]

for model in models_to_test:
    try:
        message = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"✓ {model} - WORKS")
        break  # Found a working model
    except Exception as e:
        print(f"✗ {model} - {str(e)[:80]}")
