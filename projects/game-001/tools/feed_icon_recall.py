"""播报事件 ↔ 中心徽记 的「漏报复检」（第 13 轮）。

## 为什么需要这个工具

`verification/icon-scan/README.md` §2 里挂了一条 3 轮的结论：

> 播报事件 65 个里只有 **34%** 在 ±0.5s 内有徽记事件。

第 13 轮把这条逐条复检，结论是：**那个 34% 量的不是「徽记漏报」**，
而是三件与徽记检测器无关的事叠在一起：

1. **匹配口径错** —— 旧脚本拿播报帧去比「徽记段的**起始帧**」，可是徽记是**约 2s（60 帧）**
   的 UI 元素。播报帧落在段**中间**时，到起始帧的距离自然是 30~110 帧 ⇒ 被误判成「没有徽记」。
   ⇒ 本工具按**区间**比：`a - tol ≤ f ≤ b + tol`。
2. **播报事件不是「击杀事件」**（`feed_scan.py` 的固有语义）：它取的是**行1 的上升沿**，
   而条目**从下往上追加**（最新在最下）⇒ 「播报非空时追加在下面」不产生事件，
   但**旧条目过期、剩下的条目整体上移**会产生事件 ⇒ **同一次击杀会二次触发**。
   ⇒ 本工具用 NCC 位移检验把它认出来（见下）。
3. **播报覆盖场上任何人**：队友的击杀也有播报，但**不会**出现中心徽记。
   ⇒ 这一类比必须**读播报文字**（人工）才能判定，工具只负责把它挑出来。

## 位移检验（本工具的核心判据，L1）

条目上移会把**行2 的像素整体搬到行1**（y 差 26px），于是：

    上移匹配 = max_{3 ≤ dt ≤ 45} NCC( row1[f], row2[f − dt] )

- `上移匹配 ≥ 0.85` ⇒ 行1 现在的内容**就是**若干帧前在行2 的内容
  ⇒ 这条播报事件**不是新击杀**（是旧条目过期上移）⇒ 不该要求它有徽记。
- `仍在row1 ≥ 0.72` ⇒ 行1 的内容与 5~30 帧前几乎一致 ⇒ 播报**没变**，
  是白光带被场景亮面／特效应到阈值 ⇒ **`feed_scan` 自己的假报**。

两类都与徽记检测器无关，但**必须分开报**：前者是事件语义问题，后者是播报检测器的精度问题。

## 用法

    .venv\\Scripts\\python.exe projects/game-001/tools/feed_icon_recall.py
    .venv\\Scripts\\python.exe projects/game-001/tools/feed_icon_recall.py --sheets

输出：projects/game-001/verification/feed-scan/icon-recall.json
      projects/game-001/verification/frames/<short>_feed_rows_<lo>-<hi>.png（--sheets）
"""
from __future__ import annotations

import argparse
import json
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
ICON_DIR = ROOT / "projects" / "game-001" / "verification" / "icon-scan"
FEED_DIR = ROOT / "projects" / "game-001" / "verification" / "feed-scan"
FRAMES_DIR = ROOT / "projects" / "game-001" / "verification" / "frames"

FPS = 30.0
FEED = (880, 56, 400, 26)     # 与 feed_scan.py 的 FEED 完全一致（行1）
ROW_H = 26                    # 行距；行2 = y+26
WHITE = 235                   # 与 feed_scan.py 一致
Q = 0.029
SMOOTH = 5

TOL = 15                      # ±0.5s，沿用旧口径便于对照
SHIFT_NCC = 0.85              # 「上移」判定
SAME_NCC = 0.72               # 「播报没变」判定


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def read_region(path, region):
    x, y, w, h = region
    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", str(path),
                          "-vf", f"crop={w}:{h}:{x}:{y}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    if len(raw) % (w * h * 3):
        raise SystemExit(f"[FAIL] 帧字节数不是 {w}x{h}x3 的整数倍（w/h 要偶数）")
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w, 3)


def white_series(frames):
    return (frames > WHITE).all(axis=3).mean(axis=(1, 2))


def level_steps(white, q=Q, k=SMOOTH):
    """与 feed_scan.py 的 banner_events 同一套量化 + 中值滤波，返回每帧的 level 与阶跃位置。"""
    lvl = np.clip(np.round(white / q), 0, 6).astype(int)
    sm = np.array([np.median(lvl[max(0, i - k // 2):i + k // 2 + 1])
                   for i in range(len(lvl))]).astype(int)
    return sm, [i for i in range(1, len(sm)) if sm[i] != sm[i - 1]]


def ncc(a, b):
    a = a.astype(np.float32) - float(a.mean())
    b = b.astype(np.float32) - float(b.mean())
    d = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / d) if d else 0.0


def shift_ncc(row1, row2, f, dt_max=45):
    """行1[f] 与 行2[f-dt] 的最大 NCC（=「这条内容是从下面上移来的」）。"""
    best, arg = 0.0, None
    for dt in range(3, dt_max + 1):
        g = f - dt
        if g < 0:
            break
        c = ncc(row1[f], row2[g])
        if c > best:
            best, arg = c, dt
    return best, arg


def same_row1_ncc(row1, f, lags=(5, 10, 15, 20, 25, 30)):
    return max(ncc(row1[f], row1[f - dt]) for dt in lags if f - dt >= 0)


def runs_of(short, key):
    d = json.loads((ICON_DIR / f"{short}.json").read_text(encoding="utf-8"))
    return [(e["frame"], e["frame"] + e["duration_frames"] - 1) for e in d.get(key) or []]


def iv_dist(f, ivs):
    """帧 f 到一组区间的距离：落在区间内 = 0。"""
    if not ivs:
        return 10 ** 9
    return min(0 if a <= f <= b else min(abs(f - a), abs(f - b)) for a, b in ivs)


def start_dist(f, ivs):
    """旧口径：只比「段的起始帧」（第 13 轮认定这是错的，保留只为对照）。"""
    return min((abs(f - a) for a, _ in ivs), default=10 ** 9)


def verdict(d_raw, sh, same):
    if d_raw == 0:
        return "徽记段内"
    if sh >= SHIFT_NCC:
        return "播报上移"
    if same >= SAME_NCC:
        return "播报未变"
    return "待读播报"


def analyse(shorts=None):
    shorts = shorts or [p.name[:8] for p in sorted(SRC.glob("*.mp4"))]
    events, per_material = [], []
    for s in shorts:
        p = next(SRC.glob(f"{s}*.mp4"), None)
        feed_json = FEED_DIR / f"{s}.json"
        if p is None or not feed_json.exists():
            print(f"[SKIP] {s}（缺素材或 feed-scan/{s}.json）")
            continue
        fev = json.loads(feed_json.read_text(encoding="utf-8"))["events"]
        hi, raw = runs_of(s, "events"), runs_of(s, "events_raw")
        b1 = read_region(p, FEED)
        b2 = read_region(p, (FEED[0], FEED[1] + ROW_H, FEED[2], FEED[3]))
        white1 = white_series(b1)
        _sm, steps = level_steps(white1)
        drops = [i for i in steps if _sm[i] < _sm[i - 1]]
        for k, e in enumerate(fev, 1):
            f = e["frame"]
            sh, sh_dt = shift_ncc(b1, b2, f)
            same = same_row1_ncc(b1, f)
            d_raw, d_hi = iv_dist(f, raw), iv_dist(f, hi)
            gap = any(f - 30 <= i <= f - 3 for i in drops)
            cov = "段内" if d_raw == 0 else ("±0.5s" if d_raw <= TOL else "无")
            nk = ("上移（非新击杀）" if sh >= SHIFT_NCC
                  else "播报未变（非新击杀）" if same >= SAME_NCC else "无证据否定")
            events.append({
                "material": s, "event_id": k, "frame": f, "t_s": e["t_s"],
                "dist_raw_interval": d_raw, "dist_hi_interval": d_hi,
                "dist_raw_startframe_legacy": start_dist(f, raw),
                "dist_hi_startframe_legacy": start_dist(f, hi),
                "shift_ncc": round(sh, 3), "shift_dt": sh_dt,
                "same_row1_ncc": round(same, 3),
                "row1_gap_before": bool(gap),
                "icon_cover": cov, "new_kill_evidence": nk,
                "verdict": verdict(d_raw, sh, same),
            })
        hits = [{"frame": a, "t_s": round(a / FPS, 4),
                 "nearest_feed_event_frames": int(min((abs(a - e["frame"]) for e in fev), default=-1)),
                 "matched_±0.5s": bool(any(abs(a - e["frame"]) <= TOL for e in fev))}
                for a, _b in hi]
        per_material.append({"material": s, "n_feed_events": len(fev),
                             "n_icon_hi": len(hi), "n_icon_raw": len(raw),
                             "icon_hi_matched_by_feed": sum(h["matched_±0.5s"] for h in hits),
                             "icon_hi_detail": hits})
    n = len(events)
    def pct(k):
        return round(100.0 * k / n, 1) if n else 0.0
    leg_raw = sum(e["dist_raw_startframe_legacy"] <= TOL for e in events)
    leg_hi = sum(e["dist_hi_startframe_legacy"] <= TOL for e in events)
    new_raw = sum(e["dist_raw_interval"] <= TOL for e in events)
    new_hi = sum(e["dist_hi_interval"] <= TOL for e in events)
    vc = {}
    for e in events:
        vc[e["verdict"]] = vc.get(e["verdict"], 0) + 1
    out = {
        "tool": "projects/game-001/tools/feed_icon_recall.py",
        "evidence_level": "L1（本机逐帧像素：白剪影带 + NCC 位移检验；徽记段取自 icon-scan/*.json）",
        "question": "播报事件里「没有徽记」的那些，到底是不是徽记检测器漏报？",
        "params": {"fps": FPS, "feed_region": FEED, "white": WHITE, "q": Q,
                   "smooth": SMOOTH, "tol_frames": TOL,
                   "shift_ncc_threshold": SHIFT_NCC, "same_ncc_threshold": SAME_NCC},
        "headline": {
            "n_feed_events": n,
            "legacy_startframe_matched": {"raw": leg_raw, "raw_pct": pct(leg_raw),
                                          "high_conf": leg_hi, "high_conf_pct": pct(leg_hi)},
            "interval_matched": {"raw": new_raw, "raw_pct": pct(new_raw),
                                 "high_conf": new_hi, "high_conf_pct": pct(new_hi)},
            "verdict_counts": vc,
            "need_eyes": sum(1 for e in events
                             if e["verdict"] == "待读播报" and e["dist_raw_interval"] > TOL),
        },
        "verdict_legend": {
            "徽记段内": "播报帧落在徽记段的 [起, 止] 内 ⇒ 旧脚本按「段的起始帧」比才算成漏报的",
            "播报上移": "行1 的内容 = 若干帧前行2 的内容（NCC ≥ %.2f）⇒ 旧条目过期上移，"
                        "同一次击杀的二次触发，不是新击杀" % SHIFT_NCC,
            "播报未变": "行1 与 5~30 帧前几乎一致（NCC ≥ %.2f）⇒ 带内白光来自场景亮面／特效，"
                        "是 feed_scan 自己的假报" % SAME_NCC,
            "待读播报": "两种检验都没否定它 ⇒ 必须**人工读播报文字**：如果击杀者是队友，"
                        "没有徽记是应该的（播报覆盖场上任何人）",
        },
        "note": ("旧口径（起点帧）复现了 icon-scan/README.md §2 的「34%」；"
                 "换成区间口径后同一批数据一致得多 —— 差额全部来自徽记段长约 60 帧这一件事。"
                 "剩下的「播报上移」是 feed_scan 事件语义（同一次击杀二次触发），"
                 "「播报未变」是 feed_scan 的假报，「待读播报」必须人工读文字（队友击杀无徽记）。"),
        "per_material": per_material,
        "events": events,
    }
    FEED_DIR.mkdir(parents=True, exist_ok=True)
    dst = FEED_DIR / "icon-recall.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("素材 %d 条，播报事件 %d 个" % (len(per_material), n))
    print("  旧口径（比段起始帧）±0.5s 命中：raw %d(%s%%) 高置信 %d(%s%%)"
          % (leg_raw, pct(leg_raw), leg_hi, pct(leg_hi)))
    print("  区间口径           ±0.5s 命中：raw %d(%s%%) 高置信 %d(%s%%)"
          % (new_raw, pct(new_raw), new_hi, pct(new_hi)))
    for k, v in sorted(vc.items(), key=lambda kv: -kv[1]):
        print("  verdict %-8s %d" % (k, v))
    tot_hi = sum(m["n_icon_hi"] for m in per_material)
    tot_hit = sum(m["icon_hi_matched_by_feed"] for m in per_material)
    print("  反向：高置信徽记 %d 个里 %d 个（%s%%）±0.5s 内有播报事件"
          % (tot_hi, tot_hit, round(100.0 * tot_hit / tot_hi, 1) if tot_hi else 0.0))
    print("[OK] %s" % dst.relative_to(ROOT))
    return out


def sheets(short, f_lo, f_hi, step, zoom=2.4):
    """把指定帧段的行1+行2 播报带放大贴出来（人工读「谁的击杀」用）。"""
    from PIL import Image, ImageDraw
    p = next(SRC.glob(f"{short}*.mp4"), None)
    if p is None:
        raise SystemExit(f"[FAIL] 没有素材 {short}*.mp4")
    BOX = (900, 50, 380, 90)
    a = read_region(p, BOX)
    picks = list(range(f_lo, min(f_hi, len(a) - 1) + 1, step))
    w, h = BOX[2], BOX[3]
    W, H = int(w * zoom), int(h * zoom)
    img = Image.new("RGB", (W, len(picks) * (H + 20)), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, f in enumerate(picks):
        top = i * (H + 20)
        d.text((3, top + 4), f"f{f}  t={f / FPS:.3f}s", fill=(255, 220, 0))
        img.paste(Image.fromarray(a[f]).resize((W, H), Image.LANCZOS), (0, top + 18))
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    out = FRAMES_DIR / f"{short}_feed_rows_{f_lo}-{f_hi}.png"
    img.save(out)
    print("[OK] %s  %s" % (out.relative_to(ROOT), img.size))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("short", nargs="?", help="只跑某条素材（默认全部）")
    ap.add_argument("--sheets", action="store_true",
                    help="额外输出播报带放大图（需配 --lo/--hi/--step）")
    ap.add_argument("--lo", type=int, default=0)
    ap.add_argument("--hi", type=int, default=0)
    ap.add_argument("--step", type=int, default=8)
    args = ap.parse_args()
    if args.sheets:
        if not args.short or not args.hi:
            raise SystemExit("--sheets 需要 <short> --lo <f> --hi <f> [--step n]")
        sheets(args.short, args.lo, args.hi, args.step)
        return 0
    analyse([args.short] if args.short else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
