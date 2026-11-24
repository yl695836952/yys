// piko 取数脚本（账号详情）：在已登录藏宝阁的标签页里执行。
//
// 详情接口单个账号约 8MB，piko 单次回传只有 ~26KB，所以这里直接触发浏览器下载，
// 文件会落在 Chrome 的下载目录（形如 cbg_<订单号>.json）。
// 下载后执行：python -m yyscbg fetch-detail --eids <订单号>
// 或把文件转成 {eid, desc} 结构后用 import-piko-details 离线精算。
(async () => {
  const EID = '202611202001616-16-4S0QIIC2VYCKE';
  const SERVERID = 16;

  const raw = await new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', `https://yys.cbg.163.com/cgi/api/get_equip_desc?serverid=${SERVERID}&ordersn=${EID}`);
    xhr.onload = () => resolve(xhr.responseText);
    xhr.onerror = () => resolve('');
    xhr.send();
  });

  if (!raw) return { ok: false, reason: '接口无返回，检查登录态' };

  const blob = new Blob([raw], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `cbg_${EID}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  setTimeout(() => {
    anchor.remove();
    URL.revokeObjectURL(url);
  }, 4000);

  return { ok: true, bytes: raw.length, file: `cbg_${EID}.json`, eid: EID, serverid: SERVERID };
})()
