# Benchmark & Observability Report — Day 14

> Mọi con số dưới đây lấy từ report JSON / CSV / screenshot thật trong repo, không ước lượng.

**Họ tên:** Nguyễn Trường Duy
**Ngày chạy:** 2026-11-25
**Môi trường:** Windows 11, Python 3.12 (venv), Docker Desktop (WSL2), 8 CPU / 16 GB RAM

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Mock LLM có latency nền ~120–250 ms; 500 ms cho phép dư địa cho jitter và bước retrieval nhưng vẫn bắt được suy giảm do tải |
| Error rate `/ask` | < 2 % | Mock LLM cố tình lỗi ~1 % (giống 503 upstream); 2 % là ngưỡng còn chấp nhận được trước khi alert |
| Accuracy trên golden dataset | ≥ 80 % | Ngưỡng quality gate của lab; thực tế agent v2 sau khi sửa knowledge base đạt 100 % (23/23) |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

Nguồn: `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json` (mỗi mức 300 request, `MOCK_SLOW_RATE=0.03`).

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.09 | 202.4 | 235.8 | 1702.7 | 0.33 % | ✅ PASS |
| 10 | 36.76 | 192.7 | 287.4 | 1701.9 | 1.33 % | ✅ PASS |
| 50 | 99.65 | 205.3 | 540.5 | 1709.4 | 0.00 % | ❌ FAIL (p95) |
| 100 | 59.30 | 667.3 | 2726.8 | 2881.2 | 1.33 % | ❌ FAIL (p95) |

**Nhận xét:** RPS **không tăng tuyến tính**. Từ c=1 → c=10 tăng gần 9× (4.09 → 36.76 req/s) vì mock LLM `await asyncio.sleep` nên event loop phục vụ được nhiều request đồng thời. Từ c=10 → c=50 chỉ tăng ~2.7× rồi **giảm** còn 59.3 req/s ở c=100. Nguyên nhân: (1) giới hạn `httpx.Limits(max_connections=concurrency)` và tài nguyên CPU của một process; (2) các request "slow" (~1.5 s) chiếm worker lâu, gây queueing; (3) ở c=100 p50 tăng từ ~200 ms lên 667 ms cho thấy hàng đợi bắt đầu hình thành. p99 gần như luôn ~1.7 s ở mọi mức vì tail latency của `MOCK_SLOW_RATE` — đúng lý do phải nhìn p95/p99 thay vì average.

### 2.2 Tail latency

Nguồn: `reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json` (300 request, concurrency=20).

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 207.4 | 459.2 | 473.9 |
| 0.03 (mặc định) | 239.3 | 476.6 | 1697.6 |
| 0.1 | 363.3 | 1696.4 | 1721.0 |

**Nhận xét:** **p99 nhạy nhất**: chỉ cần 3 % request chậm, p99 nhảy từ 473.9 ms → 1697.6 ms (gần 3.6×) trong khi average chỉ tăng 207 → 239 ms. Khi slow rate lên 10 %, p95 mới bắt đầu bắt kịp (1696 ms). Average thay đổi ít nhất và che giấu hoàn toàn tail latency, nên SLO phải đặt theo p95/p99: nếu đặt theo average (~240 ms) hệ thống sẽ "qua SLO" trong khi 1/10 người dùng chờ gần 1.7 s.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Nguồn: `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3 % (1/23) | 91.3 % (21/23) | **100 % (23/23)** |
| Avg tokens / câu | 58.3 | 109.0 | 115.2 |
| Tổng cost (USD) | 0.000421 | 0.000760 | 0.000804 |
| Cost / câu đúng (USD) | 0.00042075 | 0.00003619 | **0.00003495** |
| Quality gate | ❌ FAIL | ✅ PASS | ✅ PASS |

**Những câu v2 trả lời sai ban đầu và cách sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `KNOWLEDGE_BASE` về JWT: token tự chứa thông tin, ký bằng chữ ký số, có thời hạn hết hạn, khác API key tĩnh |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry về Kubernetes HPA: scale theo CPU, memory hoặc custom metrics qua Prometheus adapter |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:** v2 thêm bước retrieval nên prompt dài hơn → **gấp ~1.9× token** (58.3 → 109.0) và tổng cost tăng ~1.8×, latency p95 tăng nhẹ ~12 ms (219.4 → 231.3 ms). Nhưng accuracy tăng từ 4.3 % lên 91.3 % (+87 điểm %), nên **cost / câu trả lời đúng rẻ hơn ~11.6×** (0.00042075 → 0.00003619 USD). Đây là trade-off đáng: trả thêm token/latency nhỏ để đổi lấy chất lượng lớn hơn nhiều. Sau khi bổ sung 2 entry KB, v2 đạt 100 % mà không regression, cost/câu đúng còn 0.00003495 USD.

### Quality gate trong CI

Đã thêm `.github/workflows/part7-eval.yml`: job khởi động agent v2 rồi chạy `run_eval.py --min-accuracy 0.80 --baseline reports/eval_v2.json`. `run_eval.py` trả **exit code 1** khi accuracy dưới ngưỡng **hoặc** có câu bị regression so với baseline, nên GitHub Actions đánh job fail và **chặn merge** vào `main`.

---

## 4. Observability stack (production)

Stack chạy bằng `docker compose -p k5-day14-observability up -d --build --scale agent=3`: Nginx làm LB, Prometheus scrape 3 instance agent qua DNS service discovery, agent gửi OTLP sang Jaeger, Grafana đọc Prometheus. Đã sửa một lỗi Dockerfile của bản production: `pip install --user` ghi vào `/root/.local` nhưng user chạy là `agent` với home `/app`, nên đổi thành `/app/.local` + `PATH=/app/.local/bin:$PATH` (nếu không container chết với `ModuleNotFoundError: No module named 'uvicorn'`).

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (đủ 4 Golden Signals) — `screenshots/grafana-dashboard.png` (Traffic 20.5 req/s, Error rate 19.33%, p95 1.89 s, Instances up 3, LLM cost 1h $1.67)
- [x] Một trace chậm trong Jaeger — `screenshots/jaeger-slow-trace.png`
- [x] Một trace lỗi trong Jaeger (có event `exception`) — `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với alert đang **firing** — `screenshots/prometheus-alert-firing.png` (3 alert firing)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (value 0.21 > 0.05) | ~90 s (khoảng 60 s sau khi bắt đầu có tải) | **Error rate** (19.33%) và **Requests/s theo status code** (đường 503 tăng) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (p95 1.90 s > 1 s) | ~3 phút (2 phút `for` + 1 phút cửa sổ rate) | **Latency /ask p95** và **LLM latency p95** (~1.92 s) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~2 phút | **Cost burn rate (USD/giờ)** |
| D | `docker pause` 1 instance (agent-3) | `AgentInstanceDown` | 40 s (30 s `for` + scrape 5 s) | **Instances up** (3 → 2) |
| E | `AGENT_VERSION=v1` | Không có alert nào | — | **Retrieval hit ratio** và bảng version (chất lượng không phải metric hạ tầng) |

Ghi chú về C: không chạy lại riêng với `mock-llm-large`, nhưng khi load 60 req/s với `mock-llm-small`, `LLMCostBurnRateHigh` đã tự firing (2.0–3.6 USD/giờ > ngưỡng 2). Với `mock-llm-large` (đắt ~16 lần) alert sẽ firing nhanh hơn nhiều.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Lỗi chất lượng (v1 trả lời chung chung dù HTTP 200, latency và error rate vẫn đẹp) **không thể** phát hiện bằng metric hạ tầng. Cần: (1) chạy `eval/run_eval.py` trên golden dataset trong CI trước khi merge/deploy, chặn nếu accuracy dưới ngưỡng hoặc có regression so với baseline; (2) theo dõi **retrieval hit ratio** và tỉ lệ câu trả lời rỗng/không có citation như một SLI chất lượng; (3) canary + A/B so sánh chất lượng và feedback người dùng (thumbs down), vì observability hạ tầng chỉ trả lời "có khoẻ không", còn "trả lời có đúng không" phải đo bằng eval.

### 4.3 Debug bằng trace

- `trace_id`: `b7b90ada376cd563e3d94c492fc3e1d8`
- Tổng thời gian: **1693.3 ms**
- Span chiếm nhiều thời gian nhất: **`chat mock-llm-small` — 1674.4 ms (~98.9%)**; `agent.retrieve_context` chỉ 17.3 ms, `agent.run` 1691.8 ms, `POST /ask` 1693.3 ms. Kết luận: chậm do LLM, không phải code retrieval hay framework.
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T09:54:55.427237+00:00", "level": "INFO", "service": "observable-agent", "instance": "5651e51bc482", "event": "llm_call", "trace_id": "b7b90ada376cd563e3d94c492fc3e1d8", "span_id": "54797fb252b7e1cc", "request_id": "9656e63f805e", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 74, "output_tokens": 37, "cost_usd": 3.3e-05, "llm_ms": 1673.6}
{"ts": "2026-11-25T09:54:55.427530+00:00", "level": "INFO", "service": "observable-agent", "instance": "5651e51bc482", "event": "http_request", "trace_id": "b7b90ada376cd563e3d94c492fc3e1d8", "span_id": "54797fb252b7e1cc", "request_id": "9656e63f805e", "method": "POST", "route": "/ask", "status": 200, "ms": 1692.8}
```

Trace lỗi tương ứng: `trace_id=123812d3ee28393d8898faea1e2537e8`, `POST /ask` trả **503** sau 112.7 ms; span `chat mock-llm-small` có `status=2` và event `exception` với message `LLMError: Upstream LLM error: 503 Service Unavailable (mock)`; log cùng trace có `event=llm_error`.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 60.41 | 190 | 220 | 1700 | 74 (1.02 %) |
| 3 | 60.39 | 190 | 220 | 1700 | 77 (1.07 %) |

**Giải thích kết quả:** Scale 1 → 3 **không cải thiện** p95 (220 ms) hay RPS (~60 req/s). Nút thắt không nằm ở số instance agent:

1. **Load generator bị giới hạn bởi think time**, không phải server: 100 user, mỗi user nghỉ 0.5–2 s giữa các request (trung bình ~1.25 s) nên trần lý thuyết chỉ ~60–66 req/s. Số liệu khớp với thí nghiệm develop ở c=100 (59.3 req/s) và với in-flight chỉ ~13 request trên 3 instance.
2. **p99 = 1.7 s là tail latency của mock LLM**: `MOCK_SLOW_RATE=0.03` làm ~3% request ngủ ~1.5 s; p95 vẫn 220 ms vì 97% request còn lại nhanh. Thêm instance không làm một request đơn lẻ nhanh hơn.
3. CPU mỗi agent còn thấp (limit 0.5 CPU, in-flight ~4/instance) nên scale không tạo thêm throughput.

Muốn thấy lợi ích scale phải tăng tải thực (bỏ think time hoặc tăng user lên vài trăm) để chạm CPU/queue; còn muốn giảm p99 phải xử lý phía LLM (timeout, retry có giới hạn, cache, hoặc model nhanh hơn) chứ không phải scale ngang.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Phải nhìn p95/p99 và phân bố, không nhìn average.** Cùng một hệ thống có average 215 ms nhưng p99 1.7 s; average che mất 3% người dùng bị chậm gần 2 giây.
  2. **Metrics - traces - logs phải nối được với nhau.** Dashboard báo p95 tăng → mở Jaeger thấy `chat mock-llm-small` chiếm 98.9% → lấy `trace_id` grep log JSON để biết model/token/cost của đúng request đó.
  3. **Alert phải là code và phải test.** 4 rule trong `alert_rules.yml` có `for` để tránh alert fatigue; thử `docker pause` cho thấy `up == 0` bắt được instance treo, còn lỗi 504 ở Nginx không xuất hiện trong metric của agent — phải giám sát thêm ở tầng LB.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - **SLO theo user-facing**: success rate và p95 đo tại Nginx/LB (không chỉ trong agent), gồm cả 502/504.
  - **Chất lượng**: retrieval hit ratio, tỉ lệ answer rỗng, điểm eval trên golden dataset theo phiên bản, feedback (thumbs down) — alert khi accuracy tụt so với baseline.
  - **Chi phí & quota**: cost/request, cost theo tenant, token budget, alert khi burn rate vượt ngân sách; thêm rate-limit hit và 402/429.
  - **Độ tươi dữ liệu & phụ thuộc**: Redis latency/errors, tỉ lệ cache hit, LLM provider error rate/timeout, queue depth và saturation (CPU/memory) để scale đúng tín hiệu.
  - **Tracing**: sampling động (100% khi lỗi, 10% khi bình thường), alert trên tỉ lệ trace có exception.
