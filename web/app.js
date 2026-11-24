const state = { limit: 48, offset: 0, total: 0, thresholds: {} };

const $ = (id) => document.getElementById(id);

const num = (value) => (value === null || value === undefined || value === "" ? null : Number(value));
const fmt = (value, digits = 2) => (value === null || value === undefined ? "—" : Number(value).toFixed(digits));
const money = (value) => (value === null || value === undefined ? "—" : "¥" + Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 0 }));

function buildQuery() {
  const params = new URLSearchParams();
  const map = {
    minPrice: "minPrice", maxPrice: "maxPrice", minSpeed: "minSpeed", minLucky: "minLucky",
    minHead: "minHead", minPvp: "minPvp", minSixStar: "minSixStar", minFengzidu: "minFengzidu",
    keyword: "keyword",
  };
  for (const [id, key] of Object.entries(map)) {
    const value = $(id).value.trim();
    if (value !== "") params.set(key, value);
  }
  params.set("sort", $("sort").value);
  params.set("desc", $("direction").value);
  params.set("limit", String(state.limit));
  params.set("offset", String(state.offset));
  return params;
}

function chip(text) {
  const span = document.createElement("span");
  span.className = "chip";
  span.textContent = text;
  return span;
}

function badge(kind, text) {
  const span = document.createElement("span");
  span.className = `badge ${kind}`;
  span.textContent = text;
  return span;
}

function metric(label, value) {
  const box = document.createElement("div");
  box.className = "metric";
  box.innerHTML = `<span>${label}</span><b>${value}</b>`;
  return box;
}

function renderCard(item) {
  const card = document.createElement("article");
  card.className = "card";
  card.onclick = () => openDetail(item.eid);

  const head = document.createElement("div");
  head.className = "card-head";
  head.innerHTML = `<div class="price">${money(item.price)}</div><div class="server">${item.area || ""} · ${item.server || ""}</div>`;
  card.appendChild(head);

  const metrics = document.createElement("div");
  metrics.className = "metrics";
  metrics.appendChild(metric("散件一速", fmt(item.scatter_speed)));
  metrics.appendChild(metric("招财一速", fmt(item.lucky_speed)));
  metrics.appendChild(metric("头 / 尾", `${item.head_cnt ?? "—"} / ${item.tail_cnt ?? "—"}`));
  metrics.appendChild(metric("斗技分", item.pvp_score ?? "—"));
  metrics.appendChild(metric("六星式神", item.six_star_cnt ?? "—"));
  metrics.appendChild(metric("风姿度", item.fengzidu ? Number(item.fengzidu).toLocaleString("zh-CN") : "—"));
  card.appendChild(metrics);

  const tags = document.createElement("div");
  tags.className = "hl";
  (item.tags || []).slice(0, 5).forEach((text) => tags.appendChild(chip(text)));
  if (item.diy_desc) tags.appendChild(chip(item.diy_desc.slice(0, 22)));
  card.appendChild(tags);
  return card;
}

async function load() {
  const res = await fetch("/api/accounts?" + buildQuery().toString());
  const data = await res.json();
  state.total = data.total;
  const grid = $("grid");
  grid.innerHTML = "";
  if (!data.items.length) {
    grid.innerHTML = '<div class="empty">没有匹配的账号。先运行 <code>python -m yyscbg fetch-list</code> 抓一轮数据，或放宽条件。</div>';
  } else {
    data.items.forEach((item) => grid.appendChild(renderCard(item)));
  }
  $("count").textContent = `共 ${data.total.toLocaleString("zh-CN")} 个账号`;
  const from = data.total ? state.offset + 1 : 0;
  const to = Math.min(state.offset + state.limit, data.total);
  $("pageInfo").textContent = `当前 ${from}–${to}`;
  $("prev").disabled = state.offset === 0;
  $("next").disabled = to >= data.total;
}

async function loadStats() {
  const res = await fetch("/api/stats");
  const data = await res.json();
  state.thresholds = data.thresholds || {};
  const parts = [`在售 ${Number(data.listings || 0).toLocaleString("zh-CN")} 条`];
  if (data.details) parts.push(`已精算 ${data.details} 个`);
  parts.push(`更新于 ${data.lastSeen || "—"}`);
  parts.push(`达标线 ${state.thresholds.panel_pass} / 毕业 ${state.thresholds.panel_grad}`);
  $("statLine").textContent = parts.join(" · ");
}

async function openDetail(eid) {
  const drawer = $("drawer");
  const body = $("drawerBody");
  body.innerHTML = '<div class="empty">加载中…</div>';
  drawer.hidden = false;
  const res = await fetch("/api/account/" + encodeURIComponent(eid));
  const data = await res.json();
  if (data.error) { body.innerHTML = '<div class="empty">未找到该账号</div>'; return; }
  const item = data.listing;
  $("drawerTitle").textContent = `${money(item.price)} · ${item.server || ""}`;

  const sections = [];
  sections.push(`
    <div class="section">
      <h3>基础信息</h3>
      <div class="kv">
        <div><span>区服</span><span>${item.area || "—"} / ${item.server || "—"}</span></div>
        <div><span>等级</span><span>${item.level ?? "—"}</span></div>
        <div><span>SSR</span><span>${item.ssr_cnt ?? "—"}</span></div>
        <div><span>六星式神</span><span>${item.six_star_cnt ?? "—"}</span></div>
        <div><span>签到</span><span>${item.sign_days ?? "—"} 天</span></div>
        <div><span>风姿度</span><span>${item.fengzidu ?? "—"}</span></div>
        <div><span>散件一速</span><span>${fmt(item.scatter_speed)}</span></div>
        <div><span>招财一速</span><span>${fmt(item.lucky_speed)}</span></div>
        <div><span>头 / 尾</span><span>${item.head_cnt ?? "—"} / ${item.tail_cnt ?? "—"}</span></div>
        <div><span>斗技分</span><span>${item.pvp_score ?? "—"}</span></div>
        <div><span>收藏</span><span>${item.collect ?? 0}</span></div>
        <div><span>商品编号</span><span>${item.eid}</span></div>
      </div>
    </div>`);

  if (item.diy_desc) {
    sections.push(`<div class="section"><h3>资产</h3><div>${item.diy_desc}</div></div>`);
  }
  if ((item.top_heros || []).length) {
    const rows = item.top_heros.map((hero) => `<tr><td>${hero.name || ""}</td><td class="num">${hero.speed ?? "—"}</td><td class="num">${hero.crit ?? "—"}</td><td class="num">${hero.critDamage ?? "—"}</td></tr>`).join("");
    sections.push(`<div class="section"><h3>列表页展示式神面板（速度 / 暴击 / 爆伤）</h3>
      <table><thead><tr><th>式神</th><th class="num">速度</th><th class="num">暴击</th><th class="num">爆伤</th></tr></thead><tbody>${rows}</tbody></table></div>`);
  }

  const metrics = data.metrics;
  if (!metrics) {
    sections.push(`<div class="section"><h3>PVE 精算</h3><div class="empty">尚未精算。运行
      <code>python -m yyscbg fetch-detail --eids ${item.eid}</code> 后刷新本页。</div></div>`);
  } else {
    const speed = metrics.speed || {};
    const pve = metrics.pve || {};
    const suitRows = (speed.suitSpeeds || []).slice(0, 8)
      .map((row) => `<tr><td>${row.suit}</td><td class="num">${fmt(row.speed)}</td></tr>`).join("");
    sections.push(`
      <div class="section"><h3>御魂概览</h3>
        <div class="kv">
          <div><span>御魂总数</span><span>${speed.relicTotal ?? "—"}</span></div>
          <div><span>6星满级</span><span>${speed.maxLevelCount ?? "—"}</span></div>
          <div><span>满速御魂</span><span>${speed.fullSpeedCount ?? "—"}</span></div>
          <div><span>散件一速</span><span>${fmt(speed.scatter && speed.scatter.speed)}</span></div>
          <div><span>招财一速</span><span>${fmt(speed.lucky && speed.lucky.speed)}</span></div>
          <div><span>命中一速</span><span>${fmt(speed.hit && speed.hit.speed)}</span></div>
          <div><span>抵抗一速</span><span>${fmt(speed.resist && speed.resist.speed)}</span></div>
        </div>
        <table style="margin-top:8px"><thead><tr><th>四件套</th><th class="num">一速</th></tr></thead><tbody>${suitRows}</tbody></table>
      </div>`);

    const summary = pve.summary || [];
    if (summary.length) {
      const rows = summary.map((row) => {
        const kind = row.badge === "毕业" ? "grad" : row.badge === "达标" ? "pass" : "fail";
        return `<tr><td>${row.suit}</td><td class="num">${row.best}</td><td class="num">${row.average}</td><td>${badge(kind, row.badge)}</td></tr>`;
      }).join("");
      sections.push(`<div class="section"><h3>PVE 输出面板（${metrics.hero || "输出式神"}，满暴，4 件套 × 首领魂最优）</h3>
        <table><thead><tr><th>四件套</th><th class="num">最高</th><th class="num">平均</th><th>判定</th></tr></thead><tbody>${rows}</tbody></table>
        <div style="margin-top:8px">综合参考：<b>${pve.overall ?? "—"}</b> ${pve.badge ? badge(pve.badge === "毕业" ? "grad" : pve.badge === "达标" ? "pass" : "fail", pve.badge) : ""}</div>
      </div>`);
    }

    const ranking = metrics.pveScoreRanking || [];
    if (ranking.length) {
      const rows = ranking.map((row) => `<tr><td>${row.suit}${row.isOma ? "（首领）" : ""}</td><td class="num">${row.total}</td><td class="num">${row.count}</td></tr>`).join("");
      sections.push(`<div class="section"><h3>PVE 有效强化评分</h3>
        <table><thead><tr><th>御魂</th><th class="num">总分</th><th class="num">件数</th></tr></thead><tbody>${rows}</tbody></table></div>`);
    }
  }

  body.innerHTML = sections.join("");
}

$("apply").onclick = () => { state.offset = 0; load(); };
$("reset").onclick = () => {
  ["minPrice", "maxPrice", "minSpeed", "minLucky", "minHead", "minPvp", "minSixStar", "minFengzidu", "keyword"].forEach((id) => { $(id).value = ""; });
  state.offset = 0; load();
};
$("prev").onclick = () => { state.offset = Math.max(0, state.offset - state.limit); load(); };
$("next").onclick = () => { state.offset += state.limit; load(); };
$("closeDrawer").onclick = () => { $("drawer").hidden = true; };
$("sort").onchange = () => { state.offset = 0; load(); };
$("direction").onchange = () => { state.offset = 0; load(); };

loadStats();
load();
