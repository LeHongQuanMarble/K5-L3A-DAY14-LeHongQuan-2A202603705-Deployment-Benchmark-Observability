# Benchmark & Observability Report — Day 14

**Họ tên:** Lê Hồng Quân (MSSV 2A202603705)
**Ngày chạy:** 2026-11-25
**Môi trường:** Linux (Ubuntu), Python 3.12 venv, Docker Engine, chạy trên laptop cá nhân; stack Docker mỗi agent giới hạn 0.5 CPU / 256 MB.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Mock LLM ~120–180 ms + retrieval 20 ms; p95 500 ms cho phép dư ~2.5x so với thời gian "bình thường" nhưng vẫn chặn được request chậm (1.5 s) khi chúng vượt 5% |
| Error rate `/ask` | < 2 % | Upstream mock lỗi mặc định 1 %; 2 % cho phép dao động thống kê nhưng bắt được sự cố thật |
| Accuracy trên golden dataset | ≥ 100 % (23/23) | Dataset nhỏ, kiểm tra regression; mọi câu đều phải đúng trước khi merge |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`, 300 request mỗi mức)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.61 | 189 | 217.9 | 1676.5 | 1.33% | PASS |
| 10 | 42.85 | 191.7 | 216.9 | 1667.8 | 1.67% | PASS |
| 50 | 102.72 | 196.7 | 558.6 | 1705.7 | 1.00% | FAIL |
| 100 | 66.25 | 461.8 | 3373.8 | 3612.9 | 0.67% | FAIL |

Nguồn: `reports/load_v2_c{1,10,50,100}.json`.

**Nhận xét:** RPS tăng gần tuyến tính từ c=1 (4.6) lên c=10 (~43 req/s) vì mỗi request chủ yếu chờ I/O (sleep của mock LLM) nên song song hoá hiệu quả. Từ c=50 RPS lên ~103 nhưng p95 vượt SLO, và ở c=100 RPS **giảm** còn ~66 trong khi p50/p95 tăng vọt (461 ms / 3.4 s): agent chạy một process với thread pool của FastAPI/anyio (mặc định 40 thread cho endpoint sync), nên request xếp hàng chờ thread — đây là điểm bão hoà. Lưu ý c=1 và c=10 có p95 đẹp nhưng p99 ~1.7 s do 3 % request "slow" (+1.5 s).

### 2.2 Tail latency (concurrency 20, 300 request)

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 193.8 | 220.1 | 238 |
| 0.03 | 230.3 | 248.6 | 1688 |
| 0.1 | 296.6 | 1664.7 | 1704.1 |

Nguồn: `reports/load_v2_slow_{0,0.03,0.1}.json`.

**Nhận xét:** p99 nhạy nhất với request chậm (nhảy từ ~238 ms lên ~1.7 s ngay khi có 3 % request chậm), p95 chỉ nhảy khi tỉ lệ chậm vượt 5 % (mức 0.1 → p95 ~1.66 s), còn avg chỉ tăng nhẹ (194 → 297 ms) nên che giấu vấn đề. Vì vậy SLO phải đặt theo p95/p99 chứ không theo average.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 56.4 | 109 | 113.6 |
| Tổng cost (USD) | 0.000395 | 0.00076 | 0.00079 |
| Cost / câu đúng (USD) | 0.00039495 | 0.00003619 | 0.00003436 |
| Quality gate | PASS (chạy với `--min-accuracy 0`, chỉ để lấy baseline; thực tế không đạt 100 %) | FAIL (< 100 %) | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Thêm vào `KNOWLEDGE_BASE` entry kích hoạt bởi `jwt`, mô tả JWT là token có chữ ký, có hạn (exp) so với API key tĩnh |
| scaling-03 | cpu, memory, custom metrics | Thêm entry kích hoạt bởi `hpa`/`kubernetes`, nêu HPA scale theo CPU, memory hoặc custom metrics |

Hai entry được đặt đầu danh sách (`utils/mock_llm.py` ở cả `develop/` và `production/`) vì retrieval lấy entry khớp đầu tiên; đặt sau thì `token`/`cost` ở entry khác sẽ chặn.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:** v2 dùng retrieval nên đúng 91.3 % → 100 % so với 4.3 % của v1, tốn thêm token (~113 vs ~56 token/câu, vì thêm ngữ cảnh) và ~20 ms retrieval. Cost tuyệt đối của v2 cao hơn (~2x) nhưng cost / câu đúng rẻ hơn ~11x ($0.0000344 vs $0.000395), nên "cost / câu đúng" mới là thước đo hợp lý để so hai phiên bản.

**Quality gate trong CI:** `run_eval.py` trả exit code khác 0 khi accuracy < `--min-accuracy` hoặc có câu regression so với `--baseline`. Trong job CI (GitHub Actions) chỉ cần bước `python eval/run_eval.py --url $AGENT_URL --min-accuracy 1.0 --baseline reports/eval_v2.json`; bước fail thì job fail, và bật branch protection "require status checks" sẽ chặn merge.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải — `screenshots/grafana-dashboard.png`
- [x] Một trace chậm trong Jaeger — `screenshots/jaeger-slow-trace.png`
- [x] Một trace lỗi trong Jaeger — `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với ≥ 2 alert firing — `screenshots/prometheus-alert-firing.png` (AgentHighErrorRate, AgentHighLatencyP95 và LLMCostBurnRateHigh cùng firing)

### 4.2 Thí nghiệm "phá hệ thống"

Mình chạy gộp A + B + D một lần (khó tách riêng vì mỗi lần dựng lại stack mất nhiều phút): đặt `MOCK_ERROR_RATE=0.2 MOCK_SLOW_RATE=0.3`, recreate 3 agent, bật Locust 100 user, rồi `docker pause` instance 3. Thời gian đo từ lúc chạy Locust.

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | AgentHighErrorRate | ~71 s (pending sau ~10 s, `for: 1m`) | Error rate (19.28 %) + Requests/s theo status code (503) |
| B | `MOCK_SLOW_RATE=0.3` | AgentHighLatencyP95 | ~132 s (`for: 2m`) | Latency p50/p95/p99 (p95 ≈ 1.9 s) |
| C | `LLM_MODEL=mock-llm-large` | Không chạy thí nghiệm riêng. Ghi nhận: LLMCostBurnRateHigh đã firing sẵn ở lần chạy này vì tải benchmark ~60 req/s đã tốn ~$8/giờ, vượt ngưỡng $2/giờ | — | Cost burn rate / LLM cost (1h) |
| D | `docker pause` 1 instance | Không thấy AgentInstanceDown firing trong khoảng quan sát; panel "Instances up" giảm còn 2 (scrape instance bị pause bị timeout, nhưng alert chưa kịp chuyển pending/firing như dự kiến) | không đo được | Instances up |
| E | `AGENT_VERSION=v1` | Không chạy | — | — |

(Alert LLMCostBurnRateHigh firing từ ~10 s đầu vì rate 5 phút còn mang tải của hai lần benchmark scale trước đó.)

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?** v1 vẫn nhanh, không lỗi, nhưng trả lời sai nhiều hơn (accuracy 4 % so với 91–100 %), nên alert hạ tầng không thấy. Cần giám sát chất lượng: chạy eval golden dataset định kỳ (canary/synthetic) và alert khi accuracy giảm, theo dõi metric nghiệp vụ như retrieval hit ratio, tỉ lệ câu trả lời mặc định/"không biết", feedback người dùng; kèm panel "Phiên bản đang chạy" để biết version nào đang phục vụ.

### 4.3 Debug bằng trace

Trace chậm nhất tìm được:

- `trace_id`: `4a9feb77dc514bd4ce5524338e857674`
- Tổng thời gian: 1713.5 ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1697 ms, ~99 %); `agent.retrieve_context` chỉ 14 ms
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T08:03:53.185665+00:00", "level": "INFO", "service": "observable-agent", "instance": "5bdc4d3b72ad", "event": "llm_call", "trace_id": "4a9feb77dc514bd4ce5524338e857674", "span_id": "d697b09bc74fc3a8", "request_id": "b2542054dae4", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 95, "output_tokens": 55, "cost_usd": 4.7e-05, "llm_ms": 1696.5}
{"ts": "2026-11-25T08:03:53.185944+00:00", "level": "INFO", "service": "observable-agent", "instance": "5bdc4d3b72ad", "event": "http_request", "trace_id": "4a9feb77dc514bd4ce5524338e857674", "span_id": "d697b09bc74fc3a8", "request_id": "b2542054dae4", "method": "POST", "route": "/ask", "status": 200, "ms": 1713.1}
```

Trace lỗi: `6e6371b7e7f29274019425759a2515e3` (875 ms, `POST /ask` trả 503) khớp dòng log:

```json
{"ts": "2026-11-25T08:03:49.434738+00:00", "level": "INFO", "service": "observable-agent", "instance": "5bdc4d3b72ad", "event": "llm_error", "trace_id": "6e6371b7e7f29274019425759a2515e3", "span_id": "746a4e9a03fce208", "request_id": "357a60b1791e", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
{"ts": "2026-11-25T08:03:49.435322+00:00", "level": "INFO", "service": "observable-agent", "instance": "5bdc4d3b72ad", "event": "http_request", "trace_id": "6e6371b7e7f29274019425759a2515e3", "span_id": "746a4e9a03fce208", "request_id": "357a60b1791e", "method": "POST", "route": "/ask", "status": 503, "ms": 874.7}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures (lỗi / tổng) |
|---|---|---|---|---|---|
| 1 | 65.8 | 190 | 230 | 1700 | 66 / 7838 |
| 3 | 66.4 | 190 | 220 | 1700 | 77 / 7903 |

Nguồn: `benchmark-results/scale_1_stats.csv`, `scale_3_stats.csv`.

**Giải thích kết quả:** Scale 1 → 3 instance **không** đổi RPS và p95, vì Locust dùng `wait_time = between(0.5, 2)` nên 100 user chỉ tạo ~66 req/s (bị giới hạn bởi tải sinh ra, không phải bởi năng lực agent), và 1 instance 0.5 CPU vẫn xử lý được I/O-bound mock. Nút thắt nằm ở tail 1.7 s của 3 % request "slow" của mock LLM và tỉ lệ lỗi upstream ~1 % — thứ không giảm khi thêm instance. Muốn thấy lợi ích của scale cần tải cao hơn hoặc giảm `wait_time`.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. SLO phải đặt theo p95/p99; average che giấu tail latency (avg 194 → 297 ms trong khi p99 nhảy 238 ms → 1.7 s).
  2. So sánh hai phiên bản agent phải nhìn cả chất lượng lẫn chi phí: "cost / câu đúng" cho kết luận khác "cost / câu"; eval có exit code làm quality gate cho CI.
  3. Metrics (Grafana/Prometheus) cho biết *có* vấn đề, trace (Jaeger) cho biết *ở đâu*, log JSON có `trace_id` nối hai thứ lại; nhưng sự cố chất lượng (v1) cần giám sát riêng.
- Nếu đưa agent này lên production thật, mình sẽ thêm: alert accuracy/eval định kỳ, tỉ lệ cache/retrieval hit, alert theo ngân sách tích luỹ ngày, alert saturation (in-flight/thread pool), và sửa rule `AgentInstanceDown` để bắt cả trường hợp target treo (pause) thay vì chỉ `up == 0`.
