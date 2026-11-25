# DEPLOYMENT

## Trạng thái: ĐÃ deploy lên Render (gói Free)

- URL public: https://agent-audl.onrender.com
- Nền tảng: Render Blueprint (`06-lab-complete/render.yaml`) gồm web service `agent` (Docker, Free) + Key Value `agent-redis` (Free).
- Railway không dùng được vì trial của tài khoản đã hết hạn.
- Kiểm tra: `/health` = 200, `/ready` = 200, `POST /ask` không key = 401.
- Lưu ý: gói Free ngủ sau ~15 phút không có request, lần gọi đầu có thể chậm 50 giây trở lên.

## Đã sẵn sàng để deploy
- `06-lab-complete/railway.toml`: builder `DOCKERFILE`, `healthcheckPath = "/health"`.
- `06-lab-complete/render.yaml`: web service docker + Redis (`fromService` cho `REDIS_URL`), `AGENT_API_KEY` dùng `generateValue: true`.
- `python check_production_ready.py` → `PASS 12/12` (xem MISSION_ANSWERS.md).

## Các bước deploy (Railway)
```bash
cd 06-lab-complete
railway login && railway init
railway add --database redis          # hoặc tạo Redis trên dashboard
railway variables set AGENT_API_KEY=<key-bí-mật> REDIS_URL=<url-redis> RATE_LIMIT_PER_MINUTE=20 DAILY_BUDGET_USD=5 ENVIRONMENT=production
railway up && railway domain
```

## Biến môi trường cần đặt trên nền tảng
## Environment Variables Set (trên Render)
| Biến | Nguồn |
| --- | --- |
| `AGENT_API_KEY` | Render tự sinh (`generateValue: true`), không commit vào repo |
| `REDIS_URL` | Nối tự động từ Key Value `agent-redis` (`fromService`) |
| `RATE_LIMIT_PER_MINUTE` | `20` (khai báo trong `render.yaml`) |
| `DAILY_BUDGET_USD` | `5.0` (khai báo trong `render.yaml`) |
| `ENVIRONMENT` | `production` (khai báo trong `render.yaml`) |
| `PORT` | Do Render cấp |

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)

## Lệnh kiểm tra sau khi deploy
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```

## Kiểm thử bản deploy có API key
`utils/test_deployed.py` chạy `/health`, `/ready`, `/ask` không key (401), `/ask` có key (200) và 25 request liên tiếp để quan sát 429. Key lấy từ biến môi trường `AGENT_KEY`, không ghi vào file hay log:
```bash
AGENT_KEY=<AGENT_API_KEY trên Render> python3 utils/test_deployed.py
```
Kết quả ghi vào `reports/deployed_test.log` và `screenshots/test.png`.

### Kết quả chạy thật trên https://agent-audl.onrender.com
| Kiểm tra | Kết quả |
| --- | --- |
| `GET /health` | 200 |
| `GET /ready` | 200 |
| `POST /ask` không API key | 401 |
| `POST /ask` có `X-API-Key` | 200 |
| 25 request liên tiếp (`RATE_LIMIT_PER_MINUTE=20`) | 19 × 200, rồi 6 × 429 |

Log đầy đủ: `reports/deployed_test.log`; ảnh: `screenshots/test.png` (render từ output thật, key được che bằng `***`).
