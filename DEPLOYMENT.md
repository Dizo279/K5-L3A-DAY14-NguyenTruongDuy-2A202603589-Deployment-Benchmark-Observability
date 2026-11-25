# Deployment Guide — AI Agent (Day 14)

> Hướng dẫn deploy **production-ready AI Agent** (`06-lab-complete/`) lên Railway và Render.

---

## Yêu cầu trước khi deploy

| Yêu cầu | Chi tiết |
|---------|---------|
| Code đã PASS 12/12 | `python check_production_ready.py` báo **PASS 12/12** |
| GitHub repo public/private | Đã push tất cả commits lên `origin/main` |
| Không commit `.env` | File `.env` nằm trong `.gitignore` |

---

## Option A — Deploy lên Railway

### Bước 1: Cài Railway CLI

```bash
npm i -g @railway/cli
railway login
```

### Bước 2: Khởi tạo project

```bash
cd 06-lab-complete
railway init
# Chọn "Create new project" khi được hỏi
```

### Bước 3: Thêm Redis

Railway Dashboard → Project → **+ New** service tên `redis`, sau đó deploy image Redis từ thư mục `redis-service/` (không để Railway tự build nhầm Dockerfile của agent):

```bash
cd 06-lab-complete
railway up ./redis-service --path-as-root --service redis
```

Thư mục `redis-service/Dockerfile` chỉ chứa `FROM redis:7-alpine` + `CMD redis-server --appendonly yes`. Private domain là `redis.railway.internal:6379`, dùng làm `REDIS_URL`.

> **Lỗi đã gặp:** ban đầu cả service `agent` lẫn `redis` đều build từ cùng Dockerfile (uvicorn), khiến `/ready` trả 503. Deploy riêng `redis-service/` vào service `redis` là cách khắc phục — sau đó `/ready` trả `200 {"status":"ready","redis":true}`.

### Bước 4: Set environment variables

```bash
railway variables set AGENT_API_KEY=<your-secret-key>
railway variables set REDIS_URL=<redis-url-from-step-3>
railway variables set RATE_LIMIT_PER_MINUTE=10
railway variables set DAILY_BUDGET_USD=10.0
railway variables set ENVIRONMENT=production
```

> **QUAN TRỌNG:** `AGENT_API_KEY` phải là giá trị bí mật, không commit vào Git.

### Bước 5: Deploy

```bash
railway up
# Đợi build xong (~2-3 phút)
railway domain   # → nhận public URL
```

### Bước 6: Verify

```bash
# Kiểm tra health
curl https://<your-app>.railway.app/health

# Chạy script kiểm tra đầy đủ
python deploy_check.py --url https://<your-app>.railway.app --api-key <your-secret-key>

# Hoặc dùng check_production_ready.py
python check_production_ready.py --public-url https://<your-app>.railway.app
```

---

## Option B — Deploy lên Render

### Bước 1: Push repo lên GitHub (nếu chưa)

```bash
git push origin main
```

### Bước 2: Tạo Redis instance trên Render

Render Dashboard → **New** → **Redis** → Free tier → Tạo xong, copy **Internal URL**.

### Bước 3: Tạo Web Service

1. Render Dashboard → **New** → **Web Service**
2. Kết nối GitHub repo
3. Cấu hình:
   - **Root Directory:** `06-lab-complete`
   - **Environment:** Docker
   - **Dockerfile Path:** `./Dockerfile`
   - **Health Check Path:** `/health`

### Bước 4: Set Environment Variables

| Key | Value |
|-----|-------|
| `AGENT_API_KEY` | *your-secret-key* |
| `REDIS_URL` | *internal-redis-url-from-step-2* |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `10.0` |
| `ENVIRONMENT` | `production` |

> Trên Render, `PORT` được inject tự động — không cần set thủ công.

### Bước 5: Deploy

Click **Create Web Service** → đợi build xong (~3-5 phút).

### Bước 6: Verify

```bash
curl https://<your-app>.onrender.com/health

python deploy_check.py --url https://<your-app>.onrender.com --api-key <your-secret-key>
```

---

## Kết quả Deploy

| Platform | URL | Trạng thái |
|----------|-----|------------|
| Railway  | https://agent-production-34801c79.up.railway.app | ✅ Deployed & Verified |
| Render   | *(không deploy; so sánh trong `MISSION_ANSWERS.md` Part 3)* | — |

**Kết quả verify thực tế (2026-11-25):**

| Kiểm tra | Kết quả |
|----------|---------|
| `GET /health` | `200 {"status":"ok","app":"production-agent","env":"production"}` |
| `GET /ready` | `200 {"status":"ready","redis":true}` |
| `POST /ask` không key | `401` |
| `POST /ask` sai key | `401` |
| `POST /ask` đúng key | `200` |
| Rate limit | `429` sau 10 request |
| `deploy_check.py` | **8/8 checks passed** |

> Lệnh verify: `python deploy_check.py --url https://agent-production-34801c79.up.railway.app --api-key <AGENT_API_KEY>`
> (đặt `PYTHONUTF8=1` trên Windows để tránh lỗi cp1252 khi in emoji).

---

## Checklist Checkpoint 6

- [x] `Dockerfile` multi-stage, < 500 MB, non-root user, `HEALTHCHECK`, `CMD` dùng `${PORT}`
- [x] `docker-compose.yml` agent + redis với `depends_on`
- [x] `.dockerignore` loại trừ `.env`, `__pycache__`, `venv`
- [x] `railway.toml` builder=`DOCKERFILE`, `healthcheckPath="/health"`
- [x] `render.yaml` type=web, `healthCheckPath: /health`, secret dùng `generateValue`/`sync: false`
- [x] `.env.example` liệt kê đủ biến
- [x] `deploy_check.py` script kiểm tra public URL
- [x] PASS 12/12 (`python check_production_ready.py`)
- [x] Đã deploy lên Railway → https://agent-production-34801c79.up.railway.app
- [x] Redis chạy đúng image `redis:7-alpine` (deploy từ `redis-service/`) → `/ready` 200
- [x] `deploy_check.py` → **8/8 checks passed** trên URL public
- [x] 4 lệnh CP6: `/health` 200, `/ready` 200, `/ask` không key 401, `/ask` có key 200
- [x] Ảnh trong `screenshots/`: `dashboard.png`, `running.png`, `test.png`
