"""御魂与式神指标计算。

口径来自参考项目 yys_tool_phoenix（非商业许可，本项目仅自用参考）：
  * 一速 = 6 个号位各自最优速度之和 + 2 号位速度主属性 57（不含式神基础速度）
  * 招财一速 = 同上，但其中 4 个号位必须是招财猫
  * 满速御魂 = 6 星 15 级、速度副属性强化满 6 次（rattr 中速度条目数 = 6），2 号位需为速度主属性
  * PVE 输出面板 = 面板攻击 × 爆伤倍数（满暴 100% 起算），按 4 件套 × 2 件首领魂组合搜索
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from .config import DEFAULT_PVE_HEROES, FOUR_PIECE_SUITS, OMA_SUITS, STATIC_DIR, THRESHOLDS

# 单次强化满值（rattr 的系数 × 该值 = 实际属性增量）
GROWTH_MAX: dict[str, float] = {
    "speedAdditionVal": 3,
    "critRateAdditionVal": 3,
    "critPowerAdditionVal": 4,
    "attackAdditionRate": 3,
    "attackAdditionVal": 27,
    "maxHpAdditionRate": 3,
    "maxHpAdditionVal": 114,
    "defenseAdditionRate": 3,
    "defenseAdditionVal": 5,
    "debuffEnhance": 4,
    "debuffResist": 4,
}

POSITIONS = (1, 2, 3, 4, 5, 6)
SPEED_MAIN_MAX = 57.0  # 2 号位速度主属性满级值

_RE_TWO_PIECE = re.compile(r"^(攻击加成|防御加成|生命加成|暴击伤害|暴击|效果命中|效果抵抗)(\d+)%$")

_STAT_KEYS = {
    "速度": "speed",
    "暴击": "crit",
    "暴击伤害": "critDamage",
    "攻击加成": "attackPercent",
    "攻击": "attack",
    "生命加成": "healthPercent",
    "生命": "health",
    "防御加成": "defensePercent",
    "防御": "defense",
    "效果命中": "effectHit",
    "效果抵抗": "effectResistance",
}


# ---------------------------------------------------------------- 静态资料
def load_suit_config(path: Path | None = None) -> dict[int, dict[str, Any]]:
    """suitid -> {name, twoPiece: (label, value) | None, isOma}"""
    raw = json.loads((path or (STATIC_DIR / "relic-suits.json")).read_text(encoding="utf-8"))
    oma_ids = {int(k) for k in (raw.get("two_suit_yuhun") or {})}
    config: dict[int, dict[str, Any]] = {}
    for row in raw.get("yuhun_list") or []:
        suit_id, name, _slug, desc = row[0], row[1], row[2], row[3]
        match = _RE_TWO_PIECE.match(str(desc).strip())
        config[int(suit_id)] = {
            "id": int(suit_id),
            "name": name,
            "twoPiece": (match.group(1), int(match.group(2))) if match else None,
            "isOma": int(suit_id) in oma_ids,
        }
    return config


def load_heroes(path: Path | None = None) -> dict[int, dict[str, Any]]:
    raw = json.loads((path or (STATIC_DIR / "heroes.json")).read_text(encoding="utf-8"))
    return {int(k): v for k, v in (raw.get("heroesById") or {}).items()}


SUITS = load_suit_config()
HEROES = load_heroes()
HERO_BY_NAME = {hero.get("name"): hero for hero in HEROES.values()}


# ---------------------------------------------------------------- 基础解析
def stat_key(label: str) -> str | None:
    return _STAT_KEYS.get(label)


def _value(text: Any) -> float:
    return float(str(text).replace("%", "")) or 0.0


def _attr_total(relic: dict[str, Any]) -> dict[str, float]:
    """副属性总计；优先用 rattr 精确值，缺失时退回 attrs 文本。"""
    totals: dict[str, float] = {}
    rolls = relic.get("rolls") or []
    if rolls:
        for key, coef in rolls:
            stat = stat_key(_ROLL_LABELS.get(key, ""))
            if not stat:
                continue
            totals[stat] = totals.get(stat, 0.0) + GROWTH_MAX.get(key, 0) * float(coef)
        return totals
    for label, text in relic.get("subs") or []:
        stat = stat_key(label)
        if stat:
            totals[stat] = totals.get(stat, 0.0) + _value(text)
    return totals


_ROLL_LABELS = {
    "speedAdditionVal": "速度",
    "critRateAdditionVal": "暴击",
    "critPowerAdditionVal": "暴击伤害",
    "attackAdditionRate": "攻击加成",
    "attackAdditionVal": "攻击",
    "maxHpAdditionRate": "生命加成",
    "maxHpAdditionVal": "生命",
    "defenseAdditionRate": "防御加成",
    "defenseAdditionVal": "防御",
    "debuffEnhance": "效果命中",
    "debuffResist": "效果抵抗",
}


def parse_relic(raw: dict[str, Any]) -> dict[str, Any] | None:
    """把 inventory 里的御魂条目转成计算用结构。"""
    position = int(raw.get("pos") or 0)
    suit_id = int(raw.get("suitid") or 0)
    if position not in POSITIONS or suit_id <= 0:
        return None
    attrs = raw.get("attrs") or []
    main = (attrs[0][0], _value(attrs[0][1])) if attrs else (None, 0.0)
    subs = [(row[0], _value(row[1])) for row in attrs[1:] if isinstance(row, list) and len(row) >= 2]
    single = raw.get("single_attr")
    suit = SUITS.get(suit_id) or {"name": str(raw.get("name") or "未知御魂"), "twoPiece": None, "isOma": False}
    relic = {
        "uuid": str(raw.get("uuid") or ""),
        "suitId": suit_id,
        "suitName": suit["name"],
        "isOma": bool(suit["isOma"]),
        "twoPiece": suit["twoPiece"],
        "position": position,
        "quality": int(raw.get("qua") or 0),
        "level": int(raw.get("level") or 0),
        "mainLabel": main[0],
        "mainValue": main[1],
        "subs": subs,
        "single": (single[0], _value(single[1])) if single else None,
        "rolls": [(str(row[0]), float(row[1])) for row in (raw.get("rattr") or []) if isinstance(row, list) and len(row) >= 2],
        "speedRollCount": 0,
    }
    relic["totals"] = _attr_total(relic)
    relic["speedRollCount"] = sum(1 for key, _ in relic["rolls"] if key == "speedAdditionVal")
    return relic


def relics_from_desc(desc: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    """从 get_equip_desc 的全量数据中取出 6 个号位的御魂。"""
    by_position: dict[int, list[dict[str, Any]]] = {pos: [] for pos in POSITIONS}
    for raw in (desc.get("inventory") or {}).values():
        if not isinstance(raw, dict):
            continue
        relic = parse_relic(raw)
        if relic:
            by_position[relic["position"]].append(relic)
    return by_position


# ---------------------------------------------------------------- 速度指标
def _speed_of(relic: dict[str, Any], include_main: bool = False) -> float:
    """速度贡献。默认不计主属性：一速口径里 2 号位主速度统一按 57 折算。"""
    total = relic["totals"].get("speed", 0.0)
    if include_main and relic["mainLabel"] == "速度":
        total += relic["mainValue"]
    if relic["single"] and relic["single"][0] == "速度":
        total += relic["single"][1]
    return total


def _pick_best(items: Iterable[dict[str, Any]], need_main_speed: bool, main_required: str | None) -> dict[str, Any] | None:
    best = None
    best_value = 0.0
    for relic in items:
        if relic["quality"] != 6 or relic["level"] != 15:
            continue
        if need_main_speed and relic["position"] == 2 and relic["mainLabel"] != "速度":
            continue
        if main_required and relic["position"] == 4 and relic["mainLabel"] != main_required:
            continue
        value = _speed_of(relic)
        if best is None or value > best_value:
            best, best_value = relic, value
    return best


def speed_combination(
    by_position: dict[int, list[dict[str, Any]]],
    suit_name: str | None = None,
    main_required: str | None = None,
) -> dict[str, Any] | None:
    """一速组合。返回的 speed 已含 2 号位速度主属性 57。"""
    need_main_speed = True

    def solve(constrained_slots: set[int] | None) -> dict[str, Any] | None:
        picks: list[dict[str, Any]] = []
        total = 0.0
        for position in POSITIONS:
            items = by_position.get(position) or []
            if constrained_slots is not None and position in constrained_slots:
                items = [r for r in items if r["suitName"] == suit_name]
            if main_required and position == 4:
                items = [r for r in items if r["mainLabel"] == main_required]
            pick = _pick_best(items, need_main_speed, main_required)
            if pick is None:
                return None
            picks.append(pick)
            total += _speed_of(pick)
        return {
            "subSum": round(total, 2),
            "speed": round(total + SPEED_MAIN_MAX, 2),
            "relics": [
                {
                    "uuid": r["uuid"],
                    "suit": r["suitName"],
                    "position": r["position"],
                    "speed": round(_speed_of(r, True), 2),
                    "main": r["mainLabel"],
                }
                for r in picks
            ],
        }

    if not suit_name:
        return solve(None)

    best = None
    for mask in range(1 << len(POSITIONS)):
        chosen = {POSITIONS[i] for i in range(len(POSITIONS)) if mask & (1 << i)}
        if len(chosen) != 4:
            continue
        candidate = solve(chosen)
        if candidate and (best is None or candidate["speed"] > best["speed"]):
            best = candidate
    return best


def speed_metrics(by_position: dict[int, list[dict[str, Any]]]) -> dict[str, Any]:
    suit_speeds = []
    for suit_id, suit in SUITS.items():
        if suit["isOma"]:
            continue
        combination = speed_combination(by_position, suit["name"])
        if combination:
            suit_speeds.append({"suit": suit["name"], "speed": combination["speed"]})
    suit_speeds.sort(key=lambda row: -row["speed"])

    full_speed = [
        relic
        for relics in by_position.values()
        for relic in relics
        if relic["quality"] == 6
        and relic["level"] == 15
        and relic["speedRollCount"] == 6
        and (relic["position"] != 2 or relic["mainLabel"] == "速度")
    ]
    return {
        "scatter": speed_combination(by_position),
        "lucky": speed_combination(by_position, "招财猫"),
        "hit": speed_combination(by_position, None, "效果命中"),
        "resist": speed_combination(by_position, None, "效果抵抗"),
        "suitSpeeds": suit_speeds[:12],
        "fullSpeedCount": len(full_speed),
        "maxLevelCount": sum(
            1 for relics in by_position.values() for r in relics if r["quality"] == 6 and r["level"] == 15
        ),
        "relicTotal": sum(len(relics) for relics in by_position.values()),
    }


# ---------------------------------------------------------------- PVE 指标
def score_pve_relic(relic: dict[str, Any]) -> dict[str, Any] | None:
    """PVE 有效强化评分：只看攻击加成/暴击/爆伤，首领魂输出属性额外 +3。"""
    if relic["quality"] != 6 or relic["level"] != 15:
        return None
    if relic["position"] in (2, 4) and relic["mainLabel"] != "攻击加成":
        return None
    if relic["position"] == 6 and relic["mainLabel"] not in ("暴击", "暴击伤害"):
        return None
    effective = sum(
        1
        for key, coef in relic["rolls"]
        if _ROLL_LABELS.get(key) in ("攻击加成", "暴击", "暴击伤害")
        for _ in range(int(round(coef)))
    )
    if not relic["rolls"]:
        effective = sum(1 for label, _ in relic["subs"] if label in ("攻击加成", "暴击", "暴击伤害"))
    bonus = 3 if relic["single"] and relic["single"][0] in ("攻击加成", "暴击", "暴击伤害") else 0
    return {
        "uuid": relic["uuid"],
        "suit": relic["suitName"],
        "position": relic["position"],
        "effectiveCount": effective + bonus,
        "maximum": 11 if bonus else 8,
    }


def pve_suit_ranking(by_position: dict[int, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    for relics in by_position.values():
        for relic in relics:
            scored = score_pve_relic(relic)
            if not scored or scored["effectiveCount"] < 5:
                continue
            entry = scores.setdefault(
                relic["suitName"],
                {"suit": relic["suitName"], "total": 0, "count": 0, "isOma": relic["isOma"]},
            )
            entry["total"] += scored["effectiveCount"]
            entry["count"] += 1
    return sorted(scores.values(), key=lambda row: -row["total"])


def _bound_score(attack: float, crit_damage: float) -> float:
    return attack * crit_damage / 100.0


def _pick_candidates(items: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    """按暴击 / 攻击 / 爆伤三个方向各取一批，避免单一口径把满暴必需的御魂剪掉。"""
    if len(items) <= top_k:
        return items
    keys = (
        lambda r: r["totals"].get("crit", 0.0),
        lambda r: r["totals"].get("attackPercent", 0.0) * 2 + r["totals"].get("attack", 0.0) / 20,
        lambda r: r["totals"].get("critDamage", 0.0),
    )
    picked: dict[str, dict[str, Any]] = {}
    for key in keys:
        for relic in sorted(items, key=key, reverse=True)[:top_k]:
            picked[relic["uuid"]] = relic
    return list(picked.values())


def _best_plan_for_layout(
    by_position: dict[int, list[dict[str, Any]]],
    base: dict[str, Any],
    layout: dict[int, str | None],
    crit_min: float,
    top_k: int = 8,
    beam: int = 120,
) -> dict[str, Any] | None:
    """固定号位套装约束后，逐号位 beam 搜索最大输出面板。"""
    base_attack = float(base.get("attack") or 0)
    base_crit = float(base.get("critRate") or 0)
    base_cd = float(base.get("critDamage") or 150)

    candidates: dict[int, list[dict[str, Any]]] = {}
    for position in POSITIONS:
        required = layout.get(position)
        items = [
            relic
            for relic in by_position.get(position) or []
            if relic["quality"] == 6 and relic["level"] == 15 and (required is None or relic["suitName"] == required)
        ]
        if not items:
            return None
        candidates[position] = _pick_candidates(items, top_k)

    def heuristic(atk_flat: float, atk_pct: float, crit: float, cd: float) -> float:
        attack = base_attack * (1 + atk_pct / 100) + atk_flat
        raw = _bound_score(attack, base_cd + cd)
        # 满暴是硬约束，未满暴的状态按缺口打折，避免搜索把暴击御魂全剪掉。
        return raw * (0.35 + 0.65 * min(1.0, (base_crit + crit) / 100.0))

    states: list[tuple[float, float, float, float, list[dict[str, Any]]]] = [(0.0, 0.0, 0.0, 0.0, [])]
    for position in POSITIONS:
        expanded = []
        for atk_flat, atk_pct, crit, cd, picks in states:
            for relic in candidates[position]:
                totals = relic["totals"]
                main_label, main_value = relic["mainLabel"], relic["mainValue"]
                add_flat = totals.get("attack", 0.0)
                add_pct = totals.get("attackPercent", 0.0)
                add_crit = totals.get("crit", 0.0)
                add_cd = totals.get("critDamage", 0.0)
                if main_label == "攻击":
                    add_flat += main_value
                elif main_label == "攻击加成":
                    add_pct += main_value
                elif main_label == "暴击":
                    add_crit += main_value
                elif main_label == "暴击伤害":
                    add_cd += main_value
                if relic["single"]:
                    label, value = relic["single"]
                    if label == "攻击":
                        add_flat += value
                    elif label == "攻击加成":
                        add_pct += value
                    elif label == "暴击":
                        add_crit += value
                    elif label == "暴击伤害":
                        add_cd += value
                expanded.append((atk_flat + add_flat, atk_pct + add_pct, crit + add_crit, cd + add_cd, picks + [relic]))
        expanded.sort(key=lambda s: -heuristic(s[0], s[1], s[2], s[3]))
        states = expanded[:beam]

    best = None
    for atk_flat, atk_pct, crit, cd, picks in states:
        suit_counts: dict[str, int] = {}
        for relic in picks:
            suit_counts[relic["suitName"]] = suit_counts.get(relic["suitName"], 0) + 1
        bonus_pct = bonus_flat = bonus_crit = bonus_cd = 0.0
        for suit_name, count in suit_counts.items():
            if count < 2:
                continue
            for relic in picks:
                if relic["suitName"] == suit_name and relic["twoPiece"]:
                    label, value = relic["twoPiece"]
                    if label == "攻击加成":
                        bonus_pct += value
                    elif label == "攻击":
                        bonus_flat += value
                    elif label == "暴击":
                        bonus_crit += value
                    elif label == "暴击伤害":
                        bonus_cd += value
                    break
        total_crit = base_crit + crit + bonus_crit
        if total_crit < crit_min:
            continue
        attack = base_attack * (1 + (atk_pct + bonus_pct) / 100) + atk_flat + bonus_flat
        total_cd = base_cd + cd + bonus_cd
        candidate = {
            "panel": round(_bound_score(attack, total_cd)),
            "attack": round(attack),
            "crit": round(total_crit, 1),
            "critDamage": round(total_cd, 1),
            "relics": [
                {"uuid": r["uuid"], "suit": r["suitName"], "position": r["position"], "main": r["mainLabel"]}
                for r in picks
            ],
        }
        if best is None or candidate["panel"] > best["panel"]:
            best = candidate
    return best


def _layouts(four_piece: str | None, oma: str | None) -> list[dict[int, str | None]]:
    if not four_piece:
        return [{position: None for position in POSITIONS}]
    layouts = []
    for mask in range(1 << len(POSITIONS)):
        chosen = {POSITIONS[i] for i in range(len(POSITIONS)) if mask & (1 << i)}
        if len(chosen) != 4:
            continue
        layouts.append({position: (four_piece if position in chosen else oma) for position in POSITIONS})
    return layouts


def pve_panel(
    by_position: dict[int, list[dict[str, Any]]],
    base: dict[str, Any],
    crit_min: float = 100.0,
    oma_list: list[str] | None = None,
) -> list[dict[str, Any]]:
    """按 4 件套 × 首领魂 组合搜索输出面板，返回每个组合的最优结果。"""
    results = []
    for four_piece in FOUR_PIECE_SUITS:
        for oma in oma_list or OMA_SUITS:
            best = None
            for layout in _layouts(four_piece, oma):
                candidate = _best_plan_for_layout(by_position, base, layout, crit_min)
                if candidate and (best is None or candidate["panel"] > best["panel"]):
                    best = candidate
            if best:
                results.append({"fourPiece": four_piece, "oma": oma, **best})
    return results


# ---------------------------------------------------------------- 汇总
def hero_base(desc: dict[str, Any], wanted: list[str]) -> tuple[str | None, dict[str, Any] | None]:
    """挑一个账号拥有的输出式神，基础面板优先用静态资料（账号里的是当前等级下的实际值）。"""
    owned_names: set[str] = set()
    for raw in (desc.get("heroes") or {}).values():
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")
        if not name:
            continue
        level = int(raw.get("level") or 0)
        # 只把满级（或已觉醒高等级）的式神当作可用输出
        if level >= 30:
            owned_names.add(name)

    def static_base(name: str) -> dict[str, Any] | None:
        hero = HERO_BY_NAME.get(name)
        return hero.get("baseStats") if hero else None

    for name in wanted:
        if name in owned_names and static_base(name):
            return name, static_base(name)
    # 没有指定式神时，取静态表中攻击最高的已拥有式神近似输出面板。
    candidates = [name for name in owned_names if static_base(name)]
    if not candidates:
        return None, None
    name = max(candidates, key=lambda key: float(static_base(key).get("attack") or 0))
    return name, static_base(name)


def account_metrics(desc: dict[str, Any], pve_hero: str | None = None) -> dict[str, Any]:
    by_position = relics_from_desc(desc)
    speed = speed_metrics(by_position)
    hero_name, base = (pve_hero, (HERO_BY_NAME.get(pve_hero) or {}).get("baseStats")) if pve_hero else (None, None)
    if not base:
        hero_name, base = hero_base(desc, DEFAULT_PVE_HEROES)
    panels = pve_panel(by_position, base) if base else []

    by_four: dict[str, list[int]] = {}
    for row in panels:
        by_four.setdefault(row["fourPiece"], []).append(row["panel"])
    summary = [
        {
            "suit": suit,
            "best": max(values),
            "average": round(sum(values) / len(values)),
            "badge": _badge(max(values)),
        }
        for suit, values in by_four.items()
    ]
    summary.sort(key=lambda row: -row["best"])
    overall = summary[0]["average"] if summary else 0

    return {
        "hero": hero_name,
        "base": base,
        "speed": speed,
        "pve": {
            "panels": panels,
            "summary": summary,
            "overall": overall,
            "badge": _badge(overall),
        },
        "pveScoreRanking": pve_suit_ranking(by_position)[:10],
        "resources": {
            "gouyu": desc.get("soul_jade"),
            "money": desc.get("money"),
            "strength": desc.get("strength"),
            "fengzidu": desc.get("fengzidu"),
            "level15": desc.get("level_15"),
            "equipSummary": desc.get("equips_summary"),
            "heroSummary": desc.get("hero_summary"),
            "pvpScore": desc.get("pvp_score"),
            "pvpStage": desc.get("pvp_stage"),
            "signDays": desc.get("sign_days"),
        },
    }


def _badge(value: float) -> str:
    if value >= THRESHOLDS["panel_grad"]:
        return "毕业"
    if value >= THRESHOLDS["panel_pass"]:
        return "达标"
    return "未达标"
