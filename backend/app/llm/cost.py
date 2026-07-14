"""Token cost tracking.

On the Groq free tier, cost_usd is always 0.0. We still track token counts for
rate-limit awareness. When you graduate to a paid tier, replace the PRICING dict
with real values (USD per 1M tokens).
"""

PRICING: dict[str, dict[str, float]] = {
    "llama-3.3-70b-versatile": {"input": 0.0, "output": 0.0},  # Free tier
    "meta-llama/llama-4-scout-17b-16e-instruct": {"input": 0.0, "output": 0.0},  # Free tier
    "llama-3.1-8b-instant": {"input": 0.0, "output": 0.0},  # Free tier
}


def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    pricing = PRICING.get(model, {"input": 0.0, "output": 0.0})
    return (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000
