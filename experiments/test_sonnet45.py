#!/usr/bin/env python3
import os
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Try different Sonnet 4.5 naming patterns
models_to_test = [
    "claude-sonnet-4-5-20250929",
    "claude-4-5-sonnet-20250929",
    "claude-sonnet-4.5-20250929",
    "claude-4.5-sonnet-20250929",
    "sonnet-4-5-20250929",
    "claude-sonnet-4-5",
    "claude-4-sonnet-20250929",
]

for model in models_to_test:
    try:
        message = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"✓ {model} - WORKS!")
        break
    except Exception as e:
        error_msg = str(e)[:100]
        print(f"✗ {model} - {error_msg}")
