"""Rate limiting: sliding window 60s theo API key, state trong Redis (sorted set)."""
import hashlib
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW = 60


def check_rate_limit(key: str) -> None:
    limit = settings.rate_limit_per_minute
    rkey = "rl:" + hashlib.sha256(key.encode()).hexdigest()[:16]
    now = time.time()
    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(rkey, 0, now - WINDOW)
        pipe.zcard(rkey)
        _, count = pipe.execute()
        if count >= limit:
            oldest = r.zrange(rkey, 0, 0, withscores=True)
            retry = int(WINDOW - (now - oldest[0][1])) + 1 if oldest else WINDOW
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} requests/minute",
                headers={"Retry-After": str(max(retry, 1))},
            )
        pipe = r.pipeline()
        pipe.zadd(rkey, {f"{now}:{uuid.uuid4().hex[:8]}": now})
        pipe.expire(rkey, WINDOW + 5)
        pipe.execute()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")
