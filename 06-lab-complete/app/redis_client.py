"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

Tiêu chí 5:
  • Đọc REDIS_URL từ config
  • App vẫn phải KHỞI ĐỘNG ĐƯỢC khi Redis chưa sẵn sàng
  • redis_healthy() dùng cho GET /ready: Redis không kết nối được → False
"""
import redis
from app.config import settings


def get_redis():
    """Tạo client kết nối Redis dựa trên settings.redis_url hiện tại."""
    try:
        return redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
        )
    except Exception:
        return None


def redis_healthy() -> bool:
    """Kiểm tra Redis sẵn sàng cho readiness probe."""
    try:
        client = get_redis()
        if client is None:
            return False
        return bool(client.ping())
    except Exception:
        return False
