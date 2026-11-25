"""Test bản deploy trên Render: /ask có key -> 200, rate limit -> 429.

Chạy:  AGENT_KEY=<key> python3 utils/test_deployed.py
Key đọc từ biến môi trường, không bao giờ được in ra hay ghi vào file.
Kết quả thật được ghi vào screenshots/test.png và reports/deployed_test.log.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("BASE_URL", "https://agent-audl.onrender.com")
KEY = os.environ.get("AGENT_KEY")
if not KEY:
    sys.exit("Thiếu AGENT_KEY (đặt: AGENT_KEY=<key> python3 utils/test_deployed.py)")


def call(path, method="GET", key=None, body=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-API-Key"] = key
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


lines = []


def log(s=""):
    print(s)
    lines.append(s)


body = {"user_id": "test", "question": "Hello"}
log(f"$ curl {BASE}/health")
s, t = call("/health"); log(f"HTTP {s}  {t[:80]}")
log(f"$ curl {BASE}/ready")
s, t = call("/ready"); log(f"HTTP {s}  {t[:80]}")
log("$ curl -X POST /ask   (không có API key)")
s, t = call("/ask", "POST", None, body); log(f"HTTP {s}")
log("$ curl -X POST /ask -H 'X-API-Key: ***'")
s, t = call("/ask", "POST", KEY, body); log(f"HTTP {s}  {t[:80]}")
ok_auth = s == 200

log("$ 25 request liên tiếp với X-API-Key: ***")
codes = []
for _ in range(25):
    codes.append(call("/ask", "POST", KEY, {"user_id": "ratelimit", "question": "test"})[0])
log("codes: " + " ".join(map(str, codes)))
log(f"200: {codes.count(200)}  429: {codes.count(429)}")
ok_rl = 429 in codes
log(f"KẾT QUẢ: auth 200 = {ok_auth}, rate limit 429 = {ok_rl}")

os.makedirs("reports", exist_ok=True)
text = "\n".join(lines)
assert KEY not in text
with open("reports/deployed_test.log", "w") as f:
    f.write(text + "\n")

try:
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 18)
    img = Image.new("RGB", (1100, 40 + 26 * len(lines)), "#1e1e1e")
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        d.text((20, 20 + 26 * i), l, fill="#d4d4d4", font=font)
    img.save("screenshots/test.png")
    print("Đã ghi screenshots/test.png và reports/deployed_test.log")
except Exception as e:  # PIL là tuỳ chọn
    print("Không tạo được ảnh:", e)
