"""Measure the red multi-kill badge plate (底部击杀特效) at confirmed own-kill times.

Search window is the lower-left/centre band; the plate is red-dominant AND carries
near-white glyphs (the wordmark + kill-count digit), which separates it from the
player's brown glove and from teal ability HUD.

Kill times come from analysis2/kills_mine.json (itself validated against ground truth).
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
OUT = ROOT / "projects" / "game-001" / "research" / "_hud"
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720
KM = json.loads((ROOT / "projects/game-001/analysis2/kills_mine.json").read_text(encoding="utf-8"))

X0, Y0, X1, Y1 = 120, 560, 820, 720     # lower band, excludes far-left glove core


def frames(path, t0, t1, fps=30):
    raw = subprocess.run(
        [FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}",
         "-i", str(path), "-vf", f"fps={fps}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True).stdout
    n = len(raw) // (W * H * 3)
    a = np.frombuffer(raw[: n * W * H * 3], dtype=np.uint8).reshape(n, H, W, 3)
    return [(t0 + i / fps, a[i]) for i in range(n)]


def analyse(fr):
    reg = fr[Y0:Y1, X0:X1].astype(np.int16)
    red = reg[:, :, 0] - np.maximum(reg[:, :, 1], reg[:, :, 2])
    mx, mn = reg.max(axis=2), reg.min(axis=2)
    white = (mx > 185) & ((mx - mn) < 45)
    plate = red > 30
    if plate.sum() < 250 or white.sum() < 25:
        return None
    # keep only plate rows that contain white glyph pixels (wordmark / digit)
    keep = []
    for i in range(plate.shape[0]):
        if plate[i].sum() < 20:
            continue
        band = white[max(0, i - 14): i + 15]
        if band.sum() >= 12:
            keep.append(i)
    if len(keep) < 8:
        return None
    r0, r1 = keep[0], keep[-1]
    sub = plate[r0:r1 + 1]
    cols = np.where(sub.sum(axis=0) >= max(3, (r1 - r0) * 0.15))[0]
    if len(cols) < 20:
        return None
    return (X0 + int(cols.min()), Y0 + r0, X0 + int(cols.max()), Y0 + r1,
            int(plate.sum()), int(white.sum()))


def sc(v):
    return round(v * 1.5)


found = []
print("=== 底部红色击杀徽章板（在已确证的自身击杀时刻测量）===")
for short, rec in sorted(KM.items()):
    f = SRC / rec["file"]
    if not f.exists():
        continue
    for k in rec["mine"][:12]:
        best = None
        for t, fr in frames(f, max(0.0, k - 0.35), k + 0.55):
            r = analyse(fr)
            if r and (best is None or r[4] > best[1][4]):
                best = (t, r)
        if best:
            t, r = best
            found.append((short, k, t, r))
            print(f"  {short} kill@{k:6.2f}s  best t={t:6.3f}s  "
                  f"plate@720p x{r[0]}..{r[2]} y{r[1]}..{r[3]} "
                  f"({r[2]-r[0]+1}x{r[3]-r[1]+1}px, red_px={r[4]})")
            print(f"       -> @1080p x{sc(r[0])}..{sc(r[2])} y{sc(r[1])}..{sc(r[3])} "
                  f"({sc(r[2]-r[0]+1)}x{sc(r[3]-r[1]+1)}px)")
            if len(found) == 1:
                Image.fromarray(fr).crop((X0 - 120, Y0, X1, Y1)).resize(
                    ((X1 - X0 + 120) * 2, (Y1 - Y0) * 2)).save(OUT / "badge_ref.png")

if found:
    xs0 = [r[3][0] for r in found]
    xs1 = [r[3][2] for r in found]
    ys0 = [r[3][1] for r in found]
    ys1 = [r[3][3] for r in found]
    print(f"\n  汇总 (n={len(found)}) @720p:")
    print(f"    x 范围 {min(xs0)}..{max(xs1)}   y 范围 {min(ys0)}..{max(ys1)}")
    print(f"    -> @1080p x {sc(min(xs0))}..{sc(max(xs1))}   y {sc(min(ys0))}..{sc(max(ys1))}")
    print(f"    中位宽 {int(np.median([r[3][2]-r[3][0]+1 for r in found]))}px @720p, "
          f"中位高 {int(np.median([r[3][3]-r[3][1]+1 for r in found]))}px")
else:
    print("  未检出")
