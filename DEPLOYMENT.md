# DEPLOYMENT

## Trạng thái: CHƯA deploy lên cloud

Môi trường làm bài không có tài khoản/đăng nhập Railway hoặc Render (cần `railway login` hoặc kết nối GitHub trên Render) nên **chưa có URL public**. Mình không điền URL giả. Phần này (CP6, ảnh `dashboard.png`, `running.png`, `test.png`) cần hoàn thành bằng tài khoản của chủ repo.

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
`AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, `ENVIRONMENT`; `PORT` do nền tảng cấp.

## Lệnh kiểm tra sau khi deploy
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```
