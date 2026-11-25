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

## AI Log

- **Mục đích sử dụng:** Hỗ trợ giải thích cơ chế Docker multi-stage build, layer caching, phân tích cấu trúc Docker Compose và chuẩn hóa sơ đồ Mermaid kiến trúc.
- **Lời nhắc / Câu hỏi:** Phân tích `02-docker/develop/Dockerfile` và `02-docker/production/Dockerfile`, câu lệnh build từ root, cách đo dung lượng container và kiểm tra kết nối qua Nginx.
- **Kết quả nhận được:** Câu trả lời cho 4 câu hỏi Exercise 2.1, giải thích multi-stage, sơ đồ kiến trúc Mermaid cho Compose stack.
- **Tự kiểm tra & hiệu chỉnh:** Đã tự thực thi build cả 2 Docker image từ root repository, đo kích thước thực tế qua `docker images`, tạo `.env.local`, khởi chạy Docker Compose stack và thực hiện curl test qua Nginx cổng 80 đạt HTTP 200 OK cho cả `/health` và `/ask`.
