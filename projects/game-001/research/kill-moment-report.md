# VALORANT / 无畏契约 kill-moment treatment — research report

Scope: how top VALORANT montage editors handle the **kill moment**, expressed as measurable
rules. Every claim carries a source. Numbers I could not source are listed as unsourced,
not guessed.

**Evidence tiers used below**

| Tier | Meaning |
|---|---|
| **L1** | First-hand measurement in this workspace (frames/audio decoded from real files) |
| **L2** | Read directly off the 剪映专业版 UI in frames extracted from 17 downloaded B站 tutorials |
| **L3** | Second-hand web / prior-session claim, flagged |
| **L4** | Workspace project prior art (this repo's own EDL/tool decisions) |

Local evidence assets produced this round:
`projects/game-001/research/killmoment.json`, `killmoment2.json`,
`projects/game-001/research/_scratch/REPORT.md` (L2 detail),
`projects/game-001/research/_hud/` (contact sheets + rulers).

---

## 1. Technique table

| technique | what it looks like | when to use | timing numbers | source |
|---|---|---|---|---|
| **定格 freeze frame** | The kill frame is held completely still, then motion resumes | Emphasis on a single decisive instant / reaction | 剪映 default **3 s** (must be shortened by hand). Measured in real montages: exact-duplicate runs **median 216 ms, IQR 119–326 ms, range 100–1628 ms**; the two short montages **median 167–170 ms (~5 frames @30fps)**. ⚠️ **UPPER BOUND** — the detector also fires on genuinely static source moments (see §2) | L2: 剪映 default 3 s read off frames + Zhihu title 「剪映定格默认是3秒」 (1.7万 views). L1: `killmoment2.json` |
| **曲线变速 speed ramp** | Slow-motion running into the kill, snapping back to normal/fast after | Almost every kill in a montage — the core "kill" device | Panel: **画面 → 变速 → 曲线变速**. Presets: **蒙太奇 / 英雄时刻 / 子弹时间 / 跳接 / 闪进 / 闪出**. The one used on 瓦 kills is **闪进**. Standard kill slow-mo multiplier **0.1×** (4 independent videos). **20× (二十倍速)** used in the 五杀 tutorial. ⚠️ Some builds put **变速** as a top-level tab (画面｜变速｜动画｜调节｜AI效果) instead | L2: frame `BV1FJeRzZEtY` t≈42 s, crop `_scratch/crop_presets.jpg`; version variance seen across 2025–26 videos |
| **闪白 white flash** | One-to-few frames of blown-out white over the cut/kill | Hiding a cut, punching a kill | Measured flash events: **median 50–167 ms**; most common **33 ms / 67 ms / 133 ms** (1/2/4 frames @30fps); observed up to 367 ms | L1: `killmoment2.json`. L2: 闪白 = **媒体 → 官方素材 → 白场** (a white-frame asset, *not* a brightness effect) |
| **黑场 black dip** | Short near-black gap | Separating beats, resetting attention | Measured **33–600 ms** (`BV19m3uzhECJ` had 333 ms and 600 ms events) | L1 `killmoment2.json`; L2: 媒体 → 官方素材 → **黑场** |
| **抖动 / 震动 screen shake** | Frame jolts on impact | Kill / heavy hit impact | Named effects: **回弹摇摆, 左右晃动, 晃动模糊, 缩放震荡, 摇晃黑, 旋转黑, 黑光聚点, 瞬间模糊, 抖动模糊, 发光, 边缘发光, 丁达尔聚焦, 旋转变焦, 震动闪烁, 暗角, 跟随运镜**. Params exposed: **速度 / 大小**. Explicit on-screen recipe: 特效 → 画面特效 → search **「交叉闪震」**, then 「缩短成只有一个震当转场用」 + 变速 0.1× | L2: frames `BV1FJeRzZEtY` t≈54 s, `BV1G1r6BuEsF` |
| **击杀卡片 kill card** | Kill frame duplicated, masked, held | Highlighting one kill with an inset | Duplicate clip → **画面 → 蒙版** (线性/镜面/圆形/矩形/爱心/星形) + 羽化/圆角; each masked clip shown as **000:03:00**; 变速 **0.1×** | L2: `BV1HVe8zRE5m` |
| **曝光 / 发光 bloom-flash** | Kill frame brightens/blooms | Kill punch, "clutch" feel | 调节 → **基础｜HSL｜曲线｜色轮｜蒙版** → 亮度/对比度/高光/阴影/白色/黑色/光感. 发光 defaults **发光强度 40 / 滤镜 20 / 光束角度 40** | L2: `BV11hdSYcENH` |
| **Align to the muzzle flash, not the kill feed** | Cut/impact lands on the shot, not the announcement | Every kill cut | Kill feed/播报 appears **≈0.2–0.5 s after** the actual shot; align to the **orange muzzle flash** instead. This workspace's EDL therefore uses `PRE = 0.6 s` | L4: `projects/game-001/tools/build_by_exclusion.py` L24–29 (cites a Rocklan After Effects tutorial). ⚠️ The Rocklan URL itself was not re-fetched this round |
| **Multikill counter overlay** | Scoreboard-style `2 KILLS` plate | 2K+ | Placed **top-right**, black plate + white text, inside the upper 210 px band | L4: `projects/game-001/tools/make_montage_edl.py` L222–237 |
| **Kill-cluster gate (shot selection)** | Only shoot clusters of ≥2 own kills | Assembling a montage | `MIN_KILLS = 2`; merge single kills into a neighbour; kill-lead **`KILL_LEAD_BEATS = 2`** beats before the kill; mute-gap threshold **`GAP = 3.0 s`** (no segment may be below **0.25 kills/s**) | L4: `rebuild_blocks.py`, `make_bili_montage.py`, `build_by_exclusion.py` |
| **Sound: kill vocabulary** | whoosh / riser / sub-drop / impact | Transitions and payoffs | 剪映: **音频 → 音效 → 搜索关键词 → 使用**. whoosh **0.35 s**, riser **1.80 s**, sub_drop **0.90 s**; impact from own footage | L4: `make_sfx.py` (it also records that 剪映's 音效库 **cannot be referenced programmatically**). L2: book-sourced workflow 《剪映短视频制作全流程》(keyword 「拍照声」) |

### Standard vs advanced (as judged from the two short high-view montages)

- **Standard**: hard cut + 曲线变速 (闪进) into the kill; align cut to the shot not the feed.
- **Advanced / less universal**: exact 定格 on the kill frame, masked 击杀卡片, bloom exposure flash,
  shake composites (交叉闪震), 黑场 dips. These appear in *some* high-view montages but are not
  present in all of them.

---

## 2. Quantified rules I could find

Only numbers with a traceable source. Nothing here is invented.

| # | Rule | Value | Source | Confidence |
|---|---|---|---|---|
| Q1 | Freeze-frame hold in real montages | median **216 ms**; IQR 119–326 ms; range 100–1628 ms (n=34, 6 videos) | L1 `killmoment2.json` | **Medium — UPPER BOUND** |
| Q2 | Freeze hold, two short high-view montages only | median **167–170 ms** ≈ **5 frames @30fps**; range 100–600 ms | L1 `killmoment2.json` | Medium |
| Q3 | 剪映 定格 default duration | **3 s** (must be manually shortened) | L2 Zhihu title + frames | High (that it *is* 3 s); Low (that editors keep it) |
| Q4 | Kill slow-motion multiplier | **0.1×** | L2, 4 independent tutorials | High |
| Q5 | White-flash duration | median **50–167 ms**; commonest **33 / 67 / 133 ms** | L1 `killmoment2.json` | High (that it occurs at these lengths) |
| Q6 | Black-dip duration | **33–600 ms** | L1 `killmoment2.json` | Medium |
| Q7 | Kill-feed lag behind the shot | **≈0.2–0.5 s** | L4 `build_by_exclusion.py` L28 | Medium (inherited, not re-measured) |
| Q8 | Colour/UI change on the detected kill banner | magenta dominance **0.017**, high-freq **5.82** (vs scoreboard overlay 0.0000 / 0.34) | Parent's first-hand measurement | High |
| Q9 | Repeated-frame appearance rate | **14.8–36.5 / min** (short montages) | L1 `killmoment.json` | Low — same upper-bound caveat |
| Q10 | Mute-gap threshold in this project's kill-cluster rule | **3.0 s**, i.e. **≥0.25 kills/s** | L4 `build_by_exclusion.py` L42–45 | High (as project policy) |

**Explicitly NOT substantiated — do not use.** Three numbers appeared as *examples* in the task
brief and **no source for any of them could be found**: 「闪白 0.1 秒」, 「cut 后 3 帧」,
「变速 0.5 秒前开始」. The nearest real data is a **speed multiplier** (0.1×), not a duration.
They should be treated as fabricated until measured.

---

## 3. HUD region coordinates

Short version only — the parent now owns first-hand HUD measurement.

**Source footage in this repo is 1280x720.** 1080p = exact **×1.5** (1920/1280 = 1080/720 = 1.5).

| Region | @1280x720 | @1920x1080 (×1.5) | Source |
|---|---|---|---|
| Top-right kill feed (播报) search window | x **950–1270**, y **18–76** (`crop=320:58:950:18`) | x **1425–1905**, y **27–114** | L4 `tools/detect_kills.py` L56, `measure_kill_edit.py` L78 |
| — as normalised fractions | x0 **0.7422**, y0 **0.0250**, w **0.2500**, h **0.0806** | same fractions | L4 `tools/measure_kill_edit.py` L78 |
| Kill feed bright-text extent I measured | x **908–1256**, y **8–110** (up to 3 rows) | x **1362–1884**, y **12–165** | L1 my own near-white-text detection |
| Bottom kill-effect banner | ❌ `crop=1280:120:0:600` (y600–720) is **WRONG** — it is mostly ability/ammo/economy HUD and catches only the banner's bottom ~14 px | — | Parent's first-hand pixel measurement |
| Bottom kill-effect banner — **corrected** | banner occupies **y 522–613** (peak row 523, magenta/purple, x 380–900); corrected band **`crop=1280:100:0:520`** (y520–620) | y **783–920**; band y **780–930** | Parent's first-hand measurement |

**Two cautions that matter more than the numbers:**

1. **`detect_kills.py`'s bottom band is wrong** (per the parent). Its "kill" at `4b0460c4`
   `16.733 s` is actually the **tactical scoreboard overlay** appearing, not a kill. The
   project-wide own-kill count changes **61 → 53** once corrected.
2. **The same detector's "bottom ∩ top-right" rule is a CUT detector, not a kill detector, on
   edited montages.** A hard cut lights up both regions simultaneously. The rule is only valid
   on *unedited* source footage. This is documented in `measure_kill_edit.py` L206–218 and is
   why that tool rejects candidates within ±0.25 s of a cut.
3. High-level montages often **crop or cover the HUD entirely** (especially vertical versions) or
   use spectator/replay views, so a fixed 720p calibration does **not** transfer to reference films
   (`measure_kill_edit.py` L31–34).

**My own failure, stated plainly:** I could not automatically isolate the bottom red kill-banner
plate. Every colour/shape test I tried was contaminated by the red damage vignette, the player's
brown gloved hand, and the ability-icon glow. I verified one false positive visually
(`_hud/badge_ref.png` — the "red" was ability-icon glow). The parent's manual pixel measurement
above supersedes my attempt.

---

## 4. Reachable vs blocked hosts (measured this session)

**Transport:** `Invoke-WebRequest`, `curl.exe` and .NET HttpClient all **fail on HTTPS**
(`schannel: AcquireCredentialsHandle failed (SEC_E_NO_CREDENTIALS)`; curl exit 35 / HTTP 000).
Plain **HTTP works**. **Node.js v24 works** (own OpenSSL) — helpers now at `tools/web/_fetch.mjs`,
`_search.mjs`, `_probe.mjs`, `_bili.mjs`.

**No working general web search engine exists from this machine.** `web_search`, `read_page`,
`web_fetch` and `modlens` were all broken. Bing (`cn.bing.com?ensearch=1`) returns HTTP 200 but
**ignores long-tail query terms** (a "speed ramp tutorial" query returned speedtest.net). Bing RSS
same. DDG (html+lite), all 12 SearXNG mirrors, Google, Brave/Startpage/Qwant: blocked.

**Reachable:** bilibili.com, zhihu.com, baidu.com, capcut.com, riotgames.com, support.riotgames.com,
playvalorant.com, wiki.playvalorant.com (403 bot-gate), liquipedia.net, freesound.org,
search.marginalia.nu, cn.bing.com, example.com.

**Blocked (connect timeout):** youtube.com, reddit.com, old.reddit.com, google.com,
en.wikipedia.org, medium.com, fandom.com, steamcommunity.com, vimeo.com, pinterest.com, tiktok.com.
**Captcha/antibot:** Yandex, Mojeek, Baidu, disroot SearXNG.
**Defunct:** `blog.iflux.art` (NXDOMAIN — the primary source cited by this repo's 53 knowledge cards).

**Consequence:** YouTube and Reddit — where most VALORANT montage tutorials live — are
**unreachable**. All usable technique evidence came from **Bilibili** (via yt-dlp on direct video
URLs; note `bilisearch` returned HTTP 412) plus this workspace's own footage.

---

## 5. Could not verify

1. **True editorial freeze duration.** My exact-duplicate detector cannot separate a deliberate
   定格 effect from a genuinely static source moment. I confirmed one such run
   (`BV1U1kJBrEd7` @ 7.97–8.60 s) is a **static spectator shot of a stationary agent**, not an
   effect. Browser `measure_kill_edit.py` L44–54 documents the same unresolved problem.
   → Q1/Q2 are **upper bounds**, not measured editorial values.
2. **Per-kill attribution.** I measured freeze/flash events and, separately, kill times in the
   *source* footage — but the reference montages are heavily re-timed and use spectator views, so
   I could not prove that any given freeze sits *on* a kill. The "freeze − nearest audio transient"
   offsets in `killmoment.json` are therefore **not** evidence of alignment.
3. **Cut density of the reference montages.** Frame-difference cut detection is unreliable on
   continuous FPS footage (median "shot length" came out as 34 ms = 1 frame, i.e. detecting motion).
   This is a known failure mode here (`projects/game-001/analysis/summary.md` D2). I dropped the
   numbers rather than launder them.
4. **ACE / 五杀 differentiated treatment.** Only **one** 五杀 tutorial was found
   (`BV1xQf3BWEEz`, 320 plays) and it yielded no ACE-specific effect chain. **No 3K/4K vs ACE
   differentiated ruleset was found anywhere.** The only ACE-adjacent local evidence is a
   caption vocabulary note ("大号冲击词 ACE/CLUTCH", `make_montage_edl.py` L102).
5. **剪映 built-in kill sounds.** No source shows 剪映's 音效 library returning kill sounds for
   keywords 击杀/爆头/重低音. On-screen evidence says 瓦 creators source 枪声/击杀音效
   **externally** ("后期枪声我会发在素材群里").
6. **VALORANT's own in-game audio cues** (headshot ding, kill confirm) — I did not isolate or
   time these; no measurement was made.
7. **The Rocklan tutorial** cited for the "align to muzzle flash" rule
   (`build_by_exclusion.py`) was **not re-fetched** this round; its URL is not recorded in the repo.
8. **剪映 "5 keymap schemes"** — `operations.md` states this from local config files, but the
   web subagent found no corroborating source; treat as first-party-only.
9. **Colour-flash / chromatic-aberration pulse** as a distinct *kill* device — not found as a named
   technique; the closest verified items are 曝光/发光 and 闪白.
10. **Any playback/like performance claim** for any technique. No such data was sourced, consistent
    with this repo's existing stance (`format-research.md` §10).
11. **English-language technique sources (YouTube / Reddit).** An EN-language search was attempted
    and **produced no usable material before being stopped**. Its target hosts are blocked from
    this machine (§4), so **every technique claim in this report rests on Bilibili evidence or
    first-hand measurement** — there is no English-language corroboration for any of it.
    Treat the technique table as sourced to a *Chinese-language and local* evidence base, not a global one.
