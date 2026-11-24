# piko 浏览器取数（不需要 Cookie）

家里电脑已登录藏宝阁时，可以让 Trae 的 piko 工具直接在页面里执行脚本取数，
省去复制 Cookie。两种模式的差别很大，先看限制：

> **piko 单次 eval 回传上限约 26KB**，也就一页列表（15 条）。所以：
> - 抽查几个号 → piko 够用
> - 全量 1.3~1.5 万条 → 必须用 Cookie 模式 `fetch-list`
>
> 另外，页面里的 JS **不能**把数据 POST 到 `http://127.0.0.1`（浏览器 Private Network Access / CSP 会拦），
> 所以 piko 模式只能靠 eval 返回值或浏览器下载落盘。

## 列表（抽查）

在**已登录的列表页**标签页执行 [piko_list.js](piko_list.js)：

- 改 `PAGE` 选页（1 页 15 条）。
- 返回 `{rows, pager}`；让 Trae 把结果保存成 `data/piko/list-<页码>.json`。

```bash
python -m yyscbg import-piko data/piko
```

`import-piko` 支持单文件或目录，文件内容是 `{rows:[...]}` 或裸数组。

## 详情（候选号精算）

在**已登录的任意藏宝阁页**执行 [piko_detail.js](piko_detail.js)，先把 `EID` / `SERVERID`
换成目标账号（列表数据里的 `eid` / `serverid`）。脚本会触发浏览器下载
`cbg_<订单号>.json`（约 8MB，落在 Chrome 下载目录）。

拿到文件后二选一：

```bash
# A. 直接读下载文件，本地精算入库
python -m yyscbg import-piko-details "C:\Users\<你>\Downloads"

# B. 只想算某几个号时，用 Cookie 模式更省事
python -m yyscbg fetch-detail --eids <订单号>
```

`import-piko-details` 能自动识别 `cbg_<订单号>.json`、`{eid, desc}`、`{eid, inventory...}` 三种结构。

## 已知坑

- 详情接口在页面里必须用 XHR；`fetch()` 会 `TypeError: Failed to fetch`。
- piko 详情页返回的是 8MB，别指望从 eval 里拿出来，一定走下载。
- 下载目录里如果有同名文件，Chrome 会加 `(1)` 后缀，eid 仍能从文件名解析。
