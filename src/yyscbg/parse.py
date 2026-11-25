"""列表接口字段标准化：把藏宝阁的 highlights 字符串拆成可筛选的数值。"""

from __future__ import annotations

import re
from typing import Any

_RE_SCATTER = re.compile(r"散件一速\s*([\d.]+)")
_RE_LUCKY = re.compile(r"招财一速\s*([\d.]+)")
_RE_HEAD_TAIL = re.compile(r"(\d+)\s*头\s*(\d+)\s*尾")
_RE_HEAD_SPEED = re.compile(r"头速(?:度)?(?:均值)?\s*([\d.]+)")
_RE_PVP = re.compile(r"斗技\s*(\d+)")
_RE_SSR = re.compile(r"SSR\s*(\d+)")
_RE_SIX_STAR = re.compile(r"六星式神\s*(\d+)")
_RE_SIGN = re.compile(r"签到\s*(\d+)\s*天")
_RE_FENGZI = re.compile(r"([\d.]+)\s*万?风姿度")
_RE_SOUL_JADE = re.compile(r"(\d+)\s*枚魂玉")
_RE_DAMO = re.compile(r"(\d+)\s*个御行达摩")

# highlights 里除四类数值外，其余都是荣誉/资产标签，原样保留供前端展示与筛选。
_NUMERIC_MARKERS = ("散件一速", "招财一速", "头速度", "头速均值", "斗技")


def _first_float(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    return float(match.group(1)) if match else None


def _first_int(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(text)
    return int(match.group(1)) if match else None


def parse_listing(item: dict[str, Any]) -> dict[str, Any]:
    """把列表接口的一条 result 转成扁平记录（同时兼容 piko 脚本精简过的字段名）。"""
    highlights = [str(x) for x in (item.get("highlights") or [])]
    joined = " ".join(highlights)
    summary = str(item.get("desc_sumup_short") or "")
    diy = str(item.get("diy_desc") or "")

    head_cnt = tail_cnt = None
    match = _RE_HEAD_TAIL.search(joined)
    if match:
        head_cnt, tail_cnt = int(match.group(1)), int(match.group(2))

    tags = [
        text
        for text in highlights
        if not any(marker in text for marker in _NUMERIC_MARKERS)
        and not _RE_HEAD_TAIL.search(text)
    ]

    heroes = []
    raw_heroes = (item.get("other_info") or {}).get("top_heros") or item.get("top_heros") or []
    for hero in raw_heroes:
        heroes.append(
            {
                "name": hero.get("name"),
                "heroId": hero.get("heroId"),
                "speed": hero.get("speed", hero.get("add_speed_not_display")),
                "crit": hero.get("crit", hero.get("strike_not_display")),
                "critDamage": hero.get("critDamage", hero.get("strike_damage_not_display")),
            }
        )

    price_fen = item.get("price") or 0
    # 详情接口要的是 game_ordersn，列表里的 eid 传过去会返回「物品不存在」。
    ordersn = item.get("game_ordersn") or item.get("ordersn") or item.get("eid") or ""
    return {
        "eid": item.get("eid") or "",
        "ordersn": ordersn,
        "serverid": item.get("serverid"),
        "price": round(price_fen / 100, 2),
        "area": item.get("area_name") or item.get("area") or "",
        "server": item.get("server_name") or item.get("server") or "",
        "platform": item.get("platform_desc") or item.get("platform") or "",
        "level": item.get("equip_level") or item.get("level") or 0,
        "status": item.get("status"),
        "collect": item.get("collect_num") or item.get("collect") or 0,
        "selling_time": item.get("selling_time") or "",
        "scatter_speed": _first_float(_RE_SCATTER, joined),
        "lucky_speed": _first_float(_RE_LUCKY, joined),
        "head_cnt": head_cnt,
        "tail_cnt": tail_cnt,
        "head_speed": _first_float(_RE_HEAD_SPEED, joined),
        "pvp_score": _first_int(_RE_PVP, joined),
        "ssr_cnt": _first_int(_RE_SSR, summary),
        "six_star_cnt": _first_int(_RE_SIX_STAR, summary),
        "sign_days": _first_int(_RE_SIGN, summary),
        "fengzidu": _first_float(_RE_FENGZI, diy),
        "soul_jade": _first_int(_RE_SOUL_JADE, diy),
        "yuxing_dama": _first_int(_RE_DAMO, diy),
        "diy_desc": diy,
        "tags": tags,
        "top_heros": heroes,
        "highlights": highlights,
    }


def compact_row(record: dict[str, Any]) -> dict[str, Any]:
    """piko 模式回传用的精简结构（去掉重复的 highlights，保留可筛选字段）。"""
    row = dict(record)
    row.pop("highlights", None)
    return row
