// Bilibili tools
// node _bili.mjs search "keyword" [page]
// node _bili.mjs info BVxxxx            -> description, tags, duration, subtitle list
// node _bili.mjs subs BVxxxx            -> download+print subtitle text (if any)
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
const H = { 'User-Agent': UA, 'Referer': 'https://www.bilibili.com/', 'Accept': 'application/json,text/plain,*/*' };
const mode = process.argv[2];
const arg = process.argv[3];
const page = process.argv[4] || '1';

const j = async (u) => {
  const r = await fetch(u, { headers: H, redirect: 'follow' });
  const t = await r.text();
  try { return JSON.parse(t); } catch { return { _raw: t.slice(0, 500), _status: r.status }; }
};
const clean = (s) => String(s || '').replace(/<[^>]+>/g, '').replace(/&quot;/g, '"').replace(/&amp;/g, '&');

if (mode === 'search') {
  const u = `https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword=${encodeURIComponent(arg)}&page=${page}`;
  const d = await j(u);
  console.log('code', d.code, d.message || '');
  (d.data && d.data.result ? d.data.result : []).forEach((v, i) => {
    console.log(`\n[${i + 1}] ${clean(v.title)}\n    https://www.bilibili.com/video/${v.bvid}\n    author=${v.author} dur=${v.duration} play=${v.play} date=${new Date(v.pubdate * 1000).toISOString().slice(0, 10)}\n    desc=${clean(v.description).slice(0, 300)}`);
  });
} else if (mode === 'info') {
  const d = await j(`https://api.bilibili.com/x/web-interface/view?bvid=${arg}`);
  if (d.code !== 0) { console.log('ERR', d.code, d.message); process.exit(1); }
  const v = d.data;
  console.log('TITLE:', v.title);
  console.log('URL: https://www.bilibili.com/video/' + v.bvid);
  console.log('AUTHOR:', v.owner.name, '| PUBDATE:', new Date(v.pubdate * 1000).toISOString().slice(0, 10));
  console.log('DURATION_SEC:', v.duration, '| VIEWS:', v.stat.view, '| CID:', v.cid);
  console.log('TAGS:', (v.tagname || []).join(', '));
  console.log('\nDESC:\n' + v.desc);
  const p = await j(`https://api.bilibili.com/x/player/v2?bvid=${arg}&cid=${v.cid}`);
  const sub = (p.data && p.data.subtitle && p.data.subtitle.subtitles) || [];
  console.log('\nSUBTITLES_FOUND:', sub.length);
  sub.forEach(s => console.log('  -', s.lan_doc, s.lan, '->', s.subtitle_url));
  if (!sub.length) console.log('  (none)');
} else if (mode === 'subs') {
  const d = await j(`https://api.bilibili.com/x/web-interface/view?bvid=${arg}`);
  if (d.code !== 0) { console.log('ERR', d.code, d.message); process.exit(1); }
  const p = await j(`https://api.bilibili.com/x/player/v2?bvid=${arg}&cid=${d.data.cid}`);
  const sub = (p.data && p.data.subtitle && p.data.subtitle.subtitles) || [];
  if (!sub.length) { console.log('NO_SUBTITLES for', arg); process.exit(0); }
  let url = sub[0].subtitle_url;
  if (url.startsWith('//')) url = 'https:' + url;
  const s = await j(url);
  const body = (s.body || []);
  console.log(`# ${d.data.title}\n# https://www.bilibili.com/video/${arg}\n# cues=${body.length}`);
  body.forEach(c => console.log(`[${c.from.toFixed(1)}-${c.to.toFixed(1)}s] ${c.content}`));
} else { console.log('modes: search|info|subs'); }
