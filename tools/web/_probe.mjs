// Usage: node _probe.mjs
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
const urls = process.argv.slice(2).length ? process.argv.slice(2) : [
  'https://www.youtube.com/',
  'https://www.reddit.com/',
  'https://old.reddit.com/',
  'https://www.google.com/',
  'https://en.wikipedia.org/wiki/Speed_ramp',
  'https://www.bilibili.com/',
  'https://www.zhihu.com/',
  'https://www.baidu.com/',
  'https://freesound.org/',
  'https://search.marginalia.nu/',
  'https://lite.duckduckgo.com/lite/?q=test',
  'https://www.capcut.com/',
  'https://medium.com/',
  'https://www.fandom.com/',
  'https://steamcommunity.com/',
  'https://www.riotgames.com/',
  'https://support.riotgames.com/',
  'https://www.ecosia.org/search?q=test',
  'https://search.brave.com/search?q=test',
  'https://www.startpage.com/sp/search?query=test',
  'https://yandex.com/search/?text=test',
  'https://www.qwant.com/?q=test',
  'https://searx.be/search?q=test',
  'https://www.pinterest.com/',
  'https://vimeo.com/',
  'https://www.tiktok.com/',
];
const out = [];
await Promise.all(urls.map(async (u) => {
  const t0 = Date.now();
  try {
    const ctl = new AbortController();
    const to = setTimeout(() => ctl.abort(), 15000);
    const r = await fetch(u, { headers: { 'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9' }, redirect: 'follow', signal: ctl.signal });
    clearTimeout(to);
    const b = await r.text();
    out.push(`OK   ${r.status} len=${String(b.length).padEnd(8)} ${Date.now() - t0}ms  ${u}`);
  } catch (e) {
    out.push(`FAIL ${(e.cause && e.cause.code) || e.name} :: ${u}`);
  }
}));
out.sort().forEach(l => console.log(l));
