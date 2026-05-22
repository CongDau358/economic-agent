"""
scripts/clear_cache.py
Xóa toàn bộ cache.

    python scripts/clear_cache.py
"""

import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

async def main():
    from backend.services.cache import get_cache
    cache = get_cache()
    await cache.clear()
    print("✓ Cache đã được xóa.")

asyncio.run(main())