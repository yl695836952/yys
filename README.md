# 阴阳师藏宝阁账号分析（自用）

抓取藏宝阁全量在售账号 → 落本地 SQLite → 用本地网页按 PVP/PVE 指标筛选 → 对候选账号做御魂精算。

## 形态

```
fetch-list        全量列表（价格分桶枚举，约 1.3~1.5 万条）
   ↓ 存 data/yys.db · listings 表
serve             本地筛选网页（http://127.0.0.1:24980）
   ↓ 你挑出候选
fetch-detail      对候选号抓 8MB 全量明细，算一速/套装/输出面板
   ↓ 存 data/yys.db · details 表
在网页抽屉里看精算结果
```

## 快速开始

```bash
# 0. 安装（纯标准库，无第三方依赖；也可以不装，改用 PYTHONPATH=src）
pip install -e .

# 1. 配置登录 Cookie（藏宝阁所有接口都要登录态）
cp .env.example .env
#    浏览器登录藏宝阁 → F12 → Network → 任一 cgi 请求 → 复制请求头 Cookie 整行填进 CBG_COOKIE
python tools/check_cookie.py        # 自检

# 2. 抓全量列表（约 1000 次请求，建议低并发慢慢跑）
yyscbg fetch-list --workers 4

# 3. 起筛选页
yyscbg serve                        # 打开 http://127.0.0.1:24980

# 4. 对筛选出的候选号做精算（按 eid 或按条件批量）
yyscbg fetch-detail --eids 202611202001616-16-4S0QIIC2VYCKE
yyscbg fetch-detail --min-speed 158 --min-lucky 155 --limit 20
```

不需要 Cookie 时（比如换台电脑懒得取 Cookie），用 piko 浏览器模式，见 [tools/PIKO.md](tools/PIKO.md)。

## 指标口径

一速这类数值的算法来自参考项目 [yys_tool_phoenix](https://github.com/iXinMengChen/yys_tool_phoenix)（非商业许可，本项目仅自用参考其算法与静态资料）：

| 指标 | 定义 |
|---|---|
| 散件一速 | 6 个号位各取速度最高的满级 6 星御魂，速度相加后再加 2 号位速度主属性 57（不含式神基础速度） |
| 招财一速 | 同上，但 4 个号位必须是招财猫 |
| 满速御魂 | 6 星 15 级，速度副属性强化满 6 次（`rattr` 中速度条目数 = 6），2 号位须为速度主属性 |
| 输出面板 | 面板攻击 × 爆伤倍数；要求满暴（100%），按「4 件套 + 2 件首领魂」组合搜索最优 |
| PVE 有效强化 | 副属性中攻击加成 / 暴击 / 爆伤的强化次数，首领魂输出属性额外 +3 |

达标/毕业阈值默认 28000 / 30000，可在 `.env` 里改。

## 目录

```
src/yyscbg/cbg.py        藏宝阁接口客户端（列表 / 详情）
src/yyscbg/parse.py      列表字段标准化（highlights → 数值）
src/yyscbg/relics.py     御魂与面板计算（一速、套装、PVE 面板搜索）
src/yyscbg/fetch.py      全量枚举、详情精算、piko 导入
src/yyscbg/store.py      SQLite 存取与筛选查询
src/yyscbg/server.py     本地筛选服务
src/yyscbg/data/         御魂套装表、式神基础面板、区服表（静态资料）
web/                     筛选页面
tools/                   piko 脚本、Cookie 自检
docs/CBG_API.md          已实测的藏宝阁接口说明
AGENTS.md                交接说明（给下一个接手的 Trae/agent 看）
```

## 注意

- 只抓**在售**账号，抓完会把本轮没出现的记录标成 `active=0`，不删历史。
- 单次查询服务端最多返回 100 页 × 15 条，所以全量靠价格区间二分拆桶；脚本会自动拆。
- 详情接口每个账号约 8MB，只对候选号抓，别全量抓。
- 数据仅本地存放，`data/` 已被 gitignore。
