// node _reddit.mjs sub "query" [subreddit] [size]
// node _reddit.mjs com "query" [subreddit] [size]
// Uses pullpush.io Reddit archive (reddit.com itself is blocked on this network).
const kind = process.argv[2] === 'com' ? 'comment' : 'submission';
const q = process.argv[3];
const sub = process.argv[4] || '';
const size = process.argv[5] || '50';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131 Safari/537.36';
if (!q) { console.error('need query'); process.exit(1); }
const u = `https://api.pullpush.io/reddit/search/${kind}/?q=${encodeURIComponent(q)}${sub ? '&subreddit=' + sub : ''}&size=${size}&sort=desc`;
const r = await fetch(u, { headers: { 'User-Agent': UA, 'Accept': 'application/json' } });
console.log('// ' + u);
console.log('// status ' + r.status);
const t = await r.text();
let j; try { j = JSON.parse(t); } catch { console.log(t.slice(0, 3000)); process.exit(0); }
const items = j.data || [];
console.log('// results: ' + items.length + '\n');
const clean = s => String(s || '').replace(/\r/g, '');
for (const d of items) {
  const date = new Date((d.created_utc || 0) * 1000).toISOString().slice(0, 10);
  if (kind === 'submission') {
    console.log(`--- [${date}] r/${d.subreddit} score=${d.score} comments=${d.num_comments}`);
    console.log(`TITLE: ${clean(d.title)}`);
    console.log(`URL: https://www.reddit.com${d.permalink}`);
    if (d.selftext) console.log(`BODY: ${clean(d.selftext).slice(0, 2500)}`);
  } else {
    console.log(`--- [${date}] r/${d.subreddit} score=${d.score} by ${d.author}`);
    console.log(`LINK: https://www.reddit.com${d.permalink}`);
    console.log(`TEXT: ${clean(d.body).slice(0, 2500)}`);
  }
  console.log('');
}
