import time
from dotenv import load_dotenv
import anthropic

load_dotenv()

PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6":         {"input": 3.00, "output": 15.00},
}

def run_test(model):
    client = anthropic.Anthropic()
    start = time.perf_counter()
    response = client.messages.create(
        model=model,
        max_tokens=50,
        messages=[{"role": "user", "content": "hi"}],
    )
    elapsed = time.perf_counter() - start

    usage = response.usage
    p = PRICING[model]
    cost = (usage.input_tokens / 1_000_000 * p["input"]) + (usage.output_tokens / 1_000_000 * p["output"])

    print(f"\nModel : {model}")
    print(f"Reply : {response.content[0].text}")
    print(f"Time  : {elapsed:.2f}s")
    print(f"Tokens: {usage.input_tokens} in / {usage.output_tokens} out")
    print(f"Cost  : ${cost:.6f}")

run_test("claude-haiku-4-5-20251001")
run_test("claude-sonnet-4-6")
