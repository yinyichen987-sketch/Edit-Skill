"""L1 measurements for the vertical tutorial BV1ue8y6XE2M (击杀结尾/氛围感).

Measures, per frame:
  * row luminance profile inside declared regions
  * text row bands (rows whose bright/white pixel count stands out)
  * max glyph height per band  -> font size as fraction of frame height
  * horizontal extent of the band -> caption box width
Also: transcript-region candidate check (white text on black box).

Nothing here is guessed: every number printed comes from numpy on a real frame.
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


def frame(stem: str, t: float) -> np.ndarray:
    f = FRM / f"f_{stem}_{t:07.2f}.png"
    if not f.exists():
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(VID / f"{stem}.mp4"), "-frames:v", "1", "-y", str(f)],
                       capture_output=True)
    return np.asarray(Image.open(f).convert("RGB"), dtype=np.float32)


def bands(mask: np.ndarray, min_rows: int = 3):
    """Contiguous runs of True rows -> list of (y0, y1) inclusive."""
    out, start = [], None
    for y, v in enumerate(mask):
        if v and start is None:
            start = y
        elif not v and start is not None:
            if y - start >= min_rows:
                out.append((start, y - 1))
            start = None
    if start is not None and len(mask) - start >= min_rows:
        out.append((start, len(mask) - 1))
    return out


def analyse(stem: str, t: float, y0: int, y1: int, x0: int, x1: int,
            tag: str, white_min: int = 200, thresh_frac: float = 0.06):
    a = frame(stem, t)[y0:y1, x0:x1]
    H, W = a.shape[:2]
    lum = a.mean(axis=2)
    mn = a.min(axis=2)
    mx = a.max(axis=2)
    is_white = (mn > white_min)
    cnt = is_white.sum(axis=1)
    thr = max(2, int(W * thresh_frac * 0.1))
    mask = cnt > thr
    print(f"\n--- {tag} | {stem}@{t}s  region y[{y0}:{y1}] x[{x0}:{x1}] "
          f"({W}x{H} px)  white_min={white_min} thr={thr}px ---")
    bl = bands(mask)
    if not bl:
        print("   no white-text band found")
    for (b0, b1) in bl:
        sub = is_white[b0:b1 + 1]
        cols = np.where(sub.any(axis=0))[0]
        nz = sub.sum()
        fill = nz / max((b1 - b0 + 1) * (cols[-1] - cols[0] + 1), 1)
        print(f"   band rows {b0+y0}..{b1+y0} (h={b1-b0+1}px, "
              f"{(b1-b0+1)/852*100:.2f}% of 852)  cols {cols[0]+x0}..{cols[-1]+x0} "
              f"(w={cols[-1]-cols[0]+1}px, {(cols[-1]-cols[0]+1)/480*100:.1f}% of 480)  "
              f"glyph_fill={fill:.2f}")
    # background behind the brightest band, to see if there is a plate
    for (b0, b1) in bl:
        pad0, pad1 = max(0, b0 - 6), min(H - 1, b1 + 6)
        strip = lum[pad0:pad1 + 1]
        print(f"   band {b0+y0}..{b1+y0}: lum min={strip.min():.1f} "
              f"p10={np.percentile(strip,10):.1f} med={np.median(strip):.1f} "
              f"p90={np.percentile(strip,90):.1f} max={strip.max():.1f}")
    return bl


if __name__ == "__main__":
    S = "BV1ue8y6XE2M"
    # 0.5s: 在我剪辑前  (large title under the preview)
    analyse(S, 0.5, 370, 440, 0, 480, "big title 在我剪辑前")
    # 2.0s and 3.0s: 在剪辑后 / 看看效果
    for t in (2.0, 3.0, 4.0):
        analyse(S, t, 370, 440, 0, 480, f"big title @{t}s")
    # 5.0: 在瓦里画了个ACE
    analyse(S, 5.0, 50, 120, 0, 480, "top label @5s")
    analyse(S, 8.0, 50, 120, 0, 480, "top label @8s")
    # transcript-ish black box region
    analyse(S, 40.0, 320, 440, 0, 480, "black box candidate @40s", white_min=170)
