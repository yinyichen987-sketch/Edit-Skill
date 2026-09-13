"""Systematic caption-band scan of BV1ue8y6XE2M (480x852 vertical).

Prints, for many sampled frames, the contiguous row bands containing
near-white text pixels, so the caption band can be established from data
rather than from one lucky frame. Also reports the background luminance in
that band so a contrast ratio can be computed.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
from collections import Counter

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
STEM = "BV1ue8y6XE2M"


def load(t: float) -> np.ndarray:
    f = FRM / f"f_{STEM}_{t:07.2f}.png"
    if not f.exists():
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(VID / f"{STEM}.mp4"), "-frames:v", "1", "-y", str(f)],
                       capture_output=True)
    return np.asarray(Image.open(f).convert("RGB"), dtype=np.float32)


def lin(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def bands_of(mask, min_rows=4):
    out, s = [], None
    for y, v in enumerate(mask):
        if v and s is None:
            s = y
        elif not v and s is not None:
            if y - s >= min_rows:
                out.append((s, y - 1))
            s = None
    if s is not None and len(mask) - s >= min_rows:
        out.append((s, len(mask) - 1))
    return out


ts = [round(1.0 + k * 1.5, 2) for k in range(46)]
FOUND = Counter()
detail = []
for t in ts:
    a = load(t)
    H, W = a.shape[:2]
    body = a[365:436]                       # the caption band candidate
    mn = body.min(axis=2)
    white = (mn > 205)
    cnt = white.sum(axis=1)
    mask = cnt > 8
    bl = bands_of(mask)
    rowsum = body.mean(axis=(1, 2))
    detail.append((t, bl, float(rowsum.min()), float(rowsum.max())))
    for b in bl:
        FOUND[(b[0] + 365, b[1] + 365)] += 1

print(f"sampled {len(ts)} frames of {STEM}")
print("\nband (rows) -> how many sampled frames had it:")
for k, v in FOUND.most_common(12):
    print(f"   y{k[0]}..{k[1]}  (h={k[1]-k[0]+1}px)  x{v}/{len(ts)} frames")

print("\nper-frame detail (band rows in 365..435, plus row-lum min/max of that strip):")
for t, bl, lo, hi in detail:
    print(f"   {t:6.2f}s  bands={bl}  strip rowLum {lo:.1f}/{hi:.1f}")

print("\n--- caption geometry, from the modal band ---")
top, bot = FOUND.most_common(1)[0][0]
H = 852
print(f"modal band y{top}..{bot}: top={top/H*100:.2f}%  bottom={(bot+1)/H*100:.2f}%  "
      f"height={(bot-top+1)/H*100:.2f}% of frame height ({bot-top+1}px of {H})")

# contrast of caption text vs background in that band, averaged over frames where it appears
con = []
for t, bl, lo, hi in detail:
    if any(b[0] + 365 == top for b in bl):
        a = load(t)
        strip = a[top:bot + 1]
        mn = strip.min(axis=2)
        wht = strip[mn > 205]
        bg = strip[mn <= 205]
        if wht.size and bg.size:
            Lw = float(lin(wht).mean())
            Lb = float(lin(bg).mean())
            con.append((Lw + 0.05) / (Lb + 0.05))
if con:
    print(f"contrast (caption white vs its band background): "
          f"med={np.median(con):.2f}:1  range {min(con):.2f}-{max(con):.2f}:1  n={len(con)}")
    print(f"columns of the widest caption in the band:")
    widest = 0
    for t, bl, lo, hi in detail:
        a = load(t)
        strip = a[top:bot + 1]
        mn = strip.min(axis=2)
        cols = np.where((mn > 205).any(axis=0))[0]
        if len(cols):
            w = cols[-1] - cols[0] + 1
            if w > widest:
                widest = w
                info = (t, cols[0], cols[-1], w)
    t, c0, c1, w = info
    print(f"   widest @{t}s: cols {c0}..{c1} (w={w}px = {w/480*100:.1f}% of 480 = "
          f"{w/480*100:.1f}% of frame width)")
