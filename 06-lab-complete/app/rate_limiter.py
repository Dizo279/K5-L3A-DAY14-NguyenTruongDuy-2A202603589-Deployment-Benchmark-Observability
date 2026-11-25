"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi restart
"""
import time
import secrets
from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis


def check_rate_limit(key: str) -> None:
    client = get_redis()
    if client is None:
        return

    now = time.time()
    window_seconds = 60
    redis_key = f"ratelimit:{key}"

    try:
        pipe = client.pipeline()
        # Loại bỏ các request ngoài window 60s
        pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
        # Đếm số request hiện tại trong window
        pipe.zcard(redis_key)
        res = pipe.execute()
        current_count = res[1]

        if current_count >= settings.rate_limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(settings.rate_limit_per_minute),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Ghi nhận request mới
        pipe = client.pipeline()
        member = f"{now}-{secrets.token_hex(4)}"
        pipe.zadd(redis_key, {member: now})
        pipe.expire(redis_key, window_seconds + 5)
        pipe.execute()
    except HTTPException:
        raise
    except Exception:
        # Nếu Redis gặp sự cố ngoài dự kiến, cho qua để không chặn request khi test độc lập
        pass
