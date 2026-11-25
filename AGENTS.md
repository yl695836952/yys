# AGENTS.md · 交接说明

给下一个接手这个仓库的 agent 看。目标：藏宝阁全量账号 → 本地筛选 → 候选号御魂精算，自用买号。

## 当前状态

已完成并验证：
- 藏宝阁接口客户端（列表 / 详情，gzip 传输），Cookie 登录态，失败重试与失效提示
- 全量列表枚举：价格区间二分拆桶绕开「单查询 100 页」上限
- 列表字段标准化：散件一速、招财一速、头/尾数、头速、斗技分、SSR/六星/签到、风姿度、勾玉、御行达摩、荣誉标签、列表页 top_heros 面板
- SQLite 存取 + 多条件筛选 + 排序分页 + 本地筛选网页
- 御魂精算引擎：散件一速、招财一速、命中/抵抗一速、四件套一速、满速御魂数、PVE 有效强化评分、PVE 输出面板（4 件套 × 首领魂搜索，满暴约束）
- **批量精算流水线**（`fetch-details-all`）：线程池下载 + 进程池计算 + 按批落库 + 断点续跑 + 增量（按 `panel_scope` 判断哪些首领组合算过）
- **面板入库与筛选**：`details_panels(eid,suit,best,average)` 单独建表，筛选页支持「指定套装 ≥ 阈值」与按面板排序
- **口径已校验**：真实账号 `202611202001616-16-4S0QIIC2VYCKE` 散件一速 159.99、招财一速 158.13，与藏宝阁 highlights 完全一致；PVE 面板（须佐之男，荒骷髅）破势 29867 / 狂骨 29199

性能（本机实测，单号 7919 件御魂）：
- 解析御魂 0.14s；速度指标 0.05s（原 3.6s，已改成「每号位只排序一次 + 套装查表」）
- PVE 面板：只算荒骷髅 2.8s，三个首领 8.3s
- 全量 1.5 万号首轮（荒骷髅、8 进程）约 1.5~2 小时；之后增量几分钟

未验证：
- 真实 Cookie 下的 `fetch-list` / `fetch-details-all` 网络链路（本机无 Cookie，流水线用本地 fixture 冒充接口验证过并发/进程池/落库/增量/筛选）
- 长时间大批量的限流表现（建议 `--download-workers 4~6`，别拉满）

## 关键事实（实测，不要再猜）

接口与参数见 [docs/CBG_API.md](docs/CBG_API.md)。要点：

- 列表接口 `POST /cgi-bin/recommend.py?client_type=h5&act=recommd_by_role`，表单 `page`、`search_type=role`、`price_min`/`price_max`（**单位是「分」**）。
- 单页固定 **15 条**（`count`/`page_size` 均无效），`pager.total_pages` 上限 **100**。
- `order_by` / `order_direction` / `order_field` 实测被忽略，永远是默认推荐序 → 全量必须靠价格拆桶。
- 无 Cookie 时返回 `{"status":2,"status_code":"SESSION_TIMEOUT"}`。
- **详情必须传 `game_ordersn`，不能传 `eid`**（`eid` 尾段 17 位、`game_ordersn` 尾段 13 位；传 eid 会返回 `{"status":0,"msg":"物品不存在"}`）。`listings.ordersn` 专存 `game_ordersn`，抓列表时务必一起保存。
- 详情 `GET /cgi/api/get_equip_desc?serverid=&ordersn=<game_ordersn>`，返回 `{version, equip_desc}`，`equip_desc` 是字符串化 JSON；大小 90KB（小号）到 8MB（大号）不等。
- 详情里没有 `yuhun` 字段：御魂在 `inventory`（uuid 索引），带 `pos`/`suitid` 的就是御魂；`boss_equips` 只是 uuid 数组。
- 御魂字段：`attrs[0]` 主属性，`attrs[1..]` 副属性，`single_attr` 特殊属性（首领魂），`rattr` 强化跳数（系数 × GROWTH_MAX = 实际值，优先用它）。
- 一速口径：`Σ 六个位置最优速度副属性 + 57`（2 号位主属性按满值 57 折算，**不要把 2 号位主属性再加一遍**，这是最初的坑）。
- 页内 `fetch()` 调详情接口会 `TypeError: Failed to fetch`，**XHR 正常**。
- 页面 → `http://127.0.0.1` 会被浏览器拦截（PNA/CSP），piko 只能靠 eval 返回值或浏览器下载落盘。
- **piko eval 单次回传上限约 26KB**（一页列表多一点），所以 piko 只能抽查；全量必须用 Cookie 模式。
- **浏览器下载有限制**：同一页面连续触发多个 `<a download>` 会被 Chrome「自动下载多个文件」拦住，只落第一个。要么让用户点允许，要么一个一个来，批量请走 Cookie 模式。
- **风控**：藏宝阁对高频请求敏感，实测用户在家跑全量时触发短信验证。批量精算请把 `--download-workers` 压到 2~3、`--batch` 调小（如 20），必要时在批之间 sleep。

## 下一步（按优先级）

1. 用真实 Cookie 跑一次 `fetch-list` 全量（约 1.3~1.5 万条、1000 次请求），确认拆桶覆盖完整（对比各桶 `total_pages` 是否都 < 100），再跑 `fetch-details-all --oma 荒骷髅`。
2. 观察真实限流：如果出现 403/429，把 `--download-workers` 降到 3~4，并考虑在 `cbg.py` 里加自适应退避。
3. 补齐参考工具的「专项」判定：因幡辉夜姬散件爆伤、不见岳/云间不见岳防御、纺愿缘结神爆伤、伊邪那美/丑时之女效果命中、卑弥呼速度（阈值口径见 README 指标表）。
4. 面板搜索还能再快：`_best_plan_for_layout` 目前每套 × 每个首领 × 15 种位置分配各跑一次 beam，可以先把「2 件套加成」按套装预算好、并按套装预分组候选。
5. 前端「对当前筛选结果一键精算」：需要在服务端串行触发详情抓取（别和后台流水线抢并发）。
6. 若之后要补算另外两个首领：直接 `yyscbg fetch-details-all --oma 土蜘蛛,鬼灵歌伎`，`auto` 模式会自动挑出 `panel_scope` 没覆盖的号。

## 约定

- 新增计算口径必须写进 README 的指标表，阈值集中在 `config.THRESHOLDS`。
- 不要提交 `data/`、`.env`、Cookie。
- 静态资料 `src/yyscbg/data/*.json` 取自参考项目 yys_tool_phoenix 的官方配置快照（御魂套装、式神基础面板、区服表），随游戏更新需刷新。
- 精算结果必须同时写 `details`（全量指标）和 `details_panels`（按套装的面板），否则筛选页查不到。
