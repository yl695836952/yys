# AGENTS.md · 交接说明

给下一个接手这个仓库的 agent 看。目标：藏宝阁全量账号 → 本地筛选 → 候选号御魂精算，自用买号。

## 当前状态

已完成并验证：
- 藏宝阁接口客户端（列表 / 详情），Cookie 登录态，失败可重试与登录态失效提示
- 全量列表枚举：价格区间二分拆桶，绕开「单查询 100 页」上限
- 列表字段标准化：散件一速、招财一速、头/尾数、头速、斗技分、SSR/六星/签到、风姿度、勾玉、御行达摩、荣誉标签、列表页 top_heros 面板
- SQLite 存取 + 多条件筛选 + 排序分页
- 本地筛选网页（筛选栏 / 卡片 / 抽屉详情）
- 御魂精算引擎：散件一速、招财一速、命中/抵抗一速、四件套一速、满速御魂数、PVE 有效强化评分、PVE 输出面板（4 件套 × 首领魂搜索，满暴约束）
- **口径已校验**：真实账号 `202611202001616-16-4S0QIIC2VYCKE` 算出散件一速 159.99、招财一速 158.13，与藏宝阁 highlights 完全一致；PVE 输出面板（须佐之男）综合 29595，量级与参考工具一致
- piko 列表 / 详情脚本，`import-piko`、`import-piko-details` 均跑通

未验证：
- `fetch-list` / `fetch-detail` 的 Cookie 全链路（本机没有 Cookie，解析与计算是用 piko 抓到的真实数据验证的）
- 大数据量下的抓取稳定性、限流表现

## 关键事实（实测，不要再猜）

接口与参数见 [docs/CBG_API.md](docs/CBG_API.md)。要点：

- 列表接口 `POST /cgi-bin/recommend.py?client_type=h5&act=recommd_by_role`，表单 `page`、`search_type=role`、`price_min`/`price_max`（**单位是「分」**）。
- 单页固定 **15 条**（`count`/`page_size` 均无效），`pager.total_pages` 上限 **100**。
- `order_by` / `order_direction` / `order_field` 实测被忽略，永远是默认推荐序 → 全量必须靠价格拆桶。
- 无 Cookie 时返回 `{"status":2,"status_code":"SESSION_TIMEOUT"}`。
- 详情 `GET /cgi/api/get_equip_desc?serverid=&ordersn=`，返回 `{version, equip_desc}`，`equip_desc` 是字符串化 JSON，约 8MB。
- 详情里没有 `yuhun` 字段：御魂在 `inventory`（uuid 索引），带 `pos`/`suitid` 的就是御魂；`boss_equips` 只是 uuid 数组。
- 御魂字段：`attrs[0]` 主属性，`attrs[1..]` 副属性，`single_attr` 特殊属性（首领魂），`rattr` 强化跳数（系数 × GROWTH_MAX = 实际值，优先用它）。
- 一速口径：`Σ 六个位置最优速度副属性 + 57`（2 号位主属性按满值 57 折算，**不要把 2 号位主属性再加一遍**，这是最初的坑）。
- 页内 `fetch()` 调详情接口会 `TypeError: Failed to fetch`，**XHR 正常**。
- 页面 → `http://127.0.0.1` 会被浏览器拦截（PNA/CSP），piko 只能靠 eval 返回值或浏览器下载落盘。
- **piko eval 单次回传上限约 26KB**（一页列表多一点），所以 piko 只能抽查；全量必须用 Cookie 模式。

## 下一步（按优先级）

1. 用真实 Cookie 跑一次 `fetch-list` 全量（约 1.3~1.5 万条、1000 次请求），确认拆桶覆盖完整（对比各桶 total_pages 是否都 < 100）。
2. PVE 面板性能：当前 beam=120、top_k=8、7 套 × 3 首领 × 15 掩码，单账号约 9 秒。跑几十个号前先优化（按套装预分组候选、缓存 2 件套加成）。
3. 补齐参考工具的「专项」判定：因幡辉夜姬散件爆伤、不见岳/云间不见岳防御、纺愿缘结神爆伤、伊邪那美/丑时之女效果命中、卑弥呼速度（阈值口径见 README 指标表）。
4. 前端「对当前筛选结果一键精算」：需要本地服务串行调用详情抓取，注意别并发打爆接口。
5. 详情抓取失败重试与断点续跑：`details` 表已有 computed_at，可以按「没有 metrics 的 eid」批量补算。

## 约定

- 新增计算口径必须写进 README 的指标表，阈值集中在 `config.THRESHOLDS`。
- 不要提交 `data/`、`.env`、Cookie。
- 静态资料 `src/yyscbg/data/*.json` 取自参考项目 yys_tool_phoenix 的官方配置快照（御魂套装、式神基础面板、区服表），随游戏更新需刷新。
