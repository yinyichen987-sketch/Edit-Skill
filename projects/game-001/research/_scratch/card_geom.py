"""L1 geometry of the 卡点 reveal card (BV1qx5463Exr @1.0s, 1920x1080).

Measures the tilted bordered card: its bounding box, the neon border thickness,
the title band, and the vertical side label, directly from pixels.
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


def load(stem, t):
    f = FRM / f"f_{stem}_{t:07.2f}.png"
    if not f.exists():
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(VID / f"{stem}.mp4"), "-frames:v", "1", "-y", str(f)],
                       capture_output=True)
    return np.asarray(Image.open(f).convert("RGB"), dtype=np.int16)


a = load("BV1qx5463Exr", 1.0)
H, W = a.shape[:2]
R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
print(f"frame {W}x{H}")

# --- find the neon border: strong magenta/red-dominant pixels ---
neon = (R > 140) & (R - G > 50) & (B - G > 25)
print(f"neon-magenta pixels: {neon.sum()}")
cols = np.where(neon.any(axis=0))[0]
rows = np.where(neon.any(axis=1))[0]
print(f"  neon bbox cols {cols[0]}..{cols[-1]} (w={cols[-1]-cols[0]+1}, "
      f"{(cols[-1]-cols[0]+1)/W*100:.1f}% of {W})")
print(f"  neon bbox rows {rows[0]}..{rows[-1]} (h={rows[-1]-rows[0]+1}, "
      f"{(rows[-1]-rows[0]+1)/H*100:.1f}% of {H})")

# horizontal scan across the card's mid height to get border run lengths
y = (rows[0] + rows[-1]) // 2
run = neon[y]
segs, s = [], None
for x, v in enumerate(run):
    if v and s is None:
        s = x
    elif not v and s is not None:
        segs.append((s, x - 1)); s = None
print(f"  neon runs at y={y}: {segs}")

# --- card interior: identify the inner edge of the neon border on both sides ---
# left inner edge = end of the first neon run on each row; right inner edge = start of last
left_in, right_in = [], []
for yy in range(rows[0], rows[-1] + 1):
    r = neon[yy]
    idx = np.where(r)[0]
    if len(idx) > 6:
        left_in.append(idx[0:8].max())
        right_in.append(idx[-8:].min())
if left_in:
    li, ri = int(np.median(left_in)), int(np.median(right_in))
    print(f"  card inner span (median over rows): x {li}..{ri} "
          f"(w={ri-li+1}, {(ri-li+1)/W*100:.1f}% of {W})")
    print(f"  border thickness (outer bbox - inner): left={li-cols[0]}px right={cols[-1]-ri}px"
          f"  => ~{((li-cols[0])+(cols[-1]-ri))/2:.0f}px "
          f"({((li-cols[0])+(cols[-1]-ri))/2/W*100:.2f}% of width)")

# --- background corner luminance ---
lum = a.mean(axis=2)
print(f"  background corners: TL={lum[0:40,0:40].mean():.1f} TR={lum[0:40,-40:].mean():.1f} "
      f"BL={lum[-40:,0:40].mean():.1f} BR={lum[-40:,-40:].mean():.1f}")
print(f"  card centre lum={lum[H//2-100:H//2+100, W//2-100:W//2+100].mean():.1f}")

# --- title band 剪映教学 ---
t0, t1 = 20, 120
strip = a[t0:t1]
tmask = (strip.min(axis=2) > 180)
trows = np.where(tmask.any(axis=1))[0]
tcols = np.where(tmask.any(axis=0))[0]
if len(trows):
    print(f"  title '剪映教学' glyph rows {trows[0]+t0}..{trows[-1]+t0} "
          f"(h={trows[-1]-trows[0]+1}, {(trows[-1]-trows[0]+1)/H*100:.2f}% of {H})  "
          f"cols {tcols[0]}..{tcols[-1]} (w={tcols[-1]-tcols[0]+1})")

# --- vertical side label on the left ---
t0, t1 = 180, 420
strip = a[t0:t1, 40:130]
tmask = (strip.min(axis=2) > 180)
tcols = np.where(tmask.any(axis=0))[0]
trows = np.where(tmask.any(axis=1))[0]
if len(trows):
    print(f"  side label '效果展示' rows {trows[0]+t0}..{trows[-1]+t0} "
          f"cols {tcols[0]+40}..{tcols[-1]+40} (w={tcols[-1]-tcols[0]+1}, "
          f"h={trows[-1]-trows[0]+1})")

# --- background corner luminance ---
print(f"  background corners: TL={lum[0:40,0:40].mean():.1f} TR={lum[0:40,-40:].mean():.1f} "
      f"BL={lum[-40:,0:40].mean():.1f} BR={lum[-40:,-40:].mean():.1f}")
print(f"  centre of card lum={lum[H//2-100:H//2+100, W//2-100:W//2+100].mean():.1f}")
