"""自检：验证 .env 里的 CBG_COOKIE 是否可用。

用法：python tools/check_cookie.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yyscbg.cbg import CbgClient, CbgError, SessionTimeout  # noqa: E402
from yyscbg.config import cookie, load_dotenv  # noqa: E402

load_dotenv()
value = cookie()
if not value:
    print("未配置 CBG_COOKIE：请复制 .env.example 为 .env 并填入浏览器里的 Cookie")
    raise SystemExit(1)

print(f"Cookie 长度 {len(value)}，正在请求第 1 页…")
try:
    payload = CbgClient(value).list_page(1)
except SessionTimeout as exc:
    print(f"登录态失效：{exc}")
    raise SystemExit(2)
except CbgError as exc:
    print(f"请求失败：{exc}")
    raise SystemExit(2)

items = payload.get("result") or []
print(f"可用，共返回 {len(items)} 条；总分页 {payload.get('pager', {}).get('total_pages')} 页")
if items:
    first = items[0]
    print(f"样例：{first.get('price', 0) / 100:.0f} 元 · {first.get('server_name')} · {first.get('highlights', [])[:3]}")
