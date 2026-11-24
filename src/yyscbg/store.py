"""本地 SQLite 存储：列表快照 + 详情精算结果。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Iterable

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    eid            TEXT PRIMARY KEY,
    serverid       INTEGER,
    price          REAL,
    area           TEXT,
    server         TEXT,
    platform       TEXT,
    level          INTEGER,
    status         INTEGER,
    collect        INTEGER,
    selling_time   TEXT,
    scatter_speed  REAL,
    lucky_speed    REAL,
    head_cnt       INTEGER,
    tail_cnt       INTEGER,
    head_speed     REAL,
    pvp_score      INTEGER,
    ssr_cnt        INTEGER,
    six_star_cnt   INTEGER,
    sign_days      INTEGER,
    fengzidu       REAL,
    soul_jade      INTEGER,
    yuxing_dama    INTEGER,
    diy_desc       TEXT,
    tags           TEXT,
    top_heros      TEXT,
    highlights     TEXT,
    first_seen     TEXT,
    last_seen      TEXT,
    active         INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_listings_speed ON listings(scatter_speed);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);
CREATE INDEX IF NOT EXISTS idx_listings_pvp ON listings(pvp_score);

CREATE TABLE IF NOT EXISTS details (
    eid         TEXT PRIMARY KEY,
    metrics     TEXT,
    computed_at TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT,
    started_at  TEXT,
    finished_at TEXT,
    total       INTEGER,
    note        TEXT
);
"""

_COLUMNS = [
    "eid", "serverid", "price", "area", "server", "platform", "level", "status", "collect",
    "selling_time", "scatter_speed", "lucky_speed", "head_cnt", "tail_cnt", "head_speed",
    "pvp_score", "ssr_cnt", "six_star_cnt", "sign_days", "fengzidu", "soul_jade",
    "yuxing_dama", "diy_desc", "tags", "top_heros", "highlights",
]

SORTABLE = {
    "price": "price",
    "speed": "scatter_speed",
    "lucky": "lucky_speed",
    "pvp": "pvp_score",
    "head": "head_cnt",
    "heros": "six_star_cnt",
    "ssr": "ssr_cnt",
    "fengzidu": "fengzidu",
    "collect": "collect",
    "time": "last_seen",
}


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(path=None) -> sqlite3.Connection:
    db_path = path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_listings(conn: sqlite3.Connection, rows: Iterable[dict[str, Any]]) -> int:
    stamp = now()
    sql = (
        f"INSERT INTO listings ({', '.join(_COLUMNS)}, first_seen, last_seen, active) "
        f"VALUES ({', '.join('?' for _ in _COLUMNS)}, ?, ?, 1) "
        "ON CONFLICT(eid) DO UPDATE SET "
        + ", ".join(f"{c}=excluded.{c}" for c in _COLUMNS if c != "eid")
        + ", last_seen=excluded.last_seen, active=1"
    )
    count = 0
    for row in rows:
        if not row.get("eid"):
            continue
        values = []
        for column in _COLUMNS:
            value = row.get(column)
            if column in ("tags", "top_heros"):
                value = json.dumps(value or [], ensure_ascii=False)
            elif column == "highlights":
                value = json.dumps(value or [], ensure_ascii=False)
            values.append(value)
        conn.execute(sql, values + [stamp, stamp])
        count += 1
    conn.commit()
    return count


def mark_inactive(conn: sqlite3.Connection, keep_eids: set[str]) -> int:
    """一次全量抓取结束后，把本次没出现的记录标记为下架。"""
    cur = conn.execute("SELECT eid FROM listings WHERE active=1")
    stale = [row["eid"] for row in cur if row["eid"] not in keep_eids]
    for eid in stale:
        conn.execute("UPDATE listings SET active=0 WHERE eid=?", (eid,))
    conn.commit()
    return len(stale)


def save_metrics(conn: sqlite3.Connection, eid: str, metrics: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO details (eid, metrics, computed_at) VALUES (?, ?, ?) "
        "ON CONFLICT(eid) DO UPDATE SET metrics=excluded.metrics, computed_at=excluded.computed_at",
        (eid, json.dumps(metrics, ensure_ascii=False), now()),
    )
    conn.commit()


def get_metrics(conn: sqlite3.Connection, eid: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT metrics FROM details WHERE eid=?", (eid,)).fetchone()
    return json.loads(row["metrics"]) if row else None


def get_listing(conn: sqlite3.Connection, eid: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM listings WHERE eid=?", (eid,)).fetchone()
    return dict(row) if row else None


def query(
    conn: sqlite3.Connection,
    filters: dict[str, Any] | None = None,
    sort: str = "speed",
    desc: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    filters = filters or {}
    where: list[str] = []
    params: list[Any] = []

    def add(sql: str, *values: Any) -> None:
        where.append(sql)
        params.extend(values)

    if filters.get("active", True):
        add("active=1")
    if filters.get("minPrice") is not None:
        add("price >= ?", float(filters["minPrice"]))
    if filters.get("maxPrice") is not None:
        add("price <= ?", float(filters["maxPrice"]))
    if filters.get("minSpeed") is not None:
        add("scatter_speed >= ?", float(filters["minSpeed"]))
    if filters.get("minLucky") is not None:
        add("lucky_speed >= ?", float(filters["minLucky"]))
    if filters.get("minHead") is not None:
        add("head_cnt >= ?", int(filters["minHead"]))
    if filters.get("minTail") is not None:
        add("tail_cnt >= ?", int(filters["minTail"]))
    if filters.get("minPvp") is not None:
        add("pvp_score >= ?", int(filters["minPvp"]))
    if filters.get("minSixStar") is not None:
        add("six_star_cnt >= ?", int(filters["minSixStar"]))
    if filters.get("minSsr") is not None:
        add("ssr_cnt >= ?", int(filters["ssr_cnt"]))
    if filters.get("minFengzidu") is not None:
        add("fengzidu >= ?", float(filters["minFengzidu"]))
    if filters.get("area"):
        add("area LIKE ?", f"%{filters['area']}%")
    if filters.get("keyword"):
        add("(server LIKE ? OR diy_desc LIKE ? OR tags LIKE ?)", *( [f"%{filters['keyword']}%"] * 3 ))
    if filters.get("tag"):
        add("tags LIKE ?", f"%{filters['tag']}%")

    clause = (" WHERE " + " AND ".join(where)) if where else ""
    column = SORTABLE.get(sort, "scatter_speed")
    order = "DESC" if desc else "ASC"
    total = conn.execute(f"SELECT COUNT(*) AS n FROM listings{clause}", params).fetchone()["n"]
    rows = conn.execute(
        f"SELECT * FROM listings{clause} ORDER BY {column} IS NULL, {column} {order} LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["tags"] = json.loads(item.get("tags") or "[]")
        item["top_heros"] = json.loads(item.get("top_heros") or "[]")
        item["highlights"] = json.loads(item.get("highlights") or "[]")
        items.append(item)
    return {"total": total, "items": items}


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) AS n FROM listings WHERE active=1").fetchone()["n"]
    details = conn.execute("SELECT COUNT(*) AS n FROM details").fetchone()["n"]
    last = conn.execute("SELECT MAX(last_seen) AS t FROM listings").fetchone()["t"]
    runs = [dict(row) for row in conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 5")]
    return {"listings": total, "details": details, "lastSeen": last, "runs": runs}


def start_run(conn: sqlite3.Connection, kind: str, note: str = "") -> int:
    cur = conn.execute("INSERT INTO runs (kind, started_at, note) VALUES (?, ?, ?)", (kind, now(), note))
    conn.commit()
    return int(cur.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int, total: int) -> None:
    conn.execute("UPDATE runs SET finished_at=?, total=? WHERE id=?", (now(), total, run_id))
    conn.commit()
