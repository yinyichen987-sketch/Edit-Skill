"""Crop a region out of an extracted frame (upscaled) so UI text is readable.

Usage:
  python crop_ui.py <stem> <t> <x0> <y0> <x1> <y1> <outname> [scale]
Coordinates are in ORIGINAL video pixels. Output -> _frames/<outname>
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

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


def frame(stem: str, t: float) -> pathlib.Path:
    f = FRM / f"f_{stem}_{t:07.2f}.png"
    if not f.exists():
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(VID / f"{stem}.mp4"), "-frames:v", "1", "-y", str(f)],
                       capture_output=True)
    return f


if __name__ == "__main__":
    a = sys.argv[1:]
    stem, t = a[0], float(a[1])
    x0, y0, x1, y1 = (int(v) for v in a[2:6])
    name = a[6]
    scale = float(a[7]) if len(a) > 7 else 3.0
    im = Image.open(frame(stem, t)).convert("RGB").crop((x0, y0, x1, y1))
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    im.save(FRM / name)
    print(f"{name} {im.size} from {stem} @{t}s crop=({x0},{y0},{x1},{y1})")
