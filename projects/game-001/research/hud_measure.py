"""Measure VALORANT HUD regions (kill feed + bottom kill-effect banner) from real frames.

First-hand measurement, not a web claim. Source clips are 1280x720.
Method: pick a frame WITH the element and a reference frame WITHOUT it (same clip,
close in time so the scene is ~identical), diff them, and take the bounding box of
changed pixels inside a search window.

Usage:  .venv\\Scripts\\python.exe projects/game-001/research/hud_measure.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image
import imageio_ffmpeg

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
TMP = ROOT / "projects" / "game-001" / "research" / "_frames"
FF = imageio_ffmpeg.get_ffmpeg_exe()


def probe(path: pathlib.Path):
    p = subprocess.run([FF, "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True, errors="replace")
    txt = p.stderr
    res = None
    for line in txt.splitlines():
        line = line.strip()
        if "Video:" in line and "x" in line:
            # e.g. "Stream #0:0: Video: h264 ..., 1280x720 [SAR 1:1 ..."
            for tok in line.replace(",", " ").split():
                if "x" in tok and tok.replace("x", "").isdigit():
                    w, h = tok.split("x")
                    res = (int(w), int(h))
                    break
    return res


def grab(path: pathlib.Path, t: float) -> Image.Image:
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / f"{path.stem[:8]}_{t:.3f}.png"
    if not out.exists():
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(path), "-frames:v", "1", "-y", str(out)],
                       capture_output=True)
    return Image.open(out).convert("RGB")


def diff_bbox(a: Image.Image, b: Image.Image, box, thresh=18):
    """Bounding box (in full-frame coords) of pixels differing more than thresh."""
    x0, y0, x1, y1 = box
    A = np.asarray(a.crop(box), dtype=np.int16)
    B = np.asarray(b.crop(box), dtype=np.int16)
    d = np.abs(A - B).max(axis=2)
    mask = d > thresh
    if not mask.any():
        return None, 0, int(mask.sum())
    ys, xs = np.where(mask)
    return ((x0 + int(xs.min()), y0 + int(ys.min()),
             x0 + int(xs.max()), y0 + int(ys.max())), len(ys), int(mask.sum()))


def scale(box, sw, sh, dw, dh):
    if box is None:
        return None
    x0, y0, x1, y1 = box
    fx, fy = dw / sw, dh / sh
    return (round(x0 * fx), round(y0 * fy), round(x1 * fx), round(y1 * fy))


print("=== 1. 原始素材分辨率 ===")
clips = {}
for f in sorted(SRC.glob("*.mp4")):
    r = probe(f)
    clips[f.stem[:8]] = r
    print(f"  {f.stem[:8]}  {r}")
uniq = sorted({v for v in clips.values() if v})
print(f"  -> distinct resolutions: {uniq}")

# ---- kill feed probe -------------------------------------------------------
# 4b0460c4: kill feed edges at 4.60 / 6.30 / 9.93 ... bottom effect 4.13 / 4.73 ...
CLIP = SRC / "4b0460c400bbb5320acb6063b4f59358.mp4"
W, H = probe(CLIP)

TR_WINDOW = (900, 0, W, 200)      # generous search window, top-right
BO_WINDOW = (0, 560, W, H)        # generous search window, bottom strip

print("\n=== 2. 右上角击杀播报（kill feed）===")
# frame with feed = 4.70 (feed edge 4.60), reference = 4.45 (before feed, same scene)
probes = [(4.70, 4.45), (6.40, 6.10), (14.80, 14.55)]
for with_t, ref_t in probes:
    a, b = grab(CLIP, ref_t), grab(CLIP, with_t)   # a=without, b=with
    bb, nrow, npx = diff_bbox(a, b, TR_WINDOW)
    s1080 = scale(bb, W, H, 1920, 1080)
    print(f"  ref {ref_t:.2f}s vs feed {with_t:.2f}s -> bbox@720p {bb}  changed_px={npx}")
    print(f"      -> @1080p {s1080}")

print("\n=== 3. 底部击杀特效（bottom kill-effect banner）===")
for with_t, ref_t in [(4.80, 4.45), (9.45, 9.20), (16.80, 16.50)]:
    a, b = grab(CLIP, ref_t), grab(CLIP, with_t)
    bb, nrow, npx = diff_bbox(a, b, BO_WINDOW)
    s1080 = scale(bb, W, H, 1920, 1080)
    print(f"  ref {ref_t:.2f}s vs banner {with_t:.2f}s -> bbox@720p {bb}  changed_px={npx}")
    print(f"      -> @1080p {s1080}")

print("\n=== 4. 下缘逐行变化（定位底部横幅的 y 上界）===")
a, b = np.asarray(grab(CLIP, 4.45), dtype=np.int16), np.asarray(grab(CLIP, 4.80), dtype=np.int16)
d = np.abs(a - b).max(axis=2)
rowmax = d.max(axis=1)
rows = [(y, int(rowmax[y]), int((d[y] > 18).sum())) for y in range(H)]
active = [r for r in rows if r[2] > 3]
if active:
    print(f"  行级活跃区间: y={active[0][0]}..{active[-1][0]}  (@720p)")
    print(f"     -> @1080p y={round(active[0][0]*1.5)}..{round(active[-1][0]*1.5)}")
else:
    print("  未检出")

print("\n=== 5. 右上角逐列变化（定位播报 x 左右界）===")
a, b = np.asarray(grab(CLIP, 4.45), dtype=np.int16), np.asarray(grab(CLIP, 4.70), dtype=np.int16)
d = np.abs(np.asarray(grab(CLIP, 4.45), dtype=np.int16) - np.asarray(grab(CLIP, 4.70), dtype=np.int16)).max(axis=2)
d_tr = d[0:200, :]
colmask = (d_tr > 18).sum(axis=0)
cols = [x for x in range(W) if colmask[x] > 1]
if cols:
    print(f"  列级活跃区间: x={cols[0]}..{cols[-1]}  (@720p)")
    print(f"     -> @1080p x={round(cols[0]*1.5)}..{round(cols[-1]*1.5)}")
rowmask_tr = (d_tr > 18).sum(axis=1)
rws = [y for y in range(200) if rowmask_tr[y] > 1]
if rws:
    print(f"  行级活跃区间: y={rws[0]}..{rws[-1]}  (@720p)")
    print(f"     -> @1080p y={round(rws[0]*1.5)}..{round(rws[-1]*1.5)}")
