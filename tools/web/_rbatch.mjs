// node _rbatch.mjs  -> runs a curated list of pullpush queries with delays
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131 Safari/537.36';
const clean = s => String(s || '').replace(/\r/g, '');
const sleep = ms => new Promise(r => setTimeout(r, ms));

const JOBS = [
  ['submission', 'montage editing', 'VALORANT', 'score', 25],
  ['comment', 'montage', 'VALORANT', 'score', 25],
  ['submission', 'valorant montage', 'VideoEditing', 'score', 25],
  ['comment', 'freeze frame kill', '', 'score', 20],
  ['comment', 'speed ramp', 'VALORANT', 'score', 25],
  ['comment', 'hitmarker sound', '', 'score', 20],
  ['comment', 'ace montage', 'VALORANT', 'score', 20],
  ['submission', 'editing tips', 'VALORANT', 'score', 25],
  ['comment', 'kill effect', 'VALORANT', 'score', 25],
  ['comment', 'beat sync', 'VALORANT', 'score', 20],
];

for (const [kind, q, sub, sortType, size] of JOBS) {
  const u = `https://api.pullpush.io/reddit/search/${kind}/?q=${encodeURIComponent(q)}${sub ? '&subreddit=' + sub : ''}&size=${size}&sort=desc&sort_type=${sortType}`;
  let ok = false;
  for (let attempt = 0; attempt < 3 && !ok; attempt++) {
    try {
      const r = await fetch(u, { headers: { 'User-Agent': UA, 'Accept': 'application/json' } });
      if (r.status === 429) { console.log(`### [429 retry ${attempt}] ${kind} q="${q}" sub=${sub || 'ALL'}`); await sleep(15000); continue; }
      const j = JSON.parse(await r.text());
      const items = j.data || [];
      console.log(`\n\n########## ${kind.toUpperCase()} q="${q}" sub=${sub || 'ALL'} -> ${items.length} results ##########`);
      for (const d of items) {
        const date = new Date((d.created_utc || 0) * 1000).toISOString().slice(0, 10);
        if (kind === 'submission') {
          console.log(`\n--- [${date}] r/${d.subreddit} score=${d.score} cmts=${d.num_comments}`);
          console.log(`TITLE: ${clean(d.title)}`);
          console.log(`URL: https://www.reddit.com${d.permalink}`);
          if (d.selftext && d.selftext.length > 5) console.log(`BODY: ${clean(d.selftext).slice(0, 1800)}`);
        } else {
          console.log(`\n--- [${date}] r/${d.subreddit} score=${d.score}`);
          console.log(`URL: https://www.reddit.com${d.permalink}`);
          console.log(`TEXT: ${clean(d.body).slice(0, 1800)}`);
        }
      }
      ok = true;
      await sleep(9000);
    } catch (e) { console.log(`### ERR ${e.message} for q="${q}"`); await sleep(8000); }
  }
}
