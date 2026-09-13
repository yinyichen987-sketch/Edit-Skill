"""Isolate the VALORANT kill banner (底部击杀特效) by SHAPE, not just colour.

The Chinese-client kill banner is a wide, short red plate behind the 无畏契约 wordmark,
sitting in the lower-left. A plain "red pixel" test is fooled by the player's brown/red
gloved hand, so require a HORIZONTAL RED RUN: for each frame, find the widest contiguous
run of red-dominant pixels on any single row inside the search window, and require the
run to be >= MINRUN wide and the plate to be <= MAXH tall.

Also reports the kill feed plate (top-right dark plate + white row separator).
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw
import imageio_ffmpeg

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
OUT = ROOT / "projects" / "game-001" / "research" / "_hud"
OUT.mkdir(parents=True, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720

MINRUN = 120          # a banner plate is a wide band
RED_TH = 22
SEARCH = (0, 540, 720, 720)     # bottom-left quadrant


def stream(path, t0, t1, fps=30):
    raw = subprocess.run(
        [FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}",
         "-i", str(path), "-vf", f"fps={fps}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True).stdout
    n = len(raw) // (W * H * 3)
    a = np.frombuffer(raw[: n * W * H * 3], dtype=np.uint8).reshape(n, H, W, 3)
    return [(t0 + i / fps, a[i]) for i in range(n)]


def longest_run(row_mask):
    """(start, length) of the longest True run."""
    best = (0, 0)
    cur = 0
    start = 0
    for i, v in enumerate(row_mask):
        if v:
            if cur == 0:
                start = i
            cur += 1
            if cur > best[1]:
                best = (start, cur)
        else:
            cur = 0
    return best


def sc(v):
    return round(v * 1.5)


results = []
print("=== 全素材扫描：底部横向红色带（击杀横幅候选）===")
for f in sorted(SRC.glob("*.mp4")):
    x0, y0, x1, y1 = SEARCH
    best = None
    # sample the whole clip at 6 fps to find candidate moments cheaply
    for t, fr in stream(f, 0.0, min(40.0, 1e9), fps=6):
        reg = fr[y0:y1, x0:x1].astype(np.int16)
        red = reg[:, :, 0] - np.maximum(reg[:, :, 1], reg[:, :, 2])
        m = red > RED_TH
        for i in range(0, m.shape[0], 2):
            s, L = longest_run(m[i])
            if L >= MINRUN and (best is None or L > best[2]):
                best = (t, y0 + i, L, x0 + s)
    if best:
        results.append((f.stem[:8], *best))
        print(f"  {f.stem[:8]}  t={best[0]:6.3f}s  run_len={best[2]:4}px  "
              f"row y={best[1]:3}  x_start={best[3]:4}"
              f"   -> @1080p len={sc(best[2])} y={sc(best[1])} x={sc(best[3])}")

if results:
    results.sort(key=lambda r: -r[3])
    clip, t, row, L, xs = results[0]
    print(f"\n  最强候选: {clip} @ {t:.3f}s  run {L}px @ y={row}, x={xs}..{xs+L}")
    print(f"    -> @1080p: y={sc(row)}, x={sc(xs)}..{sc(xs+L)}, 宽 {sc(L)}")

    # refine: full vertical extent of the plate at that moment
    f = next(SRC.glob(f"{clip}*.mp4"))
    for tt, fr in stream(f, t, t + 0.001):
        reg = fr[SEARCH[1]:SEARCH[3], SEARCH[0]:SEARCH[2]].astype(np.int16)
        red = reg[:, :, 0] - np.maximum(reg[:, :, 1], reg[:, :, 2])
        m = red > RED_TH
        rows = [(SEARCH[1] + i, int(m[i].sum())) for i in range(m.shape[0])
                if longest_run(m[i])[1] >= MINRUN]
        if rows:
            print(f"    板 y 范围: {rows[0][0]}..{rows[-1][0]} @720p"
                  f"  ({rows[-1][0]-rows[0][0]+1}px 高)"
                  f" -> @1080p {sc(rows[0][0])}..{sc(rows[-1][0])}"
                  f" ({sc(rows[-1][0]-rows[0][0]+1)}px)")
        # x extent across those rows
        sub = m[rows[0][0] - SEARCH[1]: rows[-1][0] - SEARCH[1] + 1] if rows else None
        if sub is not None and sub.any():
            cols = np.where(sub.any(axis=0))[0]
            print(f"    板 x 范围: {SEARCH[0]+cols.min()}..{SEARCH[0]+cols.max()} @720p"
                  f" -> @1080p {sc(SEARCH[0]+cols.min())}..{sc(SEARCH[0]+cols.max())}")
        p = OUT / f"banner_{clip}_{t:.3f}.png"
        Image.fromarray(fr).save(p)
        print(f"    frame -> {p.name}")

print("\n=== 右上角击杀播报板（暗底板 + 白色分隔行）===")
# The feed plate: a long thin near-white horizontal rule near the top of the plate.
f = SRC / "4b0460c400bbb5320acb6063b4f59358.mp4"
for t, fr in stream(f, 4.60, 4.61):
    sub = fr[0:130, 850:1280].astype(np.int16)
    mx, mn = sub.max(axis=2), sub.min(axis=2)
    white = (mx > 190) & ((mx - mn) < 40)
    for i in range(white.shape[0]):
        s, L = longest_run(white[i])
        if L >= 200:
            print(f"  t={t:.3f}s 白色长横线: y={i} @720p, x={850+s}..{850+s+L}"
                  f"  (len {L})  -> @1080p y={sc(i)} x={sc(850+s)}..{sc(850+s+L)}")
