"""Extract a single full-resolution frame at time t."""
from __future__ import annotations

import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw
import imageio_ffmpeg

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parents[4]
VID = ROOT / "参考视频" / "教学"
OUT = ROOT / "projects" / "game-001" / "research" / "_frames"
OUT.mkdir(parents=True, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()


def frame(stem: str, t: float):
    f = OUT / f"{stem}_{t:07.2f}.png"
    if not f.exists():
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(VID / f"{stem}.mp4"), "-frames:v", "1", "-y", str(f)],
                       capture_output=True)
    return f


if __name__ == "__main__":
    stem = sys.argv[1]
    for a in sys.argv[2:]:
        p = frame(stem, float(a))
        im = Image.open(p)
        print(f"{p.name}  {im.size}")
