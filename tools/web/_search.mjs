// Usage: node _search.mjs "query" [engine]
// engines: ecosia (default), yandex, baidu, marginalia, all
const q = process.argv[2];
const engine = process.argv[3] || 'ecosia';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
if (!q) { console.error('need query'); process.exit(1); }
const E = encodeURIComponent(q);

const strip = (h) => h
  .replace(/<script[\s\S]*?<\/script>/gi, ' ')
  .replace(/<style[\s\S]*?<\/style>/gi, ' ')
  .replace(/<[^>]+>/g, ' ')
  .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"')
  .replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();

async function get(u, extra = {}) {
  const r = await fetch(u, {
    headers: { 'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9', 'Accept': 'text/html,*/*', ...extra },
    redirect: 'follow',
  });
  return await r.text();
}

function ecosiaResults(html) {
  const out = [];
  const re = /<a[^>]+href="(https?:\/\/[^"]+)"[^>]*>([\s\S]{0,400}?)<\/a>/gi;
  const seen = new Set();
  for (const m of html.matchAll(re)) {
    const url = m[1];
    if (/ecosia\.org|bing\.com|microsoft\.com|w3\.org|creativecommons/.test(url)) continue;
    if (seen.has(url)) continue;
    const txt = strip(m[2]).slice(0, 160);
    if (txt.length < 12) continue;
    seen.add(url);
    out.push(`${url}\n    ${txt}`);
  }
  return out.slice(0, 30);
}

function genericLinks(html, filters = []) {
  const out = [];
  const seen = new Set();
  for (const m of html.matchAll(/<a[^>]+href="(https?:\/\/[^"]+)"/gi)) {
    const url = m[1];
    if (filters.some(f => f.test(url))) continue;
    if (seen.has(url)) continue;
    seen.add(url); out.push(url);
  }
  return out.slice(0, 60);
}

try {
  if (engine === 'ecosia' || engine === 'all') {
    const h = await get(`https://www.ecosia.org/search?q=${E}`);
    console.log('===== ECOSIA =====');
    console.log(ecosiaResults(h).join('\n'));
    if (engine === 'all') console.log('\n--- ecosia raw text ---\n' + strip(h).slice(0, 6000));
  }
  if (engine === 'yandex' || engine === 'all') {
    const h = await get(`https://yandex.com/search/?text=${E}&lr=87`);
    console.log('\n===== YANDEX =====');
    console.log(genericLinks(h, [/yandex\./, /\.yandex/, /mc\.yandex/]).join('\n'));
    console.log('--- yandex text ---\n' + strip(h).slice(0, 6000));
  }
  if (engine === 'baidu' || engine === 'all') {
    const h = await get(`https://www.baidu.com/s?wd=${E}&rn=20`);
    console.log('\n===== BAIDU =====');
    console.log(strip(h).slice(0, 6000));
  }
  if (engine === 'marginalia' || engine === 'all') {
    const h = await get(`https://search.marginalia.nu/search?query=${E}`);
    console.log('\n===== MARGINALIA =====');
    console.log(genericLinks(h, [/marginalia/, /wikipedia/, /github\.com\/Marginalia/]).join('\n'));
  }
} catch (e) { console.error('SEARCH_ERR ' + e.message); process.exit(2); }
