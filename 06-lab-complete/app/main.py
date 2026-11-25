"""
Production AI Agent — Part 6 Final Project
"""
import sys
import json
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.auth import verify_api_key
from app.redis_client import redis_healthy
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_cost
from utils.mock_llm import ask as llm_ask


# Tiêu chí 10: Structured logging — mọi dòng log là 1 JSON object hợp lệ
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "msg": record.getMessage(),
            "name": record.name,
        }
        return json.dumps(log_obj)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("production_agent")
logger.setLevel(logging.INFO)
logger.handlers = [handler]
logger.propagate = False


# Tiêu chí 11: Graceful shutdown xử lý SIGTERM qua FastAPI lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(json.dumps({"event": "startup", "port": settings.port, "env": settings.environment}))
    yield
    # Shutdown khi nhận SIGTERM: hoàn thành request đang xử lý rồi thoát
    logger.info(json.dumps({"event": "shutdown", "msg": "Graceful shutdown complete"}))


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


# Tiêu chí 4: GET /health — Liveness probe (luôn trả 200 khi process còn chạy, kể cả khi Redis chết)
@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": "production-agent",
        "env": settings.environment,
    }


# Tiêu chí 5: GET /ready — Readiness probe (200 khi sẵn sàng, 503 khi Redis mất kết nối)
@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service unavailable",
        )
    return {
        "status": "ready",
        "redis": True,
    }


# Endpoint chính: /ask được bảo vệ bởi API key, Rate limit, Cost guard
@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    # Tiêu chí 7: Rate limiting (HTTP 429)
    check_rate_limit(key)

    # Tiêu chí 8: Cost guard trước khi gọi LLM (HTTP 402)
    check_budget()

    # Gọi LLM (mock)
    answer = llm_ask(body.question)

    # Tính toán và ghi nhận chi phí token
    in_tokens = max(1, len(body.question.split()) * 2)
    out_tokens = max(1, len(answer.split()) * 2)
    record_cost(in_tokens, out_tokens)

    # Log structured JSON
    logger.info(json.dumps({
        "event": "ask",
        "status": 200,
        "question_len": len(body.question),
        "in_tokens": in_tokens,
        "out_tokens": out_tokens,
    }))

    return {"question": body.question, "answer": answer}
