"""取数流程：全量列表（价格分桶枚举）+ 候选详情精算 + piko 回传导入。"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterable

from . import store
from .cbg import CbgClient, CbgError
from .config import CONCURRENCY, DEFAULT_PVE_HEROES, REQUEST_INTERVAL
from .parse import parse_listing
from .relics import account_metrics

PAGE_SIZE = 15
MAX_PAGES = 100  # 服务端单次查询上限：100 页 × 15 条 = 1500 条


def _pages_for(client: CbgClient, lo: int, hi: int) -> int:
    payload = client.list_page(1, price_min=lo, price_max=hi)
    return int((payload.get("pager") or {}).get("total_pages") or 0)


def build_buckets(client: CbgClient, lo: int, hi: int, progress: Callable[[str], None] = print) -> list[tuple[int, int, int]]:
    """把价格区间切成若干「不超过 100 页」的桶，返回 (lo, hi, pages)。"""
    buckets: list[tuple[int, int, int]] = []
    stack = [(lo, hi)]
    while stack:
        left, right = stack.pop()
        try:
            pages = _pages_for(client, left, right)
        except CbgError as exc:
            progress(f"  区间 {left/100:.0f}~{right/100:.0f} 元查询失败：{exc}")
            continue
        if pages >= MAX_PAGES and right - left > 1:
            mid = (left + right) // 2
            stack.append((mid + 1, right))
            stack.append((left, mid))
        else:
            buckets.append((left, right, pages))
    buckets.sort()
    return buckets


def fetch_all(
    client: CbgClient,
    lo_yuan: float = 0,
    hi_yuan: float = 1_000_000,
    workers: int = CONCURRENCY,
    progress: Callable[[str], None] = print,
) -> list[dict[str, Any]]:
    """抓取价格区间内的全部在售账号（列表级字段）。"""
    lo, hi = int(lo_yuan * 100), int(hi_yuan * 100)
    progress(f"枚举价格分桶：{lo_yuan:,.0f} ~ {hi_yuan:,.0f} 元")
    buckets = build_buckets(client, lo, hi, progress)
    total_pages = sum(max(1, pages) for _, _, pages in buckets)
    progress(f"共 {len(buckets)} 个桶 / {total_pages} 页（约 {total_pages * PAGE_SIZE} 条上限）")

    tasks = [(left, right, page) for left, right, pages in buckets for page in range(1, max(1, pages) + 1)]
    rows: dict[str, dict[str, Any]] = {}

    def work(task: tuple[int, int, int]) -> list[dict[str, Any]]:
        left, right, page = task
        for attempt in range(3):
            try:
                payload = client.list_page(page, price_min=left, price_max=right)
                return [parse_listing(item) for item in payload.get("result") or []]
            except CbgError:
                time.sleep(1 + attempt)
        return []

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(work, task): task for task in tasks}
        for future in as_completed(futures):
            for row in future.result():
                rows[row["eid"]] = row
            done += 1
            if done % 50 == 0 or done == len(tasks):
                progress(f"  列表进度 {done}/{len(tasks)}，已收 {len(rows)} 条")
            time.sleep(REQUEST_INTERVAL / max(1, workers))
    return list(rows.values())


def save_listings(rows: Iterable[dict[str, Any]], mark_stale: bool = True) -> int:
    conn = store.connect()
    try:
        rows = list(rows)
        run_id = store.start_run(conn, "list")
        count = store.upsert_listings(conn, rows)
        if mark_stale and count:
            store.mark_inactive(conn, {row["eid"] for row in rows if row.get("eid")})
        store.finish_run(conn, run_id, count)
        return count
    finally:
        conn.close()


def compute_detail(client: CbgClient, eid: str, serverid: Any, hero: str | None = None) -> dict[str, Any]:
    desc = client.equip_desc(serverid, eid)
    metrics = account_metrics(desc)
    return metrics


def compute_details(
    client: CbgClient,
    targets: list[tuple[str, Any]],
    hero: str | None = None,
    progress: Callable[[str], None] = print,
) -> int:
    conn = store.connect()
    done = 0
    try:
        for eid, serverid in targets:
            try:
                metrics = compute_detail(client, eid, serverid, hero)
                store.save_metrics(conn, eid, metrics)
                done += 1
                progress(f"  精算 {eid} 完成（{done}/{len(targets)}）")
            except CbgError as exc:
                progress(f"  精算 {eid} 失败：{exc}")
    finally:
        conn.close()
    return done


def pick_targets(limit: int = 50, **filters: Any) -> list[tuple[str, Any]]:
    conn = store.connect()
    try:
        result = store.query(conn, filters, sort="speed", desc=True, limit=limit)
        return [(row["eid"], row["serverid"]) for row in result["items"]]
    finally:
        conn.close()


# ------------------------------------------------------------------ piko 模式
def import_piko(path: Path) -> int:
    """导入 piko 回传的 JSON（支持原始 result 数组或已标准化记录）。"""
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    rows: list[dict[str, Any]] = []
    for file in files:
        payload = json.loads(file.read_text(encoding="utf-8"))
        items = payload.get("rows") if isinstance(payload, dict) else payload
        for item in items or []:
            if not isinstance(item, dict):
                continue
            row = parse_listing(item) if "highlights" in item else item
            row.setdefault("eid", item.get("eid", ""))
            if row["eid"]:
                rows.append(row)
    return save_listings(rows, mark_stale=False)


def import_piko_details(path: Path) -> int:
    """导入账号明细并本地精算。

    支持三种文件：
      * 浏览器直接下载的原始详情 `cbg_<订单号>.json`（外层含 equip_desc）
      * `{"eid": ..., "desc": {...}}`
      * `{"eid": ..., "inventory": {...}, "heroes": {...}}`
    """
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    conn = store.connect()
    saved = 0
    try:
        for file in files:
            payload = json.loads(file.read_text(encoding="utf-8"))
            eid = payload.get("eid")
            desc = payload.get("desc")
            if desc is None and "equip_desc" in payload:
                desc = payload["equip_desc"]
                if isinstance(desc, str):
                    desc = json.loads(desc)
            if desc is None and "inventory" in payload:
                desc = payload
            if not eid:
                # 浏览器下载文件名形如 cbg_202611202001616-16-4S0QIIC2VYCKE.json
                stem = file.stem
                eid = stem[4:] if stem.startswith("cbg_") else stem
            if not eid or not isinstance(desc, dict):
                continue
            store.save_metrics(conn, eid, account_metrics(desc))
            saved += 1
    finally:
        conn.close()
    return saved
