"""中心「击杀徽记」检测 —— 玩家**自己**击杀时才出现的圆形图标（第 11 轮）。

## 信号是什么（用户指出 → 逐帧复核，L1）

用户（玩家本人）说：**每次击杀，画面中间会出现一个圆形图标**。逐帧看图确认：

- 位置：`x≈612..724, y≈514..614`（屏幕正下方偏中，在技能条**上方**），直径约 100px；
- 外观：一朵「莲花／花瓣」形徽记 + 外圈细环，白色／青色、低饱和；
- **不是常驻 UI**：`b61cc53d` 全片 **64% 的帧没有它**（feature < 0.005）；
- 出现时刻 = 击杀时刻：`b61cc53d` **f183–186（6.100–6.200）没有、f187（6.2333）出现**，
  与右上角播报的「首现帧 187」**同帧**（见 `kill-frame-criteria.md` §1 第 10 条）。

## 为什么它比右上角播报更有用

| 信号 | 覆盖谁 | 实测例子（`b61cc53d`） |
|---|---|---|
| 右上角播报（`feed_scan.py`） | **场上任何人**的击杀 | 11.733s 的条目是 `风说想你 → 大白苺`（不是「我」） |
| **中心徽记（本工具）** | 疑似**只有玩家自己**的击杀 | **15.800s 有播报、没有徽记**；22.533s 两者都有 |

⇒ 做「击杀集锦」时，中心徽记是「**我**击杀」的正交证据。
⚠️ 本工具**只输出事件**，不最终判定；「徽记只在本人击杀时出现」这一条**仍待人工确认**
（见 `verification/icon-scan/README.md` 遗留）。

## 判据

    bright  = max(R,G,B) > 190
    neutral = bright 且 (max−min) < 50        # 徽记是白色／青色的低饱和亮块
    feat    = neutral 在框内的占比

实测基线 ≈ 0.000（无徽记），徽记在场 0.04–0.09 ⇒ 阈值 `0.02` + 最少持续 `3` 帧。

## 用法

    .venv\\Scripts\\python.exe projects/game-001/tools/center_kill_icon.py all
    .venv\\Scripts\\python.exe projects/game-001/tools/feed_scan.py x --cross --source icon

输出：projects/game-001/verification/icon-scan/<short>.json
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
OUTDIR = ROOT / "projects" / "game-001" / "verification" / "icon-scan"

FPS = 30.0
BOX = (612, 514, 112, 100)      # x, y, w, h（紧贴徽记、避开下方技能条；w/h 必须偶数）
BRIGHT = 190                    # 「亮」门限
SAT_MAX = 50                    # 「低饱和」门限（max−min）
THRESH = 0.02                   # 占比门限
MIN_RUN = 3                     # 最少持续帧数（去抖）
MERGE_GAP = 2                   # 允许的中间空隙（帧）
# 徽记是**约 2.0s** 的 UI 元素：多条素材里干净的一段正好是 **60 帧**。
# 短于 1s（30 帧）的「亮块超过阈值」更可能是**场景里的亮面**（墙/天空/煙）而不是徽记
# ⇒ 分成两套输出：`events`（高置信，≥30 帧）与 `events_raw`（全部，含短段）。
MIN_DUR_FRAMES = 30


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def icon_series(path, box=BOX):
    x, y, w, h = box
    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", str(path),
                          "-vf", f"crop={w}:{h}:{x}:{y}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    if len(raw) % (w * h * 3):
        raise SystemExit(f"[FAIL] 帧字节数不是 {w}x{h}x3 的整数倍 —— "
                         f"ffmpeg 很可能改写了裁剪尺寸（奇数边），请先把 w/h 调成偶数")
    a = np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w, 3).astype(np.int16)
    mx = a.max(axis=3)
    mn = a.min(axis=3)
    return ((mx > BRIGHT) & ((mx - mn) < SAT_MAX)).mean(axis=(1, 2))


def runs(mask, merge_gap=MERGE_GAP, min_run=MIN_RUN):
    """把布尔序列切成连续区间（允许 merge_gap 帧的空隙，丢掉短于 min_run 的段）。"""
    idx = np.where(mask)[0]
    if not len(idx):
        return []
    out = []
    start = prev = int(idx[0])
    for i in idx[1:]:
        i = int(i)
        if i - prev <= merge_gap + 1:
            prev = i
            continue
        out.append((start, prev))
        start = prev = i
    out.append((start, prev))
    return [(a, b) for a, b in out if b - a + 1 >= min_run]


def analyse(short):
    p = next(SRC.glob(f"{short}*.mp4"), None)
    if p is None:
        print(f"[FAIL] 没有素材 {short}*.mp4")
        return None
    feat = icon_series(p)
    rs = runs(feat >= THRESH)
    raw = [{"frame": a, "t_s": round(a / FPS, 4),
            "duration_frames": b - a + 1, "duration_s": round((b - a + 1) / FPS, 3),
            "peak": round(float(feat[a:b + 1].max()), 4)}
           for a, b in rs]
    events = [e for e in raw if e["duration_frames"] >= MIN_DUR_FRAMES]
    res = {
        "short": short, "file": p.name,
        "evidence_level": "L1（本机逐帧量中心徽记框内低饱和亮块占比；区域与阈值均为实测标定）",
        "region": {"x": BOX[0], "y": BOX[1], "w": BOX[2], "h": BOX[3]},
        "params": {"bright": BRIGHT, "sat_max": SAT_MAX, "thresh": THRESH,
                   "min_run_frames": MIN_RUN, "merge_gap_frames": MERGE_GAP,
                   "min_dur_frames_high_conf": MIN_DUR_FRAMES},
        "event_semantics": ("徽记首现帧 = 玩家自己的一次击杀（**待人工确认**）；"
                            "右上角播报则可能是队友的击杀"),
        "n_frames": int(len(feat)),
        "feat_median": round(float(np.median(feat)), 5),
        "feat_peak": round(float(feat.max()), 4),
        "empty_frame_ratio": round(float((feat < 0.005).mean()), 3),
        "n_events": len(events), "events": events,
        "n_events_raw": len(raw), "events_raw": raw,
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / f"{short}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    print("[OK] %-9s 帧 %4d  空帧占比 %.2f  高置信 %2d/%2d 个：%s" % (
        short, len(feat), res["empty_frame_ratio"], len(events), len(raw),
        ", ".join("%.3fs(%df)" % (e["t_s"], e["duration_frames"]) for e in events)))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("short", help="素材短 id 或 all")
    args = ap.parse_args()
    shorts = ([q.name[:8] for q in sorted(SRC.glob("*.mp4"))] if args.short == "all"
              else [args.short])
    for s in shorts:
        analyse(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
