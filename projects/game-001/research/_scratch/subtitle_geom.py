"""L1 measurement of the host subtitle design in BV1QrN9eGECm (1920x1080).

Two designs appear in this tutorial and they must not be averaged together:
  A) the big bold outlined line the presenter types into 剪映 (seen from ~t=60s)
  B) the chapter title card sampled at t=0

This script finds the white-glyph rows itself (no fixed strip) and measures
glyph height, horizontal extent, and outline thickness by ray-casting from each
white pixel outward until the pixel stops being dark.
"""
from __future__ import annotations

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

ROOT = pathlib.Path(__file__).resolve().parents[4]
VID = ROOT / "参考视频" / "教学"
FRM = ROOT / "projects" / "game-001" / "research" / "_frames"
FF = imageio_ffmpeg.get_ffmpeg_exe()
STEM = "BV1QrN9eGECm"
H, W = 1080, 1920


def load(t):
    f = FRM / f"f_{STEM}_{t:07.2f}.png"
    if not f.exists():
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(VID / f"{STEM}.mp4"), "-frames:v", "1", "-y", str(f)],
                       capture_output=True)
    return np.asarray(Image.open(f).convert("RGB"), dtype=np.float32)


def outline_thickness(a, mn, white, dark, name):
    """median run of consecutive dark pixels going up/down/left/right from glyph."""
    runs = []
    ys, xs = np.where(white)
    for y, x in list(zip(ys, xs))[::37]:
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            n = 0
            yy, xx = y + dy, x + dx
            while 0 <= yy < mn.shape[0] and 0 <= xx < mn.shape[1] and dark[yy, xx] and n < 40:
                n += 1
                yy += dy
                xx += dx
            if n:
                runs.append(n)
    if runs:
        print(f"    {name}: outline run med={np.median(runs):.0f}px "
              f"p25={np.percentile(runs,25):.0f} p75={np.percentile(runs,75):.0f} "
              f"max={max(runs)} (n={len(runs)})")
    return runs


for t in (0.0, 23.0, 60.0, 147.0, 285.0):
    a = load(t)
    lum = a.mean(axis=2)
    mn = a.min(axis=2)
    white = mn > 200
    dark = lum < 70
    rowc = white.sum(axis=1)
    bands, s = [], None
    for y, c in enumerate(rowc):
        if c > 12 and s is None:
            s = y
        elif c <= 12 and s is not None:
            if y - s >= 5:
                bands.append((s, y - 1))
            s = None
    if s is not None:
        bands.append((s, H - 1))
    print(f"\n=== @{t}s === white-glyph bands (rows with >12 white px):")
    # keep only bands in the lower third = subtitle area, plus report all
    for (b0, b1) in bands:
        sub = white[b0:b1 + 1]
        cols = np.where(sub.any(axis=0))[0]
        print(f"    rows {b0}..{b1}  h={b1-b0+1}px ({(b1-b0+1)/H*100:.2f}% of {H})  "
              f"cols {cols[0]}..{cols[-1]} w={cols[-1]-cols[0]+1}px "
              f"({(cols[-1]-cols[0]+1)/W*100:.1f}% of {W})")
    # outline thickness for the lowest band (the subtitle one)
    if bands:
        b0, b1 = bands[-1]
        pad = 30
        y0, y1 = max(0, b0 - pad), min(H, b1 + pad)
        outline_thickness(a[y0:y1], mn[y0:y1], white[y0:y1], dark[y0:y1],
                          f"band {b0}..{b1}")
