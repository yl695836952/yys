"""藏宝阁接口客户端（纯标准库实现，带登录 Cookie）。

已实测的接口：
  POST /cgi-bin/recommend.py?client_type=h5&act=recommd_by_role
       表单参数：page（1 起）、search_type=role、price_min/price_max（单位「分」）
                可选 order_by / order_direction（服务端实测会忽略，保持默认排序）
       返回：{status:1, result:[...15 条...], pager:{cur_page,total_pages}}
       注意：单页固定 15 条，单次查询最多 100 页（1500 条），需要按价格分桶枚举。
  GET  /cgi/api/get_equip_desc?serverid=<id>&ordersn=<eid>
       返回：{version, equip_desc: "<账号全量 JSON 字符串>"}（约 8MB）
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://yys.cbg.163.com"
LIST_PATH = "/cgi-bin/recommend.py?client_type=h5&act=recommd_by_role"
DESC_PATH = "/cgi/api/get_equip_desc"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class CbgError(RuntimeError):
    pass


class SessionTimeout(CbgError):
    """登录态失效，需要重新提供 Cookie。"""


class CbgClient:
    def __init__(self, cookie: str, timeout: float = 25.0, retries: int = 3):
        if not cookie:
            raise CbgError("缺少 Cookie：请在 .env 里配置 CBG_COOKIE（需包含 SID），或用 piko 模式取数")
        self.cookie = cookie
        self.timeout = timeout
        self.retries = retries

    # ------------------------------------------------------------------ 底层
    def _headers(self) -> dict:
        return {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": f"{BASE}/cgi/mweb/pl?view_loc=equip_list",
            "Origin": BASE,
            "Cookie": self.cookie,
        }

    def _open(self, url: str, data: bytes | None = None) -> bytes:
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(url, data=data, headers=self._headers())
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                last = exc
                if exc.code in (403, 429, 500, 502, 503):
                    time.sleep(1.5 * (attempt + 1) + random.random())
                    continue
                raise CbgError(f"HTTP {exc.code}: {url}") from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last = exc
                time.sleep(1.0 * (attempt + 1) + random.random())
        raise CbgError(f"请求失败：{url}（{last}）")

    @staticmethod
    def _check(payload: dict) -> dict:
        status = payload.get("status")
        if status == 1:
            return payload
        code = payload.get("status_code") or ""
        if code == "SESSION_TIMEOUT":
            raise SessionTimeout("登录态失效（SESSION_TIMEOUT），请更新 .env 里的 CBG_COOKIE")
        raise CbgError(f"接口返回异常 status={status} status_code={code} msg={payload.get('msg')}")

    # ------------------------------------------------------------------ 列表
    def list_page(
        self,
        page: int = 1,
        price_min: int | None = None,
        price_max: int | None = None,
        order_by: str | None = None,
        order_direction: str | None = None,
    ) -> dict:
        """取列表一页（15 条）。价格单位为「分」。"""
        form = {"page": page, "search_type": "role"}
        if price_min is not None:
            form["price_min"] = price_min
        if price_max is not None:
            form["price_max"] = price_max
        if order_by:
            form["order_by"] = order_by
        if order_direction:
            form["order_direction"] = order_direction
        body = urllib.parse.urlencode(form).encode()
        raw = self._open(BASE + LIST_PATH, body)
        return self._check(json.loads(raw.decode("utf-8")))

    # ------------------------------------------------------------------ 详情
    def equip_desc(self, serverid: int | str, ordersn: str) -> dict:
        """取账号全量明细（约 8MB，含全量御魂与式神基础面板）。"""
        url = f"{BASE}{DESC_PATH}?serverid={serverid}&ordersn={urllib.parse.quote(str(ordersn))}"
        raw = self._open(url)
        outer = json.loads(raw.decode("utf-8"))
        desc = outer.get("equip_desc")
        if desc is None:
            raise CbgError(f"详情缺少 equip_desc：{ordersn}")
        if isinstance(desc, str):
            desc = json.loads(desc)
        if not isinstance(desc, dict):
            raise CbgError(f"详情 equip_desc 结构异常：{ordersn}")
        return desc
