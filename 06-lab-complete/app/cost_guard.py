"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""
from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_in_memory_cost = {}


def _get_cost_key() -> str:
    return f"cost:total:{settings.agent_api_key}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    client = get_redis()
    key = _get_cost_key()
    current_cost = 0.0

    if client is not None:
        try:
            val = client.get(key)
            if val is not None:
                current_cost = float(val)
        except Exception:
            current_cost = _in_memory_cost.get(key, 0.0)
    else:
        current_cost = _in_memory_cost.get(key, 0.0)

    if current_cost >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Daily budget exceeded",
                "used_usd": current_cost,
                "budget_usd": settings.daily_budget_usd,
            },
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    client = get_redis()
    key = _get_cost_key()

    if client is not None:
        try:
            client.incrbyfloat(key, cost)
        except Exception:
            _in_memory_cost[key] = _in_memory_cost.get(key, 0.0) + cost
    else:
        _in_memory_cost[key] = _in_memory_cost.get(key, 0.0) + cost

    return cost
