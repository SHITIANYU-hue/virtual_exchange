import anthropic
import os

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

models_to_test = [
    "claude-3-haiku-20240307",
    "claude-3-5-haiku-20241022",
    "claude-haiku-4-20250131",
]

for model in models_to_test:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}]
        )
        print(f"✅ {model}: WORKS")
    except Exception as e:
        print(f"❌ {model}: {str(e)[:100]}")
