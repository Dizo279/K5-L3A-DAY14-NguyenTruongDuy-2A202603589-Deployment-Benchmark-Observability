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

## AI Log

- **Mục đích sử dụng:** Hỗ trợ phân tích mã nguồn giữa `01-localhost-vs-production/develop` và `production`, xác định các anti-pattern theo 12-Factor App và đo kiểm output API.
- **Lời nhắc / Câu hỏi:** Phân tích sự khác biệt giữa hai phiên bản app, chạy curl test trên cả hai endpoint, tổng hợp bảng so sánh chuẩn hóa.
- **Kết quả nhận được:** Danh sách 7 anti-patterns chi tiết kèm số dòng code, output curl test thực tế (query param vs json body) và bảng so sánh chi tiết.
- **Tự kiểm tra & hiệu chỉnh:** Đã tự chạy lệnh uvicorn nền và curl trên máy local, xác minh lỗi 422 khi truyền JSON vào bản develop, kiểm tra endpoint `/health` và `/ready` trên bản production trả về kết quả chuẩn xác.
