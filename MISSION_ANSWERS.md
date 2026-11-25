# MISSION_ANSWERS — Day 14

**Họ tên:** Lê Hồng Quân · **MSSV:** 2A202603705 · **Lớp:** K5-L3A

## Part 1 — Localhost vs Production

### Exercise 1.1 — Anti-pattern trong `01-localhost-vs-production/develop/app.py`
1. API key và DB URL hardcode: `OPENAI_API_KEY = "sk-hardcoded-..."`, `DATABASE_URL = "postgresql://admin:password123@..."` → push lên GitHub là lộ secret.
2. Không có config management: `DEBUG = True`, `MAX_TOKENS = 500` cố định trong code, không đọc từ env.
3. Dùng `print()` thay vì logging có cấu trúc, và còn in cả secret: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`.
4. Không có endpoint health check → platform không biết khi nào agent chết để restart.
5. Port và host cố định: `host="localhost", port=8000` → không nhận được PORT do Railway/Render cấp, container không nhận kết nối từ ngoài.
6. `reload=True` (debug reload) trong production; không xử lý SIGTERM/graceful shutdown.

### Exercise 1.2 — Chạy bản develop
```
$ curl -X POST "http://localhost:8000/ask?question=Hello"
{"answer":"..."}   # chạy được, nhưng không production-ready (có 6 vấn đề ở trên)
```
(App develop nhận `question` qua query, gửi JSON sẽ bị 422.)

### Exercise 1.3 — So sánh develop vs production
| Feature | Basic | Advanced | Tại sao quan trọng? |
|---|---|---|---|
| Config | Hardcode trong code | Env vars qua `config.py` / `.env` | Cùng một image chạy dev/staging/prod; secret không nằm trong git |
| Health check | Không có | `/health` (liveness) + `/ready` (readiness) | Platform tự restart khi chết, load balancer chỉ route tới instance sẵn sàng |
| Logging | `print()`, in cả secret | JSON log có cấu trúc, không log secret | Máy parse/lọc/tìm theo field được; không rò rỉ secret |
| Shutdown | Đột ngột | Graceful (xử lý SIGTERM/lifespan) | Request đang chạy không bị cắt khi deploy/scale |
| Host/Port | `localhost:8000` cố định | `0.0.0.0` + `PORT` từ env | Container và PaaS cấp port động |

## Part 2 — Docker

### Exercise 2.1 (`02-docker/develop/Dockerfile`)
1. Base image: `python:3.11` (full distribution, ~1 GB).
2. Working directory: `/app`.
3. `COPY requirements.txt` trước `COPY app.py`: layer cài dependencies được cache; sửa code không phải `pip install` lại.
4. `CMD` là lệnh mặc định, dễ bị ghi đè khi `docker run <image> <cmd>`; `ENTRYPOINT` là chương trình cố định, tham số truyền vào được nối thêm.

### Exercise 2.2 — kết quả gọi container
```
$ docker run -d -p 8000:8000 my-agent:develop
$ curl -X POST "http://localhost:8000/ask?question=What+is+Docker"
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.3 — kích thước image (đo bằng `docker images`)
| Image | Size |
|---|---|
| `my-agent:develop` (single-stage, `python:3.11`) | 1.67 GB |
| `my-agent:advanced` (multi-stage, `python:3.11-slim`) | 240 MB |

Giảm ~85.6 % (1.67 GB → 240 MB). Stage 1 (builder) cài gcc/libpq-dev và pip install dependencies vào `/root/.local`; Stage 2 (runtime) chỉ copy site-packages + code sang base `slim`, bỏ toàn bộ build tools, chạy bằng user non-root. Nhỏ hơn vì base slim và không mang theo compiler/cache.

### Exercise 2.4 — Docker Compose stack
```
Client ──80/443──▶ nginx ──▶ agent ──▶ redis   (session cache / rate limit)
                                   └──▶ qdrant  (vector DB)
```
Services: `agent`, `redis`, `qdrant`, `nginx` (chỉ nginx publish cổng; các service nói chuyện qua network `internal`). Kết quả:
```
$ curl http://localhost/health
{"status":"ok","uptime_seconds":19.1,"version":"2.0.0",...}
$ curl http://localhost/ask -X POST -H 'Content-Type: application/json' -d '{"question":"Explain microservices"}'
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

## Part 3 — Cloud Deployment

- **Trạng thái:** đã deploy lên Render (gói Free). URL: https://agent-audl.onrender.com (chi tiết trong [DEPLOYMENT.md](DEPLOYMENT.md)). Ảnh: `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png` (`test.png` là kết quả `curl` thật được render thành ảnh).
- **So sánh `railway.toml` và `render.yaml`** (của agent Part 6):
  - Railway dùng TOML cho từng service: `[build] builder="DOCKERFILE"`, `[deploy] healthcheckPath="/health"`, restart policy; biến môi trường và Redis được tạo bằng CLI/dashboard (`railway variables set`, thêm plugin Redis) rồi tham chiếu.
  - Render dùng một Blueprint YAML mô tả cả hạ tầng: `services` gồm `type: web` (`runtime: docker`, `healthCheckPath`) và `type: redis`; `REDIS_URL` nối bằng `fromService`, secret bằng `generateValue: true`/`sync: false`. Tức Render khai báo được Redis và secret ngay trong file (IaC đầy đủ hơn), còn Railway cấu hình build/deploy trong file và phần còn lại trên nền tảng.
- **Exercise 3.3 — Cloud Run CI/CD (`cloudbuild.yaml` + `service.yaml`):** push lên main kích hoạt Cloud Build chạy 4 bước tuần tự: (1) `test`: cài requirements và chạy `pytest tests/`; (2) `build`: build image Docker gắn tag `$COMMIT_SHA` và `latest`, dùng `--cache-from` để tận dụng layer cache; (3) `push`: đẩy mọi tag lên Container Registry; (4) `deploy`: `gcloud run deploy` ở region asia-southeast1 với min 1 / max 10 instance, 512Mi, secret `OPENAI_API_KEY` lấy từ Secret Manager. `service.yaml` là bản IaC (Knative) của cùng service: concurrency 80/instance, minScale 1 để tránh cold start, giới hạn CPU/memory, env và secretKeyRef, deploy bằng `gcloud run services replace`.

## Part 4 — API Security

### Exercise 4.1 — API key (`04-api-gateway/develop`)
- Key được kiểm ở dependency `verify_api_key` gắn vào `/ask` qua `Depends`; so sánh header `X-API-Key` với biến môi trường `AGENT_API_KEY`.
- Sai/thiếu key → 401. Rotate key: đổi biến môi trường rồi restart/redeploy (không sửa code).
```
$ curl -si -X POST localhost:8000/ask -H 'Content-Type: application/json' -d '{"question":"Hello"}'
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
$ curl -si -X POST localhost:8000/ask -H 'X-API-Key: secret-key-123' -H 'Content-Type: application/json' -d '{"question":"Hello"}'
HTTP/1.1 200 OK
{"question":"Hello","answer":"..."}
```

### Exercise 4.2 — JWT (`04-api-gateway/production`)
Lấy token ở `POST /auth/token` (`student`/`demo123`), token đã che:
```
$ curl -si -X POST localhost:8000/ask -H 'Content-Type: application/json' -d '{"question":"Explain JWT"}'
HTTP/1.1 401 Unauthorized
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}
$ curl -si -X POST localhost:8000/ask -H "Authorization: Bearer <REDACTED>" -H 'Content-Type: application/json' -d '{"question":"Explain JWT"}'
HTTP/1.1 200 OK
{"question":"Explain JWT","answer":"...","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

### Exercise 4.3 — Rate limiting
- Thuật toán: **sliding window** (deque timestamp theo user). Limit: 10 req/phút cho user, 100 req/phút cho admin (role admin dùng `rate_limiter_admin` — đó là cách "bypass").
```
# vòng lặp 15 lần với token student
1-9   → 200
10-15 → 429
$ curl -si ... (lần thứ 16)
HTTP/1.1 429 Too Many Requests
retry-after: 59
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```
(Lần gọi thứ 10 đã bị 429 vì lần `/ask` ở bước 4.2 đã dùng 1 slot trong cùng cửa sổ 60 s.)

### Exercise 4.4 — Cost guard
Mỗi user có `UsageRecord` (input/output tokens theo ngày). Trước khi gọi LLM, `check_budget` tính chi phí đã dùng = tokens/1000 × giá; vượt `daily_budget_usd` (1 USD/user) → HTTP 402, vượt budget toàn cục → 503, đạt 80 % thì cảnh báo log. Sau khi gọi, `record_usage` cộng thêm tokens. Bản demo lưu in-memory (mất khi restart, không chia sẻ giữa instance); trong agent Part 6 mình lưu tổng chi phí theo ngày trong Redis (`INCRBYFLOAT cost:YYYY-MM-DD`, TTL 2 ngày). Rate limit bảo vệ tốc độ, cost guard bảo vệ tiền: một client chậm nhưng gọi prompt cực dài vẫn đốt tiền nên cần cả hai.

## Part 5 — Scaling & Reliability

- **5.1 Health vs readiness:** `/health` (liveness) chỉ trả 200 khi process còn sống — fail thì platform restart container. `/ready` (readiness) trả 200 khi phụ thuộc (Redis…) sẵn sàng, 503 nếu không — fail thì load balancer ngừng route traffic tới instance đó nhưng không restart. Vì vậy `/health` phải 200 kể cả khi Redis chết, còn `/ready` phải 503.
- **5.2 Graceful shutdown:** khi nhận SIGTERM, uvicorn ngừng nhận kết nối mới, chờ request đang chạy xong rồi chạy phần shutdown của `lifespan` và thoát với exit code 0; `docker stop` của agent Part 6 xong trong 0.6 s, request đang chạy vẫn trả 200 (script chấm xác nhận).
- **5.3 Stateless:** state (history, rate limit, chi phí) lưu trong Redis chứ không trong biến global, vì nhiều instance/worker không chia sẻ RAM; request tiếp theo có thể rơi vào instance khác.
- **5.4–5.5 Chạy 3 instance sau Nginx** (`docker compose -p k5-day14-scaling up -d --build --scale agent=3`, `python test_stateless.py`):
```
Total requests: 5
Instances used: {'instance-8bee31', 'instance-64b3fb', 'instance-f9d9dc'}
✅ All requests served despite different instances!
Total messages: 10
✅ Session history preserved across all instances via Redis!
```
5 request cùng một session được 3 instance khác nhau phục vụ (Nginx round-robin) mà history 10 message vẫn đầy đủ vì nằm trong Redis.

## Part 6 — Kết quả `check_production_ready.py` (chế độ đầy đủ, có Docker)

```
=========================================================
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

## Part 7 — Benchmark & Observability
Xem [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md). Mình cũng sửa một lỗi trong `benchmark-observability/production/Dockerfile`: thư mục `--user` bị copy sang `/home/agent/.local` nhưng user `agent` có home `/app` nên Python không tìm thấy `uvicorn` (container restart liên tục); thêm `/home/agent/.local/lib/python3.11/site-packages` vào `PYTHONPATH`.

## AI log
Mình dùng Claude Code (Claude Sonnet 5.5) để hoàn thành bài: viết các file TODO của `06-lab-complete/`, chạy các lệnh benchmark/Docker, chụp ảnh bằng Chrome headless và soạn các file báo cáo. Mọi số liệu trong bài lấy từ lần chạy thật trên máy (JSON/CSV trong `reports/`, `benchmark-results/`).

**Phần deploy và kiểm thử bổ sung (cũng dùng Claude Code):**
- *Hỏi gì / nhận gì:* nhờ AI deploy `06-lab-complete/` lên Render gói Free. AI đề xuất thêm `plan: free` và `rootDir: 06-lab-complete` vào `render.yaml` (nếu thiếu `plan`, Render mặc định gói Starter có phí) và điều khiển Chrome để tạo Blueprint với Blueprint Path `06-lab-complete/render.yaml`.
- *Mình tự làm / kiểm tra:* mình tự đăng nhập Render và tự lấy `AGENT_API_KEY` từ dashboard (AI không đọc được key). Mình chạy `utils/test_deployed.py` bằng key đó: `/ask` có key → 200, 25 request liên tiếp → 19 × 200 rồi 6 × 429 (`reports/deployed_test.log`).
- *Kịch bản D chạy lại:* lần gộp A+B+D ban đầu không thấy `AgentInstanceDown` firing, nên chạy riêng stack 3 agent, `docker pause production-agent-3`; alert firing sau 41 s (`reports/scenario_d_instance_down.log`). Số này lấy từ Prometheus API, không ước lượng.
- *Lưu ý:* `screenshots/test.png` được dựng từ output `curl` thật, không phải ảnh chụp terminal. Chạy lại `check_production_ready.py` trong venv mới: PASS 12/12.

