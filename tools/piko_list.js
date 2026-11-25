// piko 取数脚本（列表页）：在已登录藏宝阁的列表页标签页里执行。
// 返回 {rows:[...]}，字段名保持藏宝阁原始命名，交给 `python -m yyscbg import-piko`。
//
// 注意：piko 单次 eval 回传上限约 26KB（约一页多一点），所以这里默认一次只取 1 页。
// 要抓全量请用 Cookie 模式（python -m yyscbg fetch-list），piko 只适合抽查。
(async () => {
  const PAGE = 1;

  const post = (body) =>
    new Promise((resolve) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', 'https://yys.cbg.163.com/cgi-bin/recommend.py?client_type=h5&act=recommd_by_role');
      xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
      xhr.onload = () => resolve(xhr.responseText);
      xhr.onerror = () => resolve('{}');
      xhr.send(body);
    });

  const payload = JSON.parse(await post(`page=${PAGE}&search_type=role`));
  const rows = (payload.result || []).map((item) => ({
    eid: item.eid,
    // 详情接口只认 game_ordersn，务必一起带回去
    game_ordersn: item.game_ordersn,
    serverid: item.serverid,
    price: item.price,
    area_name: item.area_name,
    server_name: item.server_name,
    platform_desc: item.platform_desc,
    equip_level: item.equip_level,
    status: item.status,
    collect_num: item.collect_num,
    selling_time: item.selling_time,
    highlights: item.highlights || [],
    desc_sumup_short: item.desc_sumup_short || '',
    diy_desc: item.diy_desc || '',
    top_heros: ((item.other_info && item.other_info.top_heros) || []).map((hero) => ({
      name: hero.name,
      heroId: hero.heroId,
      add_speed_not_display: hero.add_speed_not_display,
      strike_not_display: hero.strike_not_display,
      strike_damage_not_display: hero.strike_damage_not_display,
    })),
  }));

  return JSON.stringify({ rows, pager: payload.pager });
})()
