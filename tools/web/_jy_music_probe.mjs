// 探测剪映（JianyingPro）云曲库接口是否可从本机访问。
// 端点名取自本机 VECreator.dll 的字符串表（第一方证据）：
//   /lv/v1/search/songs · /lv/v1/get_collections · /lv/v1/get_collection_songs
//   /lv/v1/music/similar_music_rec · /lv/v1/pc/aweme_collection_songs
// 用法: node tools\web\_jy_music_probe.mjs
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

const HOSTS = [
  'https://lv-api.ulikecam.com',
  'https://lv-pc-api.ulikecam.com',
  'https://lv-pc-api-sinfonlinea.ulikecam.com',
];

const CALLS = [
  ['POST', '/lv/v1/search/songs', { query: '卡点', count: 20, cursor: 0 }],
  ['POST', '/lv/v1/get_collections', { count: 20, cursor: 0 }],
  ['GET', '/lv/v1/get_collections?count=20&cursor=0', null],
  ['POST', '/lv/v1/get_collection_songs', { collection_id: '0', count: 20, cursor: 0 }],
  ['POST', '/lv/v1/music/similar_music_rec', { music_id: '0', count: 20 }],
];

const out = [];
for (const host of HOSTS) {
  for (const [method, path, body] of CALLS) {
    const t0 = Date.now();
    try {
      const ctl = new AbortController();
      const to = setTimeout(() => ctl.abort(), 12000);
      const r = await fetch(host + path, {
        method,
        headers: {
          'User-Agent': UA,
          'Accept': 'application/json, text/plain, */*',
          'Content-Type': 'application/json',
          'Origin': 'https://www.jianying.com',
          'Referer': 'https://www.jianying.com/',
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: ctl.signal,
      });
      clearTimeout(to);
      const txt = await r.text();
      out.push(`${String(r.status).padEnd(4)} ${String(Date.now() - t0).padStart(5)}ms ${method} ${host}${path}\n      ${txt.slice(0, 400).replace(/\s+/g, ' ')}`);
    } catch (e) {
      out.push(`FAIL         ${method} ${host}${path} :: ${(e.cause && e.cause.code) || e.name}`);
    }
  }
}
out.forEach(l => console.log(l));
