# Day 14 Lab - Mission Answers

**Học viên:** Nguyễn Trường Duy  
**MSSV:** 2A202603589  
**Lớp:** K5-L3A  
**Repository:** `K5-L3A-DAY14-NguyenTruongDuy-2A202603589-Deployment-Benchmark-Observability`

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`

Đã phân tích mã nguồn `develop/app.py` và phát hiện các anti-patterns sau:

1. **Hardcoded Secrets & Credentials (Dòng 17–18):**
   - Code: `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`, `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`.
   - Vấn đề: Secret bị lưu trực tiếp trong mã nguồn. Khi commit lên Git, credentials sẽ bị lộ công khai hoặc trong lịch sử commit. Không thể rotate key linh hoạt mà không cần sửa code và deploy lại.
2. **Hardcoded Configuration & Debug Flag (Dòng 21–22, 53):**
   - Code: `DEBUG = True`, `MAX_TOKENS = 500`, `reload=True`.
   - Vấn đề: Cấu hình bị gắn chết trong mã nguồn thay vì nạp từ biến môi trường. Bật debug/reload trong môi trường production gây tốn tài nguyên và tiềm ẩn nguy cơ bảo mật (lộ stack trace chi tiết khi có exception).
3. **Insecure & Unstructured Logging (`print`) (Dòng 33–35, 38):**
   - Code: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`.
   - Vấn đề: Sử dụng hàm `print()` không có timestamp, log level, không có định dạng JSON để gửi vào log aggregators (như Loki, Datadog). Nguy hiểm hơn, lệnh này in trực tiếp secret API key ra stdout/log file.
4. **Thiếu Liveness & Readiness Health Checks:**
   - Không tồn tại các endpoint `/health` hay `/ready`.
   - Vấn đề: Container orchestration (Kubernetes, Docker Compose, Cloud platforms) không thể kiểm tra xem service có sống (liveness probe) hay đã sẵn sàng tiếp nhận traffic (readiness probe) hay chưa để tự động restart hoặc điều phối tải.
5. **Host & Port Binding Cố Định (Dòng 51–52):**
   - Code: `host="localhost"`, `port=8000`.
   - Vấn đề: Bind vào `localhost` (127.0.0.1) làm container bị cô lập, không cho phép kết nối mạng từ bên ngoài container hoặc host machine. Cổng `8000` bị cố định, không đọc biến môi trường `PORT` do các nền tảng PaaS (Railway, Render, Cloud Run) tự động inject.
6. **Thiếu Graceful Shutdown & Lifecycle Management:**
   - Code không bắt tín hiệu hệ thống (`SIGTERM`/`SIGINT`) và không định nghĩa lifespan context.
   - Vấn đề: Khi container bị scale down hoặc deploy phiên bản mới, tiến trình bị ngắt đột ngột (abrupt termination), làm hỏng các requests đang xử lý dang dở (in-flight requests).
7. **Xử lý Input qua Query Parameters cho POST request (Dòng 31):**
   - Code: `def ask_agent(question: str):`.
   - Vấn đề: FastAPI mặc định hiểu kiểu nguyên thủy không có body model là Query Parameter. Khi client gửi payload qua JSON body (chuẩn REST POST), server sẽ trả về lỗi HTTP 422 Unprocessable Content.

---

### Exercise 1.2: Kết quả chạy và gọi bản develop

Khi chạy server develop (`uvicorn app:app` trên cổng 8000) và thực hiện gọi API:

1. **Gọi đúng chuẩn của bản develop (Query Parameter):**
   ```bash
   curl -X POST "http://localhost:8000/ask?question=Hello"
   ```
   **Output:**
   ```json
   {"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
   ```

2. **Gọi với JSON Body (chuẩn REST thông thường):**
   ```bash
   curl -i -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{"question": "Hello"}'
   ```
   **Output:**
   ```http
   HTTP/1.1 422 Unprocessable Content
   date: Wed, 25 Nov 2026 07:34:03 GMT
   server: uvicorn
   content-length: 94
   content-type: application/json

   {"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
   ```
*Nhận xét:* Bản develop chạy được trên máy cá nhân nhưng vi phạm nghiêm trọng các tiêu chuẩn production về định dạng dữ liệu, quản lý cấu hình và bảo mật.

---

### Exercise 1.3: Bảng so sánh Develop (Basic) vs Production (Advanced)

| Đặc tính / Feature | Basic (Develop) | Advanced (Production) | Tại sao quan trọng? |
| :--- | :--- | :--- | :--- |
| **Quản lý Cấu hình (Config)** | Hardcoded trực tiếp trong code (`DEBUG = True`, `MAX_TOKENS = 500`) | Đọc tập trung qua `config.py` dùng biến môi trường (`os.getenv`), cấu hình qua `.env` | Tuân thủ 12-Factor App (Config in environment). Cho phép thay đổi cấu hình giữa dev/staging/prod mà không cần build lại code. |
| **Quản lý Secret** | Hardcode thẳng trong code (`sk-hardcoded-fake-key...`) | Đọc từ biến môi trường `AGENT_API_KEY`, validate khi khởi động | Tránh rò rỉ secret lên kho mã nguồn (GitHub), cho phép cơ chế xoay vòng key (secret rotation) an toàn. |
| **Host & Port Binding** | `host="localhost"`, `port=8000` | `host=settings.host` (`0.0.0.0`), `port=settings.port` (đọc từ `PORT`) | `0.0.0.0` cho phép ứng dụng nhận kết nối từ ngoài container; `PORT` giúp tương thích với cơ chế cấp port động của PaaS (Render, Railway). |
| **Logging** | Dùng hàm `print()`, log lộ API key ra terminal | Dùng thư viện `logging` chuẩn, xuất structured JSON format (`{"time":..., "level":..., "msg":...}`) | Structured logging giúp các hệ thống log aggregator (Loki, Datadog, ELK) dễ dàng parse, filter, thiết lập alert; không làm rò rỉ secret. |
| **Health Checks** | Không có endpoint kiểm tra | Cung cấp `/health` (Liveness) và `/ready` (Readiness) | Liveness probe giúp nền tảng phát hiện app treo để restart; Readiness probe giúp Load Balancer chỉ điều hướng traffic khi app đã sẵn sàng. |
| **Shutdown & Lifecycle** | Không xử lý tín hiệu, tắt đột ngột | Sử dụng `lifespan` context và xử lý tín hiệu `SIGTERM` (`handle_sigterm`) | Graceful shutdown cho phép hoàn thành các request đang chạy dang dở, giải phóng kết nối cơ sở dữ liệu, tránh lỗi gián đoạn 502 Bad Gateway khi deploy. |
| **CORS Middleware** | Không có | Cấu hình `CORSMiddleware` với danh sách `allowed_origins` | Bảo vệ API khỏi các truy vấn trái phép từ domain của bên thứ ba qua trình duyệt. |
| **Input Parsing** | Query Parameter (`/ask?question=...`) | JSON Request Body với HTTP 422 validation | Chuẩn hóa giao diện REST API, dễ dàng mở rộng truyền thêm metadata, user_id, conversation_id. |

---

### Tự kiểm tra (Self-Check CP1)
- **Minh chứng sửa lỗi trong `production/app.py`:**
  - *Anti-pattern:* `develop/app.py` (dòng 17, 51-52) hardcode secret và bind localhost.
  - *Đã sửa tại:* `production/app.py` (dòng 24, 196-197) import `settings` từ `config.py`:
    ```python
    # production/app.py dòng 196-197
    host=settings.host,   # 0.0.0.0 — nhận kết nối từ bên ngoài container
    port=settings.port,   # từ PORT env var do platform inject
    ```
  - *Đã sửa Health Check tại:* `production/app.py` (dòng 135–161) với `/health` trả 200 uptime và `/ready` kiểm tra trạng thái khởi động.
  - *Đã sửa Graceful Shutdown tại:* `production/app.py` (dòng 39–69, 180–189) bắt `SIGTERM` và sử dụng `lifespan`.

---

## Part 2: Docker

### Exercise 2.1: Dockerfile cơ bản questions

1. **Base image là gì?**
   - Base image trong `02-docker/develop/Dockerfile` là `python:3.11`. Đây là full distribution image của Python dựa trên Debian, dung lượng lớn (~1 GB khi tải về) do chứa đầy đủ các công cụ biên dịch (gcc, make), thư viện C headers, và package managers không cần thiết cho môi trường runtime.
2. **Working directory là gì?**
   - Working directory là `/app`, được thiết lập bởi chỉ thị `WORKDIR /app`. Mọi chỉ thị tiếp theo như `COPY`, `RUN`, `CMD` đều được thực thi tại đường dẫn này bên trong container.
3. **Tại sao `COPY requirements.txt` trước?**
   - Để tối ưu hóa cơ chế **Docker Layer Caching**. Các thư viện phụ thuộc (`requirements.txt`) thường rất ít khi thay đổi so với mã nguồn logic ứng dụng (`app.py`). Đặt `COPY requirements.txt .` và `RUN pip install ...` lên trước giúp Docker lưu lại cache của layer cài đặt package. Khi lập trình viên thay đổi code và build lại, Docker tái sử dụng cache từ các layer trước và chỉ build layer copy mã nguồn, giúp tốc độ build tăng gấp nhiều lần.
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?**
   - `ENTRYPOINT`: Xác định câu lệnh thực thi chính cố định của container. Lệnh này không bị ghi đè khi truyền tham số qua dòng lệnh `docker run <image> <args>` (trừ khi cố tình dùng cờ `--entrypoint`).
   - `CMD`: Xác định câu lệnh mặc định hoặc đối số mặc định truyền vào cho `ENTRYPOINT`. Khi người dùng truyền command/args tại thời điểm chạy `docker run`, phần giá trị của `CMD` sẽ bị ghi đè hoàn toàn.

---

### Exercise 2.2: Build và run `my-agent:develop`

- **Lệnh build từ root repo:**
  ```bash
  docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
  ```
- **Lệnh chạy container:**
  ```bash
  docker run -d -p 8000:8000 --name test-agent-dev my-agent:develop
  ```
- **Kết quả gọi container:**
  - Health check:
    ```bash
    curl http://localhost:8000/health
    ```
    *Output:*
    ```json
    {"status":"ok","uptime_seconds":2.8,"container":true}
    ```
  - Gọi `/ask` qua query parameter:
    ```bash
    curl -X POST "http://localhost:8000/ask?question=What+is+Docker"
    ```
    *Output:*
    ```json
    {"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
    ```

---

### Exercise 2.3: Multi-stage build & Kích thước Image

- **Phân tích Multi-stage trong `02-docker/production/Dockerfile`:**
  - **Stage 1 (Builder):** `FROM python:3.11-slim AS builder`. Cài đặt các công cụ biên dịch (`gcc`, `libpq-dev`), sau đó cài toàn bộ thư viện trong `requirements.txt` vào thư mục người dùng `/root/.local` bằng `pip install --user --no-cache-dir`.
  - **Stage 2 (Runtime):** `FROM python:3.11-slim AS runtime`. Tạo người dùng hệ thống bảo mật không có quyền root (`appuser`). Chỉ copy duy nhất thư mục packages đã compile từ Stage 1 (`COPY --from=builder /root/.local /home/appuser/.local`), copy mã nguồn app, đặt `HEALTHCHECK` và cấu hình chạy dưới quyền `USER appuser`.
  - **Tại sao image nhỏ hơn và bảo mật hơn?**
    - Loại bỏ hoàn toàn các trình biên dịch nặng (`gcc`, `libpq-dev`, build headers), apt-lists, và pip wheel cache khỏi image cuối.
    - Base image dùng `python:3.11-slim` thay vì `python:3.11` full.
    - Chạy bằng user non-root ngăn chặn nguy cơ leo thang đặc quyền (privilege escalation) nếu container bị tấn công.

- **Kích thước Image đo được thực tế từ lệnh `docker images`:**
  ```bash
  docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | Select-String "my-agent"
  ```
  *Bảng số đo thực tế trên máy:*

  | Image | Tag | Base Image | Size đo thực tế |
  | :--- | :--- | :--- | :--- |
  | `my-agent` | `develop` | `python:3.11` (Single-stage) | **1.67 GB** (~1670 MB) |
  | `my-agent` | `advanced` | `python:3.11-slim` (Multi-stage) | **240 MB** |

  - **Mức giảm dung lượng:** Giảm **1430 MB** (~1.43 GB).
  - **Tỷ lệ chênh lệch:** Giảm **85.6%** dung lượng so với bản develop! (Đạt tiêu chuẩn production < 500 MB).

---

### Exercise 2.4: Docker Compose stack

- **Sơ đồ kiến trúc các service trong Stack (`docker-compose.yml`):**

```mermaid
flowchart TD
    Client["Client / Browser (Port 80)"] -->|HTTP Traffic| Nginx["Nginx Reverse Proxy & Load Balancer (:80)"]
    
    subgraph Internal_Network ["Docker Internal Bridge Network (internal)"]
        Nginx -->|Reverse Proxy / Rate Limit| Agent["FastAPI AI Agent (:8000) (Non-root user)"]
        Agent -->|Session Cache & Rate Limiting| Redis["Redis (:6379) (redis:7-alpine)"]
        Agent -->|Vector DB / Knowledge Base| Qdrant["Qdrant (:6333) (qdrant:v1.9.0)"]
    end
```

- **Cơ chế giao tiếp giữa các service:**
  - Các service (`agent`, `redis`, `qdrant`, `nginx`) kết nối qua Docker bridge network tên `internal`.
  - Nginx đóng vai trò là reverse proxy duy nhất expose cổng ra bên ngoài (`80:80`). Khách hàng không thể truy cập trực tiếp vào agent, redis hay qdrant.
  - DNS nội bộ của Docker tự động phân giải domain name theo tên service (`http://agent_backend`, `redis://redis:6379`, `http://qdrant:6333`).

- **Khởi chạy và kết quả kiểm thử qua Nginx (Port 80):**
  - Chạy compose với project name riêng biệt:
    ```bash
    docker compose -p k5-day14-docker02 -f 02-docker/production/docker-compose.yml up -d
    ```
  - **Kết quả gọi `/health` qua Nginx:**
    ```bash
    curl -i http://localhost/health
    ```
    *Output:*
    ```http
    HTTP/1.1 200 OK
    Server: nginx
    Date: Wed, 25 Nov 2026 07:51:51 GMT
    Content-Type: application/json
    Content-Length: 95
    Connection: keep-alive
    X-Frame-Options: DENY
    X-Content-Type-Options: nosniff
    X-XSS-Protection: 1; mode=block

    {"status":"ok","uptime_seconds":4.3,"version":"2.0.0","timestamp":"2026-11-25T07:51:51.101401"}
    ```
  - **Kết quả gọi `/ask` qua Nginx:**
    ```bash
    curl -i -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'
    ```
    *Output:*
    ```http
    HTTP/1.1 200 OK
    Server: nginx
    Date: Wed, 25 Nov 2026 07:51:51 GMT
    Content-Type: application/json
    Content-Length: 95
    Connection: keep-alive
    X-Frame-Options: DENY
    X-Content-Type-Options: nosniff
    X-XSS-Protection: 1; mode=block

    {"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
    ```

---

### Tự kiểm tra (Self-Check CP2)
- **Multi-stage giảm dung lượng ở đâu:** Tách biệt stage builder và runtime; runtime loại bỏ toàn bộ gcc, headers, cache build, apt cache, chỉ lấy thành phẩm Python packages trong `/root/.local` và chạy trên nền slim.
- **Vì sao `COPY requirements.txt` phải đứng trước `COPY . .`:** Tận dụng triệt để layer cache của Docker. Mã nguồn thay đổi thường xuyên trong khi dependencies hiếm khi thay đổi; đưa dependencies lên trước giúp tái sử dụng cache, không phải tải lại thư viện khi build lại code.
- **Tính xác thực số đo:** Kích thước `1.67GB` (develop) và `240MB` (advanced) là số đo thực tế trên máy đo bằng `docker images`, không chép từ tài liệu.

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment (agent Part 6)

Deploy trực tiếp thư mục `06-lab-complete/` bằng Railway CLI + Dockerfile multi-stage.

- **Public URL:** https://agent-production-34801c79.up.railway.app
- **Project:** `ai-agent-day14` · **Services:** `agent` (Dockerfile) + `redis` (image `redis:7-alpine`, private domain `redis.railway.internal:6379`)
- **Biến môi trường đặt trên nền tảng (không ghi trong code):** `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE=10`, `DAILY_BUDGET_USD=10.0`, `ENVIRONMENT=production`. Railway tự inject `PORT`.
- **Screenshot:** `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`

Kết quả 4 lệnh tự kiểm ở CP6 (mỗi lệnh chỉ in mã HTTP):

```text
GET  /health                          -> 200   {"status":"ok","app":"production-agent","env":"production"}
GET  /ready                           -> 200   {"status":"ready","redis":true}
POST /ask (không có X-API-Key)        -> 401
POST /ask (có X-API-Key đúng)         -> 200
```

`deploy_check.py` xác nhận **8/8 checks passed** (health, readiness, auth 401/401/200, rate limit 429 sau 10 request, cost guard, logging).

> Lưu ý khi deploy: Railway đã từng build nhầm service Redis từ Dockerfile của agent (cả hai service cùng một thư mục). Khắc phục bằng cách tách `06-lab-complete/redis-service/Dockerfile` (`FROM redis:7-alpine`) và deploy riêng thư mục đó vào service `redis` (`railway up ./redis-service --path-as-root --service redis`). Sau đó `/ready` trả 200 với `"redis":true`.

### So sánh `railway.toml` và `render.yaml`

| Khác biệt | `railway.toml` (Railway) | `render.yaml` (Render) |
|---|---|---|
| Phạm vi khai báo | Chỉ cấu hình build + deploy của **một** service (`[build]`, `[deploy]`) | Blueprint IaC khai báo **toàn bộ** hạ tầng: web service + Redis trong cùng một file |
| Cách build | `builder = "DOCKERFILE"` → dùng Dockerfile multi-stage sẵn có | `runtime: docker` + `dockerfilePath`/root directory (hoặc `runtime: python` + `buildCommand`) |
| Health check | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Secret / biến môi trường | Set thủ công bằng `railway variables set ...` hoặc Dashboard; không nằm trong file | Khai báo trong `envVars`: `generateValue: true` (Render tự sinh), `sync: false` (điền tay trên Dashboard) |
| Redis | Service riêng, thêm bằng CLI/Dashboard (image `redis:7-alpine`) | Khai báo declarative `- type: redis` ngay trong blueprint |
| Tính tái lập | Thấp hơn: phần env/Redis phải thao tác lệnh | Cao: một file mô tả đủ, tạo lại môi trường bằng “New Blueprint” |

**Vì sao chọn Railway làm nền tảng chính:** CLI `railway up` deploy nhanh từ đúng thư mục `06-lab-complete/`, log/build stream ngay trong terminal và hợp với Dockerfile multi-stage đã viết. `render.yaml` được giữ làm phương án IaC dự phòng vì mô tả đầy đủ service + Redis + secret trong một file, dễ tái lập.

### Exercise 3.3: Pipeline Cloud Run (chỉ đọc file, không deploy)

`cloudbuild.yaml` định nghĩa CI/CD chạy khi push lên `main`: (1) step `test` cài dependencies và chạy `pytest`; (2) step `build` build Docker image tag `$COMMIT_SHA` + `latest`, dùng `--cache-from` để tận dụng layer cache; (3) step `push` đẩy image lên Google Container Registry; (4) step `deploy` gọi `gcloud run deploy` với image theo `$COMMIT_SHA`, region `asia-southeast1`, `--min-instances=1/--max-instances=10` và secret lấy từ Secret Manager qua `--set-secrets` (không hardcode). `service.yaml` là Knative Service IaC: autoscaling 1–10, `containerConcurrency: 80`, `timeoutSeconds: 60`, `livenessProbe` trỏ `/health`, `startupProbe` trỏ `/ready`, biến `AGENT_API_KEY`/`OPENAI_API_KEY` đọc từ `secretKeyRef`.

### Tự kiểm tra (Self-Check CP6)

- URL public chạy đúng 4 lệnh: `/health` 200, `/ready` 200, `/ask` thiếu key 401, `/ask` có key 200.
- `AGENT_API_KEY` và `REDIS_URL` đặt bằng biến môi trường trên Railway, không có trong code hay Git.
- `railway.toml` dùng `builder = "DOCKERFILE"` và `healthcheckPath = "/health"`; `render.yaml` khai báo web service + Redis + secret không ghi giá trị thật.

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (Develop)

Chạy ứng dụng `04-api-gateway/develop/app.py` với cấu hình biến môi trường `AGENT_API_KEY=secret-key-123`:

1. **Trường hợp không truyền API Key (Kỳ vọng: 401 Unauthorized):**
   ```bash
   curl -i -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{"question":"hello"}'
   ```
   *Output thực tế:*
   ```http
   HTTP/1.1 401 Unauthorized
   date: Wed, 25 Nov 2026 07:59:47 GMT
   server: uvicorn
   content-length: 67
   content-type: application/json

   {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
   ```

2. **Trường hợp truyền sai API Key (Kỳ vọng: 403 Forbidden):**
   ```bash
   curl -i -X POST "http://localhost:8000/ask" -H "X-API-Key: wrong-key" -H "Content-Type: application/json" -d '{"question":"hello"}'
   ```
   *Output thực tế:*
   ```http
   HTTP/1.1 403 Forbidden
   date: Wed, 25 Nov 2026 07:59:47 GMT
   server: uvicorn
   content-length: 29
   content-type: application/json

   {"detail":"Invalid API key."}
   ```

3. **Trường hợp truyền đúng API Key (Kỳ vọng: 200 OK):**
   ```bash
   curl -i -X POST "http://localhost:8000/ask" -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question":"hello"}'
   ```
   *Output thực tế:*
   ```http
   HTTP/1.1 200 OK
   date: Wed, 25 Nov 2026 07:59:47 GMT
   server: uvicorn
   content-length: 145
   content-type: application/json

   {"question":"hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
   ```

---

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting (Production)

Chạy ứng dụng `04-api-gateway/production/app.py` với Full Security Stack.

1. **Lấy JWT Token:**
   Đăng nhập với tài khoản `student` / `demo123` (tài khoản role user, giới hạn 10 requests/phút):
   ```bash
   curl -X POST "http://localhost:8000/auth/token" \
        -H "Content-Type: application/json" \
        -d '{"username": "student", "password": "demo123"}'
   ```
   *Output:*
   ```json
   {
     "access_token": "eyJhbGciOiJIUzI1NiIs...",
     "token_type": "bearer",
     "expires_in_minutes": 60,
     "hint": "Include in header: Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
   }
   ```

2. **Gọi endpoint bảo vệ `/ask` khi không có Token (401 Unauthorized):**
   ```bash
   curl -i -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{"question": "what is docker?"}'
   ```
   *Output thực tế:*
   ```http
   HTTP/1.1 401 Unauthorized
   date: Wed, 25 Nov 2026 08:00:12 GMT
   server: uvicorn
   www-authenticate: Bearer
   content-length: 76
   content-type: application/json
   x-content-type-options: nosniff
   x-frame-options: DENY
   x-xss-protection: 1; mode=block
   referrer-policy: strict-origin-when-cross-origin

   {"detail":"Authentication required. Include: Authorization: Bearer <token>"}
   ```

3. **Gọi với Token hợp lệ (200 OK) (Token đã được che):**
   ```bash
   curl -i -X POST "http://localhost:8000/ask" \
        -H "Authorization: Bearer <TOKEN_CHE_GIA_TRI_THAT>" \
        -H "Content-Type: application/json" \
        -d '{"question": "what is docker?"}'
   ```
   *Output thực tế:*
   ```http
   HTTP/1.1 200 OK
   date: Wed, 25 Nov 2026 08:00:12 GMT
   server: uvicorn
   content-length: 196
   content-type: application/json
   x-content-type-options: nosniff
   x-frame-options: DENY
   x-xss-protection: 1; mode=block
   referrer-policy: strict-origin-when-cross-origin

   {"question":"what is docker?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
   ```

4. **Kích hoạt Rate Limiting bằng vòng lặp 15 requests (Kỳ vọng: từ request thứ 11 trả về 429 Too Many Requests):**
   - Vòng lặp gửi liên tục 15 request với token của user `student` (quota 10 req/phút):
     - Request #1 đến #10: Trả về `HTTP/1.1 200 OK`.
     - Request #11 đến #15: Trả về `HTTP/1.1 429 Too Many Requests`.
   - **Output `curl -i` của request thứ 11 (429 Too Many Requests):**
     ```http
     HTTP/1.1 429 Too Many Requests
     date: Wed, 25 Nov 2026 08:00:57 GMT
     server: uvicorn
     x-ratelimit-limit: 10
     x-ratelimit-remaining: 0
     x-ratelimit-reset: 1795593718
     retry-after: 59
     content-length: 98
     content-type: application/json
     x-content-type-options: nosniff
     x-frame-options: DENY
     x-xss-protection: 1; mode=block
     referrer-policy: strict-origin-when-cross-origin

     {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
     ```

---

### Exercise 4.4: Cost Guard Implementation & So sánh Rate Limiting

- **Kiến trúc và cơ chế hoạt động của Cost Guard (`cost_guard.py`):**
  - **Mục tiêu:** Kiểm soát và bảo vệ ngân sách chi phí gọi LLM API, tránh rủi ro phát sinh hóa đơn khổng lồ do các truy vấn phức tạp hoặc bị lạm dụng.
  - **Theo dõi số lượng token & tính chi phí:** Sau mỗi request hoàn thành, hệ thống ghi nhận số lượng `input_tokens` và `output_tokens` vào `UsageRecord`. Chi phí tính theo đơn giá mô hình (ví dụ GPT-4o-mini: \$0.15/1M input tokens, \$0.60/1M output tokens).
  - **Hạn mức 2 tầng (Two-tier Quota):**
    1. *Hạn mức cá nhân (`daily_budget_usd = $1.0`):* Ngăn một người dùng tiêu xài quá giới hạn cho phép trong ngày. Nếu vượt quá, trả về mã lỗi `HTTP 402 Payment Required`.
    2. *Hạn mức toàn hệ thống (`global_daily_budget_usd = $10.0`):* Bảo vệ tổng ngân sách hệ thống khỏi việc nhiều người dùng cùng lúc đẩy chi phí lên cao. Nếu vượt quá, trả về `HTTP 503 Service Unavailable`.
  - **Cơ chế cảnh báo sớm (Early Warning):** Khi người dùng chạm ngưỡng 80% ngân sách (`warn_at_pct = 0.8`), hệ thống ghi log cảnh báo (`WARNING`) để quản trị viên hoặc người dùng kịp thời nhận biết.
  - **Khả năng Production:** Trong code mẫu lưu memory, khi triển khai production hệ thống sẽ lưu vào Redis (hash `cost:{user_id}:{date}`) kèm TTL tự động reset vào đầu ngày UTC, đảm bảo tính stateless và đồng bộ trên nhiều instance.

- **So sánh: Rate Limiting vs Cost Guard — Tại sao cần cả hai?**
  - **Rate Limiting:** Bảo vệ **tốc độ truy cập** (Request Velocity) và **sức tải hạ tầng** (CPU, RAM, Network I/O, Database connection pools). Ngăn chặn tấn công DoS/DDoS hoặc bot spam hàng nghìn request trong vài giây. Tuy nhiên, Rate Limiting không quan tâm kích thước payload (1 request hỏi 100,000 tokens văn bản tốn hàng chục USD vẫn chỉ tính là 1 request).
  - **Cost Guard:** Bảo vệ **tài chính và ngân sách LLM** (Financial Budget). Dù kẻ tấn công gửi request rất chậm (ví dụ 1 request mỗi 2 phút, hoàn toàn lọt qua Rate Limiter), nhưng mỗi request gửi nội dung khổng lồ thì Cost Guard sẽ lập tức phát hiện chi phí tích lũy vượt quá $1.0/ngày và khóa truy vấn ngay lập tức.
  - **Kết luận:** Hệ thống bắt buộc phải có cả hai tầng bảo vệ: Rate Limiting giữ cho hạ tầng máy chủ luôn ổn định, còn Cost Guard giữ cho tài chính dự án an toàn.

---

### Tự kiểm tra (Self-Check CP3)
- Đã chạy vòng lặp curl 15 lần và trực tiếp nhận được mã `HTTP 429 Too Many Requests` ở request thứ 11 với đầy đủ headers `x-ratelimit-limit: 10`, `x-ratelimit-remaining: 0`, `retry-after: 59`.
- Đã che hoàn toàn giá trị token trong tài liệu báo cáo theo đúng yêu cầu bảo mật.

---

## Part 5: Scaling & Reliability

### Exercise 5.1 & 5.2: Liveness vs Readiness & Graceful Shutdown (Develop)

Chạy ứng dụng `05-scaling-reliability/develop/app.py` trên cổng 8000:

1. **Kết quả kiểm thử Health Check Endpoints:**
   - **Liveness Probe (`GET /health`):**
     ```bash
     curl -i http://localhost:8000/health
     ```
     *Output:*
     ```http
     HTTP/1.1 200 OK
     date: Wed, 25 Nov 2026 08:05:05 GMT
     server: uvicorn
     content-length: 195
     content-type: application/json

     {"status":"ok","uptime_seconds":1.2,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T08:05:06.858802+00:00","checks":{"memory":{"status":"ok","note":"psutil not installed"}}}
     ```
   - **Readiness Probe (`GET /ready`):**
     ```bash
     curl -i http://localhost:8000/ready
     ```
     *Output:*
     ```http
     HTTP/1.1 200 OK
     date: Wed, 25 Nov 2026 08:05:05 GMT
     server: uvicorn
     content-length: 37
     content-type: application/json

     {"ready":true,"in_flight_requests":1}
     ```
   - **Gọi `/ask`:**
     ```bash
     curl -i -X POST "http://localhost:8000/ask?question=Hello"
     ```
     *Output:*
     ```http
     HTTP/1.1 200 OK
     date: Wed, 25 Nov 2026 08:05:05 GMT
     server: uvicorn
     content-length: 95
     content-type: application/json

     {"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
     ```

2. **Phân biệt Liveness Probe vs Readiness Probe:**
   - **Liveness (`/health`):** Trả lời câu hỏi *"Agent process có còn sống và phản hồi không?"*. Container orchestrator (Docker, Kubernetes) gọi định kỳ. Nếu endpoint này fail (timeout hoặc mã lỗi khác 200), orchestrator kết luận app đã bị deadlock/freeze và sẽ lập tức **restart container**.
   - **Readiness (`/ready`):** Trả lời câu hỏi *"Agent đã sẵn sàng nhận thêm traffic mới chưa?"*. Load Balancer kiểm tra endpoint này trước khi route request vào. Trả về 503 khi app đang tải model vào RAM lúc khởi động, hoặc khi hệ thống đang trong tiến trình shutdown. Khi fail, Load Balancer **tạm ngừng gửi traffic mới** tới instance đó nhưng **không restart container**.

3. **Cơ chế Graceful Shutdown:**
   - Bắt tín hiệu `SIGTERM` từ hệ điều hành / orchestrator.
   - Ngay lập tức đặt cờ `_is_ready = False`. Khi đó endpoint `/ready` trả về `503 Service Unavailable`, báo hiệu cho Load Balancer lập tức loại instance khỏi danh sách nhận traffic mới.
   - Middleware `track_requests` theo dõi bộ đếm `_in_flight_requests`. Vòng lặp shutdown đợi cho đến khi toàn bộ các request đang xử lý hoàn tất (`_in_flight_requests == 0`) hoặc chạm timeout tối đa (30 giây).
   - Đóng các kết nối cơ sở dữ liệu và giải phóng tài nguyên trước khi tiến trình kết thúc, đảm bảo không có request nào của người dùng bị ngắt ngang gây lỗi `502 Bad Gateway`.

---

### Exercise 5.3 – 5.5: Stateless Architecture & Horizontal Scaling với Redis + Nginx (Production)

1. **Tại sao lưu State trong RAM (In-Memory) bị hỏng khi Scale nhiều Instance?**
   - Khi triển khai nhiều instance phía sau một bộ cân bằng tải (Load Balancer - Nginx), các request liên tiếp của cùng một user sẽ được điều phối tới các instance khác nhau theo thuật toán Round-Robin hoặc Least Connections.
   - Nếu instance lưu conversation history trong bộ nhớ RAM cục bộ (ví dụ Python dictionary):
     - Request 1 đến `Instance A`: User nói *"Tên tôi là Duy"*. `Instance A` ghi nhớ vào RAM.
     - Request 2 đến `Instance B`: User hỏi *"Tên tôi là gì?"*. Do `Instance B` có vùng nhớ RAM tách biệt hoàn toàn với `Instance A`, nó không có dữ liệu ngữ cảnh này và trả lời không biết $\rightarrow$ Sai lệch trải nghiệm người dùng nghiêm trọng.
     - Ngoài ra, nếu bất kỳ instance nào bị crash hoặc restart khi deploy/auto-scale, toàn bộ session lưu trên instance đó sẽ bị mất sạch.

2. **Giải pháp Stateless Design với Redis:**
   - Thiết kế instance hoàn toàn không lưu trạng thái (Stateless).
   - Dữ liệu session và conversation history được lưu trữ tập trung tại Redis cluster thông qua key pattern `session:{session_id}` kèm thời gian sống (TTL).
   - Bất kỳ instance nào nhận request từ Nginx đều có thể truy xuất và cập nhật cùng một phiên làm việc trên Redis một cách đồng bộ và nhất quán.

3. **Kiểm thử thực tế với 3 Agent Replicas (`test_stateless.py`):**
   - Đã tạo `.env.local` và khởi chạy stack bằng lệnh:
     ```bash
     docker compose -p k5-day14-scaling up -d --build --scale agent=3
     ```
   - Nginx mở cổng host **8080**, route traffic vào 3 container agent (`agent-1`, `agent-2`, `agent-3`).
   - Chạy script kiểm thử:
     ```bash
     python test_stateless.py
     ```
   - **Output thực tế ghi nhận từ terminal:**
     ```text
     ============================================================
     Stateless Scaling Demo
     ============================================================

     Session ID: 89ad3a04-0170-471b-9abb-8606034d3bfe

     Request 1: [instance-8d2248]
       Q: What is Docker?
       A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

     Request 2: [instance-83a1c2]
       Q: Why do we need containers?
       A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

     Request 3: [instance-1c85ad]
       Q: What is Kubernetes?
       A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ O...

     Request 4: [instance-8d2248]
       Q: How does load balancing work?
       A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

     Request 5: [instance-83a1c2]
       Q: What is Redis used for?
       A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

     ------------------------------------------------------------
     Total requests: 5
     Instances used: {'instance-8d2248', 'instance-83a1c2', 'instance-1c85ad'}
     ✅ All requests served despite different instances!

     --- Conversation History ---
     Total messages: 10
       [user]: What is Docker?...
       [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
       [user]: Why do we need containers?...
       [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...
       [user]: What is Kubernetes?...
       [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đây...
       [user]: How does load balancing work?...
       [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
       [user]: What is Redis used for?...
       [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...

     ✅ Session history preserved across all instances via Redis!
     ```

4. **Giải thích kết quả:**
   - 5 requests trong cùng một phiên hội thoại đã được Nginx phân phối đều tới **cả 3 instances khác nhau** (`instance-8d2248`, `instance-83a1c2`, `instance-1c85ad`).
   - Mặc dù mỗi câu hỏi được xử lý bởi một container riêng biệt, toàn bộ 10 tin nhắn (5 câu hỏi và 5 câu trả lời) vẫn được tổng hợp và bảo toàn trọn vẹn trong Redis.
   - Sau khi kiểm thử thành công, đã chạy `docker compose -p k5-day14-scaling down` để dọn dẹp tài nguyên và trả lại cổng mạng.

---

### Tự kiểm tra (Self-Check CP4)
- **Hiểu sâu sắc Liveness vs Readiness:** Đã chỉ rõ sự khác biệt trong hành vi xử lý của orchestrator (Restart vs De-route traffic).
- **Khả năng Stateless:** Đã chứng minh qua output thực tế của `test_stateless.py`, xác nhận toàn bộ 3 instance tham gia xử lý nhưng không mất bất kỳ mẩu dữ liệu lịch sử hội thoại nào nhờ Redis.

---

## Part 6: Final Project (Production-ready AI Agent)

### Kết quả chạy `check_production_ready.py` (`PASS 12/12`)

Đã hoàn thiện toàn bộ mã nguồn trong thư mục `06-lab-complete/` và chạy script chấm `check_production_ready.py`.

```text
================================================================
  Production Readiness Check — Day 14 Lab
================================================================

✅ 1. Dockerfile (multi-stage, < 500 MB)
     ✅ Dockerfile tồn tại
     ✅ requirements.txt tồn tại
     ✅ Multi-stage build (≥ 2 lệnh FROM)
     ✅ Base image gọn (slim / alpine / distroless) — stage cuối dùng python:3.11-slim
     ✅ Chạy bằng user non-root
     ✅ Có HEALTHCHECK
     ✅ Docker: build image thành công — 10s
     ✅ Docker: image < 500 MB — 238 MB
     ✅ Docker: container chạy được, GET /health → 200

✅ 2. docker-compose.yml (agent + redis)
     ✅ docker-compose.yml tồn tại
     ✅ Có service agent (build từ Dockerfile) + redis — services: agent, redis — đọc bằng docker compose config
     ✅ Service agent kết nối redis (REDIS_URL + depends_on)

✅ 3. .dockerignore
     ✅ .dockerignore tồn tại và có nội dung
     ✅ .dockerignore loại trừ .env (secrets)
     ✅ .dockerignore loại trừ __pycache__, venv

✅ 4. Health check endpoint (GET /health)
     ✅ Code có route /health
     ✅ Khi chạy: GET /health → 200 — uvicorn --workers 2

✅ 5. Readiness endpoint (GET /ready)
     ✅ Code có route /ready
     ✅ Khi chạy: GET /ready → 200
     ✅ Khi chạy: Redis mất kết nối → /ready 503 (còn /health vẫn 200)

✅ 6. API Key authentication
     ✅ Code đọc header X-API-Key
     ✅ Khi chạy: thiếu / sai API key → 401
     ✅ Khi chạy: API key đúng → 200

✅ 7. Rate limiting
     ✅ Code trả HTTP 429 khi vượt giới hạn
     ✅ Khi chạy: vượt giới hạn → 429 — 429 sau 5 request thành công (RATE_LIMIT_PER_MINUTE=5)
     ✅ Khi chạy: state nằm trong Redis — restart agent vẫn bị 429

✅ 8. Cost guard
     ✅ Code trả HTTP 402 khi hết budget
     ✅ Khi chạy: hết budget → 402 — 402 ở request thứ 2

✅ 9. Config từ environment variables
     ✅ app/config.py đọc biến môi trường
     ✅ .env.example liệt kê đủ biến cấu hình
     ✅ .env nằm trong .gitignore
     ✅ Không hard-code secret trong code
     ✅ Khi chạy: agent dùng AGENT_API_KEY và RATE_LIMIT_PER_MINUTE từ env

✅ 10. Structured logging
     ✅ Code ghi log dạng JSON
     ✅ Khi chạy: mọi dòng log của app là JSON hợp lệ — 7 dòng JSON

✅ 11. Graceful shutdown
     ✅ Code xử lý SIGTERM / lifespan shutdown
     ✅ Khi chạy: SIGTERM lúc đang có request → request vẫn 200, process tự thoát — exit code 0
     ✅ Docker: `docker stop` tắt êm (exit code 0, < 10s) — exit code 0, 0.4s

✅ 12. Public URL ready (Railway / Render config)
     ✅ Có railway.toml hoặc render.yaml (không chỉ toàn comment)
     ✅ railway.toml: builder + healthcheckPath = "/health"
     ✅ render.yaml: web service + healthCheckPath /health
     ✅ render.yaml: secret không ghi thẳng giá trị (generateValue / sync: false)
     ✅ App lắng nghe theo biến PORT do platform cấp

================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

---

### Giải thích chuyên sâu: Vì sao `/health` trả 200 khi Redis chết còn `/ready` phải trả 503?

Đây là một trong những nguyên lý thiết kế hệ thống phân tán quan trọng nhất trong môi trường Production (Kubernetes, Docker Swarm, PaaS):

1. **Bản chất của Liveness Probe (`GET /health`):**
   - **Mục đích:** Trả lời cho orchestrator câu hỏi: *"Tiến trình (process) của container này có còn hoạt động bình thường hay đã bị treo (deadlock / OOM / freeze)?"*.
   - **Hành vi của Orchestrator:** Nếu `/health` trả về lỗi (khác 200) hoặc timeout $\rightarrow$ Orchestrator ngay lập tức **tiêu diệt (kill) và restart container**.
   - **Khi Redis gặp sự cố / mất kết nối:** Bản thân process của Agent vẫn đang chạy hoàn toàn bình thường, mã nguồn không bị lỗi hay treo. Nếu `/health` kiểm tra Redis và trả về 500/503, orchestrator sẽ liên tục restart container của agent theo vòng lặp vô tận (*CrashLoopBackOff*). Việc restart container agent liên tục không thể giải quyết được sự cố của cụm Redis, mà còn gây tốn tài nguyên CPU/RAM, làm quá tải Docker daemon và khiến toàn bộ cụm dịch vụ tê liệt. Do đó, `/health` **phải luôn trả 200** chừng nào process agent còn sống.

2. **Bản chất của Readiness Probe (`GET /ready`):**
   - **Mục đích:** Trả lời cho Load Balancer câu hỏi: *"Agent này hiện tại có đủ điều kiện để tiếp nhận và xử lý request mới từ người dùng hay không?"*.
   - **Hành vi của Load Balancer:** Nếu `/ready` trả về 503 $\rightarrow$ Load Balancer lập tức **gỡ instance này ra khỏi danh sách định tuyến (de-route)**, không chuyển traffic của người dùng tới đây nữa; **tuyệt đối không restart container**.
   - **Khi Redis gặp sự cố:** Agent phụ thuộc vào Redis để kiểm tra Rate Limiting, Cost Guard, và truy xuất Session/Conversation History. Khi không có Redis, Agent không thể bảo vệ hệ thống và không thể xử lý logic nhất quán. Vì vậy, `/ready` **bắt buộc phải trả về 503 Service Unavailable**. Load Balancer sẽ tạm thời giữ hoặc route request sang instance khác. Ngay khi Redis phục hồi kết nối, `/ready` sẽ tự động trả lại HTTP 200 mà không cần restart bất kỳ container nào, hệ thống lập tức tiếp tục phục vụ người dùng trơn tru.

---

## AI Log

- **Mục đích sử dụng:** Hỗ trợ phân tích cơ chế bảo mật xác thực (API Key vs JWT), thuật toán Sliding Window Counter trong Rate Limiting, kiến trúc Stateless, thiết kế Full Security Stack cho Final Project (`06-lab-complete/`), và thiết lập môi trường test POSIX trong container để kiểm tra tín hiệu SIGTERM cho Graceful shutdown.
- **Lời nhắc / Câu hỏi:** Hoàn thiện các file TODO trong `06-lab-complete/` (`config.py`, `redis_client.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`, `main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`), khắc phục lỗi thiếu module `redis`, giải pháp chạy script chấm trong container POSIX để vượt qua kiểm tra SIGTERM.
- **Kết quả nhận được:** Mã nguồn hoàn chỉnh cho 12 tiêu chí, phân tích bản chất Liveness vs Readiness, script Docker build runner posix và kết quả chấm đạt tuyệt đối `PASS 12/12` (43/43 checks passed).
- **Tự kiểm tra & hiệu chỉnh:** Đã tự kiểm tra bằng `check_production_ready.py --static-only` (đạt 28/28 checks), cài đặt `redis` và `psutil`, xây dựng container `checker-runner` với đầy đủ Docker CLI và Docker Compose plugin kết nối `--net=host`, chạy script chấm toàn diện và ghi nhận kết quả `PASS 12/12 — PRODUCTION READY!`.
