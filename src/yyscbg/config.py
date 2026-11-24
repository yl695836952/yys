"""项目配置：路径、Cookie、服务端口与判定阈值。"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
STATIC_DIR = Path(__file__).resolve().parent / "data"

DB_PATH = Path(os.environ.get("YYS_DB") or (DATA_DIR / "yys.db"))

HOST = os.environ.get("YYS_HOST", "127.0.0.1")
PORT = int(os.environ.get("YYS_PORT", "24980"))

# 藏宝阁只认登录态，Cookie 里至少要含 SID（HttpOnly，需从浏览器/CDP 取）。
COOKIE_ENV = "CBG_COOKIE"

# 并发与节流：单机全量约 1.3~1.5 万条，100 页/查询上限。
CONCURRENCY = int(os.environ.get("YYS_CONCURRENCY", "4"))
REQUEST_INTERVAL = float(os.environ.get("YYS_INTERVAL", "0.15"))

# PVE/PVP 判定阈值，默认值取自参考工具（yys_tool_phoenix）的默认口径，可在 .env 调整。
THRESHOLDS = {
    # 4 项两件套平均后的输出面板
    "panel_pass": int(os.environ.get("YYS_PANEL_PASS", "28000")),
    "panel_grad": int(os.environ.get("YYS_PANEL_GRAD", "30000")),
    # 散件一速（含 2 号位 57）
    "speed_pass": float(os.environ.get("YYS_SPEED_PASS", "158.0")),
    "speed_grad": float(os.environ.get("YYS_SPEED_GRAD", "160.0")),
    # 招财一速
    "lucky_speed_pass": float(os.environ.get("YYS_LUCKY_SPEED_PASS", "155.0")),
    "lucky_speed_grad": float(os.environ.get("YYS_LUCKY_SPEED_GRAD", "158.0")),
    # 斗技积分
    "pvp_pass": int(os.environ.get("YYS_PVP_PASS", "3000")),
    "pvp_grad": int(os.environ.get("YYS_PVP_GRAD", "3600")),
}

# 评估 PVE 时默认使用的输出式神（没有该式神时自动回退到其它输出）。
DEFAULT_PVE_HEROES = ["须佐之男", "天照", "季", "千姬", "紧那罗"]

# 输出套装与首领御魂，顺序即界面展示顺序。
FOUR_PIECE_SUITS = ["狂骨", "海月火玉", "伤魂鸟", "破势", "隐念", "镇墓兽", "片叶之苇"]
OMA_SUITS = ["土蜘蛛", "荒骷髅", "鬼灵歌伎"]


def load_dotenv(path: Path | None = None) -> None:
    """读取仓库根目录 .env；已存在的环境变量优先，不覆盖。"""
    env_file = path or (ROOT / ".env")
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def cookie() -> str:
    return (os.environ.get(COOKIE_ENV) or "").strip()
