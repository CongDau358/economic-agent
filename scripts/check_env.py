"""
scripts/check_env.py
Kiểm tra .env trước khi chạy server.

    python scripts/check_env.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

REQUIRED = ["OPENAI_API_KEY"]
RECOMMENDED = ["FRED_API_KEY", "API_KEYS", "REDIS_URL"]

errors, warnings = [], []

for key in REQUIRED:
    val = os.getenv(key, "")
    if not val or val.startswith("sk-your") or val == "sk-...":
        errors.append(f"  ✗ {key} — chưa được cấu hình")
    else:
        print(f"  ✓ {key}")

for key in RECOMMENDED:
    if not os.getenv(key):
        warnings.append(f"  ⚠ {key} — tuỳ chọn nhưng nên có")
    else:
        print(f"  ✓ {key}")

if warnings:
    print("\nWarnings:")
    for w in warnings: print(w)

if errors:
    print("\nErrors:")
    for e in errors: print(e)
    print("\n✗ Cấu hình .env chưa đầy đủ. Copy .env.example → .env và điền giá trị.")
    sys.exit(1)
else:
    print("\n✓ Cấu hình .env hợp lệ.")