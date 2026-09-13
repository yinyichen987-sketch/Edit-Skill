// Usage: node _fetch.mjs <url> [mode]
// mode: raw | text (default text) | links | json
const url = process.argv[2];
const mode = process.argv[3] || 'text';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

if (!url) { console.error('need url'); process.exit(1); }

const strip = (h) => h
  .replace(/<script[\s\S]*?<\/script>/gi, ' ')
  .replace(/<style[\s\S]*?<\/style>/gi, ' ')
  .replace(/<noscript[\s\S]*?<\/noscript>/gi, ' ')
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/<\/(p|div|li|h[1-6]|tr|br)>/gi, '\n')
  .replace(/<br\s*\/?>/gi, '\n')
  .replace(/<[^>]+>/g, ' ')
  .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"')
  .replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&mdash;/g, '-').replace(/&hellip;/g, '...')
  .replace(/[ \t]+/g, ' ')
  .replace(/\n{3,}/g, '\n\n')
  .trim();

const dec = (s) => s.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&#(\d+);/g, (m, d) => String.fromCharCode(+d));

async function go(u, depth = 0) {
  if (depth > 5) throw new Error('too many redirects');
  const res = await fetch(u, {
    headers: {
      'User-Agent': UA,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept-Encoding': 'gzip, deflate, br',
    },
    redirect: 'follow',
  });
  const body = await res.text();
  return { res, body };
}

try {
  const { res, body } = await go(url);
  console.error(`[status ${res.status}] [final ${res.url}] [len ${body.length}]`);
  if (mode === 'raw') { console.log(body); }
  else if (mode === 'links') {
    const set = new Set();
    for (const m of body.matchAll(/href="([^"]+)"/gi)) set.add(dec(m[1]));
    console.log([...set].join('\n'));
  }
  else if (mode === 'json') {
    try { console.log(JSON.stringify(JSON.parse(body), null, 1).slice(0, 40000)); }
    catch { console.log(body.slice(0, 40000)); }
  }
  else { console.log(strip(body).slice(0, 60000)); }
} catch (e) {
  console.error('FETCH_ERR ' + e.message);
  process.exit(2);
}
