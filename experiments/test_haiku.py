import anthropic
import os

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Try to list or test available models
try:
    response = client.messages.create(
        model="claude-haiku-4-20250514",
        max_tokens=10,
        messages=[{"role": "user", "content": "hi"}]
    )
except Exception as e:
    print(f"claude-haiku-4-20250514: {e}")

# Try Haiku 3.5
try:
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=10,
        messages=[{"role": "user", "content": "hi"}]
    )
    print("claude-3-5-haiku-20241022: ✅ WORKS")
except Exception as e:
    print(f"claude-3-5-haiku-20241022: {e}")

# Try latest naming
try:
    response = client.messages.create(
        model="claude-haiku-4-20250514",
        max_tokens=10,
        messages=[{"role": "user", "content": "hi"}]
    )
    print("claude-haiku-4-20250514: ✅ WORKS")
except Exception as e:
    print(f"claude-haiku-4-20250514: {e}")
