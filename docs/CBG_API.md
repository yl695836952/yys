# 藏宝阁接口笔记（实测 2026-11）

所有接口都在 `https://yys.cbg.163.com` 下，**必须带登录 Cookie**（含 `SID`），否则返回：

```json
{"status": 2, "status_code": "SESSION_TIMEOUT", "msg": "更新登录状态"}
```

## 列表

```
POST /cgi-bin/recommend.py?client_type=h5&act=recommd_by_role
Content-Type: application/x-www-form-urlencoded

page=1&search_type=role&price_min=10000&price_max=20000
```

- `price_min` / `price_max`：单位「分」，即 10000 = ¥100。
- 未带价格区间时返回默认推荐池（与 `tfid=f_kingkong` 精选一致）。
- `order_by=price&order_direction=ASC`、`order_field=price`、`count=50`、`page_size=50` 实测**都不生效**（`order_field` 始终回 `recommd`，单页始终 15 条）。
- `attrs_search.max_sanjian_speed_min` 等一速筛选参数未验证成功，前端筛选页的字段名尚未确认；需要服务端一速筛选时再抓一次 筛选页 的请求体。

响应：

```json
{
  "status": 1,
  "order_field": "recommd",
  "pager": {"cur_page": 1, "total_pages": 100},
  "paging": {"is_last_page": false},
  "result": [ { ... }, ... 15 条 ]
}
```

`pager.total_pages` 最多 100 → 单查询最多 1500 条，全量必须按价格区间二分。

### result 关键字段

| 字段 | 说明 |
|---|---|
| `eid` | 订单号，详情/商品页都用它（形如 `202611202001616-16-4S0QIIC2VYCKE`） |
| `serverid` | 区服 id，详情接口必传 |
| `price` | 价格，单位「分」 |
| `area_name` / `server_name` | 大区 / 服务器 |
| `equip_level` | 账号等级 |
| `collect_num` | 收藏数 |
| `selling_time` | 上架时间 |
| `highlights` | 字符串数组：`散件一速159.99`、`招财一速158.13`、`6头8尾`、`头速度17.13`、`斗技2700`，以及荣誉标签 |
| `desc_sumup_short` | `SSR 340   六星式神 327   签到2931天` |
| `diy_desc` | `3328枚魂玉,23.1万体力,63384风姿度,2张曜之契,157个御行达摩` |
| `other_info.top_heros` | 列表页展示的式神面板：`add_speed_not_display`、`strike_not_display`(暴击)、`strike_damage_not_display`(爆伤) |

## 详情

```
GET /cgi/api/get_equip_desc?serverid=16&ordersn=<game_ordersn>
```

**`ordersn` 必须用列表里的 `game_ordersn`，不能传 `eid`。**

两者的格式不同（`eid` 尾部是 17 位、`game_ordersn` 尾部是 13 位），
用 `eid` 请求会返回：

```json
{"status": 0, "msg": "物品不存在"}
```

这是踩过的坑：代码里 `listings.ordersn` 专门存 `game_ordersn`，详情只认这个字段。
明细大小差异很大：小号约 90KB，满收藏的大号约 8MB。

响应外层：

```json
{"version": "9f7fed8d...", "equip_desc": "{...账号全量 JSON 字符串...}"}
```

`equip_desc` 解析后约 90 个顶层 key，常用的：

| key | 说明 |
|---|---|
| `inventory` | 背包/御魂，按 uuid 索引（7919 条级别） |
| `heroes` | 已拥有式神，`attrs` 为**基础面板**（攻击/暴击/爆伤/速度…） |
| `boss_equips` | 首领御魂 uuid 数组 |
| `pvp_score` / `pvp_rank` / `pvp_stage` | 斗技分 / 排名 / 段位 |
| `soul_jade`(`goyu`) / `money` / `strength` / `fengzidu` | 勾玉 / 金币 / 体力 / 风姿度 |
| `level_15` / `equips_summary` / `hero_summary` | 满级御魂数 / 御魂总数 / 式神数 |
| `sign_days` | 签到天数 |
| `head_skin` / `cbg_special_skin_list` | 头像框 / 皮肤 |
| `damo_count_dict` | 御行达摩等（物品 411） |

### 御魂条目（`inventory` 的值）

```json
{
  "uuid": "6799a7138fb48a6554448323",
  "suitid": 300077, "name": "鬼灵歌伎",
  "pos": 3, "qua": 6, "level": 15,
  "attrs": [["防御","104.00"],["防御加成","5.52%"],["速度","8.20%"],["暴击","5.65%"],["暴击伤害","3.70%"]],
  "single_attr": ["暴击","8.00%"],
  "rattr": [["defenseAdditionRate",0.95],["critRateAdditionVal",0.92],["speedAdditionVal",0.83]]
}
```

- `attrs[0]` 主属性，`attrs[1..]` 副属性，`single_attr` 特殊属性（首领魂）。
- `rattr` 是强化跳数：每跳实际值 = 系数 × `GROWTH_MAX[key]`（速度 3、暴击 3、爆伤 4、攻击加成 3、攻击 27、生命加成 3、生命 114、防御加成 3、防御 5、命中 4、抵抗 4）。
- 6 星主属性满值：速度 57、攻击 486、防御 104、生命 2052、各类百分比 55、爆伤 89。
- 6 星 15 级、速度属性强化满 6 跳的御魂即「满速」御魂。

## 浏览器内取数注意

- 页面里 `fetch()` 调详情接口会 `TypeError: Failed to fetch`，**用 XHR** 就正常。
- 页面 → `http://127.0.0.1` 被拦截（PNA / CSP），piko 不能直接往本地服务推数据。
- 藏宝阁筛选页 `/cgi/mweb/advance/search?search_type=role` 支持：区服、公示期、价格、系统、图鉴、指定式神、6 星数量、斗技段位/积分、散件一速、招财一速、头/尾个数与速度、满速御魂数、资产/皮肤/头像框/成就等。
