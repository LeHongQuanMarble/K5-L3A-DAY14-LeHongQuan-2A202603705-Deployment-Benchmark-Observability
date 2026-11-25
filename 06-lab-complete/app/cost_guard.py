"""Cost guard: cộng dồn chi phí LLM trong Redis theo ngày, vượt DAILY_BUDGET_USD → 402."""
import time

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _key() -> str:
    return "cost:" + time.strftime("%Y-%m-%d", time.gmtime())


def check_budget() -> None:
    try:
        spent = float(r.get(_key()) or 0.0)
    except Exception:
        raise HTTPException(status_code=503, detail="Cost guard unavailable")
    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exhausted")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens / 1000) * PRICE_INPUT_PER_1K + (output_tokens / 1000) * PRICE_OUTPUT_PER_1K
    try:
        k = _key()
        r.incrbyfloat(k, cost)
        r.expire(k, 2 * 86400)
    except Exception:
        pass
    return cost
