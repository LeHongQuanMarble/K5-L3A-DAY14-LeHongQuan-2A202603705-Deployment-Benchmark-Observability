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
`AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, `ENVIRONMENT`; `PORT` do nền tảng cấp.

## Lệnh kiểm tra sau khi deploy
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```
