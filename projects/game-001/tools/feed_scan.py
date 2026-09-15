"""击杀横幅（top-right kill feed）逐帧扫描 —— 第 10 轮补充（第二版判据）。

## 为什么换这个区域

第 7 轮把「击杀横幅」找在**底部 y522~613**（结论：那里是武器皮肤检视/技能图标），
洋红目标定在中部 `x380..900, y500..625`。**本轮机上看图后修正了区域**：

`b61cc53d` 的击杀横幅在 **右上角 `x≈880..1280, y≈56..82`**，内容是
`[击杀者头像] 我 [白色武器剪影] 被击杀者名`，与 VALORANT 原生 HUD 一致（L1，逐帧看图）。

## 第一版判据为什么失败（留着当教训）

第一版用「本帧 vs 0.5s 前」的平均绝对差（MAD）找突变 —— **失败**：
该区域被全屏特效（洋红/白闪）整片改写，MAD 峰值全部落在特效上（6.9s / 19.33s），
一个真正的横幅事件都没抓到（sigma=6 时 0 个事件）。

## 第二版判据：白色剪影占比的「阶梯」

横幅里那块**白色武器剪影**在灰度上极亮（R,G,B 均 > 235），而游戏画面里几乎不出现这种纯白块。
于是量 `white = #(像素三通道都>235) / 区域面积`：

- 有一条播报时 `white ≈ q`（本录制尺度下 **q ≈ 0.029**，L1 实测）；没有播报时 ≈ 0；
- **`FEED` 这条 26px 带只盖得住播报的「第一行」**（y56~82），而**新条目是从下往上追加的**
  （最新在最下、最旧在最上，L1 逐帧看图：`4b0460c4_t14.93_full.png` 有两行，
  下一行是 14.400s 才出现的）；
- ⇒ **本工具的「上升沿」= 播报由「空」变「非空」，即某一批播报里的第一次击杀**
  （也可来自条目过期时的整体上移）。**它不等于「每一次击杀」**：

  | 情况 | 带内 white | 是否产生事件 |
  |---|---|---|
  | 播报为空 → 来了第一条 | 0 → q | ✅ |
  | 播报已有 n 条 → 又来了新的一条（追加在下面） | ≈ q 不变 | ❌ **漏** |
  | 播报非空 → 条目过期整体上移（出现短暂空隙） | q → 0 → q | ⚠️ **可能假报** |

  ⇒ 实测：`4b0460c4` 14.4~16.2s 画面里**有两条**播报，带内 white 全程 ≈ 1 个 q（**漏掉一次**）。

对 `white` 按 q 量化 + 5 帧中值滤波去抖，取**上升沿**作为「横幅事件」。

> ⚠️ **`level`（= white/q 量化值）不要读成「条目数」**：带内只放得下一行，
> `level ≥ 2` 只出现 1~15 帧（b61cc53d 全片 15 帧），是动画重叠，不是第二条播报。
> 想数「有几条」需要按行做跟踪/模板匹配，**本轮没做**（见
> `verification/feed-scan/README.md` §0 与 §7）。

## 诊断模式：`rows`

把 `FEED` 带再切成**逐行带**（默认 2 行 × 26px），打印每一行自己的阶跃变化 ——
用来复现上面那条「新条目追加在下面 ⇒ 第一行不变」的结论：

    .venv\\Scripts\\python.exe projects/game-001/tools/feed_scan.py 4b0460c4 --rows

## 用法

    .venv\\Scripts\\python.exe projects/game-001/tools/feed_scan.py b61cc53d
    .venv\\Scripts\\python.exe projects/game-001/tools/feed_scan.py all
    .venv\\Scripts\\python.exe projects/game-001/tools/feed_scan.py x --cross   # 与音频瞬态做汇总检验

输出：projects/game-001/verification/feed-scan/<short>.json
      projects/game-001/verification/feed-scan/cross-audio.json（--cross）
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import subprocess
import sys

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
A2 = ROOT / "projects" / "game-001" / "analysis2"
AUDIO_DIR = ROOT / "projects" / "game-001" / "verification" / "audio-signal"
OUTDIR = ROOT / "projects" / "game-001" / "verification" / "feed-scan"
ICON_DIR = ROOT / "projects" / "game-001" / "verification" / "icon-scan"

FPS = 30.0
FEED = (880, 56, 400, 26)   # x, y, w, h（w/h 必须是偶数：ffmpeg 会改写奇数边）
WHITE = 235                 # 「纯白剪影」阈值
Q = 0.029                   # 一个横幅条目的白色占比（本录制尺度，L1 实测）
SMOOTH = 5                  # 中值滤波窗（帧）


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def read_region(path, region=FEED):
    x, y, w, h = region
    cmd = [ffmpeg_exe(), "-v", "error", "-i", str(path),
           "-vf", f"crop={w}:{h}:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    if len(raw) % (w * h * 3):
        raise SystemExit(f"[FAIL] 帧字节数 {len(raw)} 不是 {w}x{h}x3 的整数倍 —— "
                         f"ffmpeg 很可能改写了裁剪尺寸（奇数边），请先把 w/h 调成偶数")
    n = len(raw) // (w * h * 3)
    return np.frombuffer(raw, dtype=np.uint8).reshape(n, h, w, 3), n


def white_series(path, region=FEED):
    frames, n = read_region(path, region)
    return ((frames > WHITE).all(axis=3)).mean(axis=(1, 2))


def banner_events(white, q=Q, k=SMOOTH):
    lvl = np.clip(np.round(white / q), 0, 6).astype(int)
    sm = np.array([np.median(lvl[max(0, i - k // 2):i + k // 2 + 1])
                   for i in range(len(lvl))]).astype(int)
    ups = [i for i in range(1, len(sm)) if sm[i] > sm[i - 1]]
    return ups, sm


def audio_transients(short, pct, min_gap=0.10):
    f = AUDIO_DIR / f"{short}_series.json"
    if not f.exists():
        return None, None
    s = json.loads(f.read_text(encoding="utf-8"))
    flux = np.asarray(s["flux"], dtype=float)
    tt = np.arange(len(flux)) * (s["hop_ms"] / 1000.0)
    thr = float(np.percentile(flux, pct))
    isp = (flux >= thr) & (flux >= np.roll(flux, 1)) & (flux > np.roll(flux, -1))
    idx = np.where(isp)[0]
    keep = []
    for i in idx[np.argsort(-flux[idx])]:
        if all(abs(tt[i] - tt[j]) >= min_gap for j in keep):
            keep.append(int(i))
    return np.array(sorted(tt[keep])), tt


def binom_sf(k, n, p):
    if k <= 0:
        return 1.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    return min(1.0, sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def count_matches(tt, cs, tol):
    lo = np.searchsorted(tt, cs - tol, side="left")
    hi = np.searchsorted(tt, cs + tol, side="right")
    return int((hi > lo).sum())


def icon_event_times(short):
    """读 center_kill_icon.py 产出的中心徽记事件（玩家自己的击杀）。"""
    f = ICON_DIR / f"{short}.json"
    if not f.exists():
        return None
    ev = json.loads(f.read_text(encoding="utf-8")).get("events") or []
    return np.array([e["t_s"] for e in ev]) if ev else None


def cross_audio(n_sim=2000, seed=5, source="feed"):
    """事件 vs 音频强瞬态：分强度档/容差做汇总检验 + 含挑选偏差的滞后扫描。

    source="feed" → 右上角播报事件（场上任何人的击杀）
    source="icon" → 中心徽记事件（玩家自己的击杀；由 center_kill_icon.py 产出）
    """
    rng = np.random.default_rng(seed)
    label = {"feed": "横幅", "icon": "中心徽记"}.get(source, source)
    data = []
    for p in sorted(SRC.glob("*.mp4")):
        short = p.stem[:8]
        if source == "icon":
            ts = icon_event_times(short)
            if ts is None:
                continue
            ups = np.round(ts * FPS).astype(int)
            if not len(ups):
                continue
        else:
            ups, _ = banner_events(white_series(p))
            if not ups:
                continue
        dur = max(len(ups) / FPS + 1.0, float(ups[-1]) / FPS + 1.0)
        data.append((short, dur, np.array([i / FPS for i in ups])))
    print("%s事件合计 %d 个（%d 条素材）" % (label, sum(len(b) for _, _, b in data), len(data)))
    out = {"generated_by": f"projects/game-001/tools/feed_scan.py x --cross --source {source}",
           "source": source, "source_label": label,
           "evidence_level": "L1（事件=本机逐帧量像素判据；音频=本机解码音轨）",
           "n_events": int(sum(len(b) for _, _, b in data)),
           "n_banner_events": int(sum(len(b) for _, _, b in data)),
           "tests": [], "lag_scan": None}
    for pct in (95, 99, 99.5):
        prep = []
        for short, dur, b in data:
            ta, tt = audio_transients(short, pct)
            if ta is None or not len(ta):
                continue
            prep.append((short, float(tt[-1] + 0.01), b, ta))
        for tol in (0.03, 0.05, 0.10):
            obs = n = 0
            exp = 0.0
            for short, dur, b, ta in prep:
                grid = np.arange(0.0, dur, 0.001)
                hit = np.zeros(len(grid), dtype=bool)
                for x in ta:
                    hit |= np.abs(grid - x) <= tol
                p = float(hit.mean())
                obs += count_matches(ta, b, tol)
                n += len(b)
                exp += len(b) * p
            pbar = exp / n if n else 0.0
            sims = np.empty(n_sim, dtype=int)
            for k in range(n_sim):
                tot = 0
                for short, dur, b, ta in prep:
                    tot += count_matches(ta, (b + rng.uniform(0, dur)) % dur, tol)
                sims[k] = tot
            row = {
                "audio_strength_pct": pct, "tol_s": tol, "tol_frames": round(tol * FPS, 2),
                "n_banner_events": n, "expected_by_chance": round(exp, 2), "observed": obs,
                "hit_rate": round(obs / n, 4) if n else None,
                "chance_level": round(pbar, 4),
                "binom_p_one_sided": round(binom_sf(obs, n, pbar), 6) if n else None,
                "shift_null_mean": round(float(sims.mean()), 2),
                "shift_null_p_one_sided": round(float((sims >= obs).sum() + 1) / (n_sim + 1), 5),
            }
            out["tests"].append(row)
            print("  音频≥p%-5s tol=±%.2f  事件 %3d  预期 %6.2f  实测 %3d  命中率 %.3f  "
                  "二项p=%.5f  平移p=%.5f" % (pct, tol, n, exp, obs, row["hit_rate"],
                                              row["binom_p_one_sided"], row["shift_null_p_one_sided"]))
    # 滞后扫描（含 max-statistic 零假设）
    prep = []
    for short, _dur, b in data:
        ta, tt = audio_transients(short, 95)
        if ta is None or not len(ta):
            continue
        # 循环平移的周期要用**音频序列的长度**（= 素材时长），
        # 不能用「横幅事件跨度+1s」—— 周期取小了会把零分布压扁，p 值会偏乐观。
        prep.append((short, float(tt[-1] + 0.01), b, ta))
    lags = np.round(np.arange(-0.40, 0.401, 0.02), 3)
    tol = 0.05

    def curve(shifted):
        return np.array([sum(count_matches(ta, cs + lag, tol) for _, _, cs, ta in shifted)
                         for lag in lags])

    obs = curve(prep)
    bi = int(np.argmax(obs))
    mx = np.empty(1000, dtype=int)
    for k in range(1000):
        shifted = [(s, d, (b + rng.uniform(0, d)) % d, ta) for s, d, b, ta in prep]
        mx[k] = int(curve(shifted).max())
    out["lag_scan"] = {
        "tol_s": tol, "audio_strength_pct": 95,
        "matches_at_lag0": int(obs[len(lags) // 2]),
        "best_lag_s": float(lags[bi]), "best_matches": int(obs[bi]),
        "null_max_mean": float(mx.mean()), "null_max_p95": float(np.percentile(mx, 95)),
        "p_best_lag_maxstat": round(float((mx >= obs[bi]).sum() + 1) / 1001.0, 5),
        "top5": sorted([{"lag_s": float(l), "matches": int(v)} for l, v in zip(lags, obs)],
                       key=lambda r: -r["matches"])[:5],
        "curve": [{"lag_s": float(l), "matches": int(v)} for l, v in zip(lags, obs)],
    }
    ls = out["lag_scan"]
    print("  滞后扫描(音频≥p95, ±%.2fs)：lag=0→%d，最佳 lag=%+.2fs→%d；"
          "零分布 max 均值 %.1f/p95 %d ⇒ p=%.4f" % (
              tol, ls["matches_at_lag0"], ls["best_lag_s"], ls["best_matches"],
              ls["null_max_mean"], ls["null_max_p95"], ls["p_best_lag_maxstat"]))
    dst = OUTDIR / ("cross-audio.json" if source == "feed" else f"cross-audio-{source}.json")
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("[OK] %s" % dst.relative_to(ROOT))
    return out


def analyse(short):
    p = next(SRC.glob(f"{short}*.mp4"), None)
    if p is None:
        print(f"[FAIL] 没有素材 {short}*.mp4")
        return None
    white = white_series(p)
    ups, sm = banner_events(white)
    events = [{"frame": i, "t_s": round(i / FPS, 4), "level": int(sm[i]),
               "white_before": round(float(white[i - 1]), 4), "white_after": round(float(white[i]), 4)}
              for i in ups]
    res = {
        "short": short, "file": p.name,
        "evidence_level": "L1（本机逐帧量 top-right 白色剪影占比；区域与 q 均为实测标定）",
        "region": {"x": FEED[0], "y": FEED[1], "w": FEED[2], "h": FEED[3]},
        "params": {"white_threshold": WHITE, "q_per_entry": Q, "smooth_frames": SMOOTH},
        "event_semantics": ("上升沿 = 播报由「空」变「非空」（一批播报里的第一次击杀，"
                            "或条目过期上移造成的空隙）。**不等于每一次击杀**：播报非空时"
                            "追加在下面的新条目不会改变本带。level 不是条目数（见脚本头注）。"),
        "n_frames": int(len(white)),
        "white_median": round(float(np.median(white)), 4),
        "white_p99": round(float(np.percentile(white, 99)), 4),
        "n_events": len(events), "events": events,
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / f"{short}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    print("[OK] %s  帧 %d  white 中位 %.4f  横幅事件 %d 个：%s" % (
        (OUTDIR / f"{short}.json").relative_to(ROOT), len(white), np.median(white), len(events),
        ", ".join("%.3fs" % e["t_s"] for e in events)))
    return res


def rows(short, n_rows=2, row_h=26):
    """逐行带诊断：复现「新条目追加在下面 ⇒ 第一行不变」。

    `FEED` 带只覆盖播报的第一行；把带子按行切开分别测 white，就能看见
    新条目是落在**下面那一行**的（第一行在同一时刻毫无变化）。
    """
    p = next(SRC.glob(f"{short}*.mp4"), None)
    if p is None:
        print(f"[FAIL] 没有素材 {short}*.mp4")
        return 1
    x, y, w, _h = FEED
    series = {}
    for r in range(n_rows):
        region = (x, y + r * row_h, w, row_h)
        series[f"row{r + 1}"] = white_series(p, region)
    print("%s  逐行带（每行 y%d~%d）：" % (short, y, y + n_rows * row_h))
    for name, s in series.items():
        lvl = np.clip(np.round(s / Q), 0, 6).astype(int)
        changes = [(i, round(i / FPS, 3), int(lvl[i - 1]), int(lvl[i]), round(float(s[i]), 4))
                   for i in range(1, len(lvl)) if lvl[i] != lvl[i - 1]]
        print("  %s  阶跃 %d 次：" % (name, len(changes)))
        for c in changes:
            print("     帧 %4d  t=%7.3fs  %d→%d  (white=%.4f)" % c)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("short", help="素材短 id、all，或 x（配 --cross）")
    ap.add_argument("--cross", action="store_true", help="与音频瞬态做汇总检验")
    ap.add_argument("--rows", action="store_true",
                    help="逐行带诊断（复现「新条目追加在下面、第一行不变」）")
    ap.add_argument("--source", choices=("feed", "icon"), default="feed",
                    help="x --cross 用哪个事件源：feed=右上角播报（默认）、icon=中心徽记")
    args = ap.parse_args()
    if args.cross:
        cross_audio(source=args.source)
        return 0
    if args.rows:
        return rows(args.short)
    shorts = ([q.name[:8] for q in sorted(SRC.glob("*.mp4"))] if args.short == "all" else [args.short])
    for s in shorts:
        analyse(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
