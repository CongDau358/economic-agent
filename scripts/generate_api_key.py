"""
scripts/generate_api_key.py
Tạo API key ngẫu nhiên bảo mật và thêm vào .env

    python scripts/generate_api_key.py
    python scripts/generate_api_key.py --count 3
    python scripts/generate_api_key.py --length 48 --prefix ea
"""

import argparse
import os
import secrets
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate_key(length: int = 40, prefix: str = "ea") -> str:
    """Tạo API key dạng: ea_<random_alphanumeric>"""
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}_{random_part}" if prefix else random_part


def update_env_file(keys: list[str], env_path: Path) -> None:
    """Thêm/cập nhật API_KEYS trong .env file."""
    if not env_path.exists():
        print(f"⚠  {env_path} chưa tồn tại — tạo từ .env.example")
        example = ROOT / ".env.example"
        if example.exists():
            import shutil
            shutil.copy(example, env_path)
        else:
            env_path.write_text("")

    content = env_path.read_text(encoding="utf-8")
    keys_str = ",".join(keys)

    lines = content.splitlines()
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith("API_KEYS="):
            # Giữ các key cũ, thêm key mới
            existing = line.split("=", 1)[1].strip()
            existing_keys = [k.strip() for k in existing.split(",") if k.strip()]
            merged = existing_keys + [k for k in keys if k not in existing_keys]
            new_lines.append(f"API_KEYS={','.join(merged)}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"API_KEYS={keys_str}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate secure API keys")
    parser.add_argument("--count",  type=int, default=1,   help="Số lượng key (default: 1)")
    parser.add_argument("--length", type=int, default=40,  help="Độ dài phần random (default: 40)")
    parser.add_argument("--prefix", type=str, default="ea", help="Prefix (default: ea)")
    parser.add_argument("--no-save", action="store_true",  help="Chỉ in ra, không lưu vào .env")
    args = parser.parse_args()

    keys = [generate_key(args.length, args.prefix) for _ in range(args.count)]

    print("\n" + "─" * 50)
    print("  Generated API Keys:")
    print("─" * 50)
    for i, key in enumerate(keys, 1):
        print(f"  [{i}] {key}")
    print("─" * 50)

    if not args.no_save:
        env_path = ROOT / ".env"
        update_env_file(keys, env_path)
        print(f"\n✓ Đã lưu vào {env_path} (API_KEYS)")
        print("  Khởi động lại server để áp dụng.\n")
    else:
        print("\n  (--no-save: không lưu vào .env)\n")


if __name__ == "__main__":
    main()