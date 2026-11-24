"""命令行入口：python -m yyscbg <命令>"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import store
from .cbg import CbgClient, CbgError, SessionTimeout
from .config import OMA_SUITS, cookie, load_dotenv
from .fetch import (
    compute_details,
    fetch_all,
    import_piko,
    import_piko_details,
    pick_targets,
    run_detail_pipeline,
    save_listings,
)
from .server import serve


def _client() -> CbgClient:
    load_dotenv()
    return CbgClient(cookie())


def cmd_fetch_list(args: argparse.Namespace) -> int:
    client = _client()
    rows = fetch_all(client, lo_yuan=args.min_price, hi_yuan=args.max_price, workers=args.workers)
    count = save_listings(rows)
    print(f"已入库 {count} 条（去重后）")
    return 0


def cmd_fetch_detail(args: argparse.Namespace) -> int:
    client = _client()
    oma = _oma_list(args.oma)
    if args.eids:
        conn = store.connect()
        try:
            targets = []
            for eid in args.eids.split(","):
                listing = store.get_listing(conn, eid.strip())
                if listing:
                    targets.append((listing["eid"], listing["serverid"]))
        finally:
            conn.close()
    else:
        filters = {
            "minSpeed": args.min_speed,
            "minLucky": args.min_lucky,
            "minPvp": args.min_pvp,
            "minPrice": args.min_price,
            "maxPrice": args.max_price,
            "minPanel": args.min_panel,
            "panelSuit": args.panel_suit,
        }
        targets = pick_targets(args.limit, **filters)
    if not targets:
        print("没有匹配的账号，先用 fetch-list 抓一轮，或放宽筛选条件")
        return 1
    print(f"将对 {len(targets)} 个账号做详情精算（每个约 8MB 数据，首领组合 {'/'.join(oma)}）")
    done = compute_details(client, targets, oma_list=oma)
    print(f"完成 {done} 个")
    return 0


def cmd_fetch_details_all(args: argparse.Namespace) -> int:
    oma = _oma_list(args.oma)
    result = run_detail_pipeline(
        _client,
        oma,
        download_workers=args.download_workers,
        batch_size=args.batch,
        limit=args.limit,
        mode=args.mode,
    )
    print(f"结束：成功 {result['done']} / 失败 {result['failed']} / 计划 {result['total']}")
    return 0


def _oma_list(value: str | None) -> list[str]:
    if not value:
        return list(OMA_SUITS)
    names = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [name for name in names if name not in OMA_SUITS]
    if unknown:
        raise SystemExit(f"未知首领御魂：{'、'.join(unknown)}（可选：{'、'.join(OMA_SUITS)}）")
    return names


def cmd_import_piko(args: argparse.Namespace) -> int:
    count = import_piko(Path(args.path))
    print(f"从 piko 数据导入列表 {count} 条")
    return 0


def cmd_import_piko_details(args: argparse.Namespace) -> int:
    count = import_piko_details(Path(args.path))
    print(f"从 piko 数据精算入库 {count} 个账号")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    conn = store.connect()
    try:
        print(store.stats(conn))
    finally:
        conn.close()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    serve()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="yyscbg", description="阴阳师藏宝阁 PVP/PVE 分析工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch-list", help="全量抓取在售账号（列表级字段）")
    p.add_argument("--min-price", type=float, default=0)
    p.add_argument("--max-price", type=float, default=1_000_000)
    p.add_argument("--workers", type=int, default=4)
    p.set_defaults(func=cmd_fetch_list)

    p = sub.add_parser("fetch-detail", help="对候选账号抓详情并计算 PVE/PVP 指标")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--eids", default="")
    p.add_argument("--min-speed", type=float, default=None)
    p.add_argument("--min-lucky", type=float, default=None)
    p.add_argument("--min-pvp", type=float, default=None)
    p.add_argument("--min-price", type=float, default=None)
    p.add_argument("--max-price", type=float, default=None)
    p.add_argument("--min-panel", type=float, default=None)
    p.add_argument("--panel-suit", default="狂骨")
    p.add_argument("--oma", default="", help="首领御魂，逗号分隔；默认全部（土蜘蛛,荒骷髅,鬼灵歌伎）")
    p.set_defaults(func=cmd_fetch_detail)

    p = sub.add_parser("fetch-details-all", help="全量/增量精算：把在售账号全部算一遍面板")
    p.add_argument("--oma", default="荒骷髅", help="首轮建议只算「荒骷髅」，快约 3 倍")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--download-workers", type=int, default=6)
    p.add_argument("--batch", type=int, default=60)
    p.add_argument("--mode", choices=["auto", "missing", "redo"], default="auto",
                   help="auto=增量（含补算新组合）；missing=只算没算过的；redo=全部重算")
    p.set_defaults(func=cmd_fetch_details_all)

    p = sub.add_parser("import-piko", help="导入 piko 浏览器模式回传的列表 JSON")
    p.add_argument("path")
    p.set_defaults(func=cmd_import_piko)

    p = sub.add_parser("import-piko-details", help="导入 piko 回传的账号明细并本地精算")
    p.add_argument("path")
    p.set_defaults(func=cmd_import_piko_details)

    p = sub.add_parser("stats", help="查看本地数据概况")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("serve", help="启动本地筛选页面")
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SessionTimeout as exc:
        print(f"[登录态失效] {exc}")
        return 2
    except CbgError as exc:
        print(f"[藏宝阁接口错误] {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
