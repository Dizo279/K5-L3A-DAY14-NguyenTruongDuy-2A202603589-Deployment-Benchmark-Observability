"""
Config — 12-Factor: mọi cấu hình đọc từ biến môi trường.

Tiêu chí 9:
  • Đọc các biến từ môi trường: PORT, ENVIRONMENT, AGENT_API_KEY, REDIS_URL,
    RATE_LIMIT_PER_MINUTE, DAILY_BUDGET_USD, MONTHLY_BUDGET_USD
  • Không hardcode secret
"""
import os
from dataclasses import dataclass


@dataclass
class Settings:
    port: int = int(os.getenv("PORT", "8000"))
    environment: str = os.getenv("ENVIRONMENT", "development")
    agent_api_key: str = os.getenv("AGENT_API_KEY", "")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    daily_budget_usd: float = float(os.getenv("DAILY_BUDGET_USD", "10.0"))
    monthly_budget_usd: float = float(os.getenv("MONTHLY_BUDGET_USD", "300.0"))


settings = Settings()
