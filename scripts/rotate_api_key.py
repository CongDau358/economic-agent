"""
scripts/rotate_api_key.py
Rotate (thêm mới + vô hiệu hoá cũ) API keys trong .env.

    python scripts/rotate_api_key.py                     # rotate toàn bộ
    python scripts/rotate_api_key.py --keep-old          # thêm mới, giữ cũ
    python scripts/rotate_api_key.py --revoke ea_abc123  # xoá 1 key cụ thể
    python scripts/rotate_api_key.py --list              # liệt kê keys hiện tại
"""

from __future__ import annotations

import argparse
import os
import secrets
import string
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def _read_keys() -> list[str]:
    if not ENV_PATH.exists():
        return []
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("API_KEYS="):
            raw = line.split("=", 1)[1].strip()
            return [k.strip() for k in raw.split(",") if k.strip()]
    return []


def _write_keys(keys: list[str]) -> None:
    if not ENV_PATH.exists():
        print(f"⚠  {ENV_PATH} không tồn tại — tạo mới")
        ENV_PATH.write_text(f"API_KEYS={','.join(keys)}\n", encoding="utf-8")
        return

    lines     = ENV_PATH.read_text(encoding="utf-8").splitlines()
    new_lines = []
    written   = False

    for line in lines:
        if line.startswith("API_KEYS="):
            new_lines.append(f"API_KEYS={','.join(keys)}")
            written = True
        else:
            new_lines.append(line)

    if not written:
        new_lines.append(f"API_KEYS={','.join(keys)}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _gen_key(prefix: str = "ea", length: int = 40) -> str:
    alphabet = string.ascii_letters + string.digits
    return f"{prefix}_{''.join(secrets.choice(alphabet) for _ in range(length))}"


def cmd_list():
    keys = _read_keys()
    if not keys:
        print("  (Không có API key nào được cấu hình)")
        return
    print(f"\n  API Keys hiện tại ({len(keys)}):")
    for i, k in enumerate(keys, 1):
        masked = k[:6] + "..." + k[-4:]
        print(f"  [{i}] {masked}  (length={len(k)})")
    print()


def cmd_rotate(keep_old: bool = False):
    old_keys = _read_keys()
    new_key  = _gen_key()

    if keep_old:
        keys = old_keys + [new_key]
        print(f"\n  ✓ Thêm key mới (giữ {len(old_keys)} key cũ):")
    else:
        keys = [new_key]
        if old_keys:
            print(f"\n  ⚠  Đã vô hiệu hoá {len(old_keys)} key cũ")

    _write_keys(keys)
    print(f"  ✓ Key mới: {new_key}")
    print(f"  ✓ Đã lưu vào {ENV_PATH}\n")
    print("  ⚠  Khởi động lại server để áp dụng thay đổi\n")


def cmd_revoke(key: str):
    keys = _read_keys()
    if key not in keys:
        print(f"  ✗ Key '{key}' không tìm thấy trong .env")
        return

    keys.remove(key)
    _write_keys(keys)
    print(f"  ✓ Đã xoá key: {key[:6]}...{key[-4:]}")
    print(f"  ✓ Còn lại {len(keys)} key")
    print("  ⚠  Khởi động lại server để áp dụng\n")


def main():
    parser = argparse.ArgumentParser(description="Rotate API keys")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--list",     action="store_true", help="Liệt kê keys hiện tại")
    group.add_argument("--keep-old", action="store_true", help="Thêm key mới, giữ key cũ")
    group.add_argument("--revoke",   metavar="KEY",       help="Xoá 1 key cụ thể")
    args = parser.parse_args()

    print(f"\n{'─'*50}")
    print("  Economic Agent — API Key Manager")
    print(f"{'─'*50}")

    if args.list:
        cmd_list()
    elif args.revoke:
        cmd_revoke(args.revoke)
    else:
        cmd_rotate(keep_old=args.keep_old)


if __name__ == "__main__":
    main()