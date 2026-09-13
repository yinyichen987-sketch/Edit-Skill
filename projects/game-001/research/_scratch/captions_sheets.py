"""Generic contact-sheet builder for the captions/hooks tutorial mining task.

Usage: python captions_sheets.py <stem> <t0> <t1> <n> <name> [cw] [fps]
Extracts n frames evenly across [t0,t1], tiles them into a grid, labels each
with timestamp + frame index, saves to _frames/<name>.
"""
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
FRM = ROOT / "projects" / "game-001" / "research" / "_frames"
FRM.mkdir(parents=True, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()

COLS = 4


def grab(stem: str, t: float) -> Image.Image:
    f = FRM / f"f_{stem}_{t:07.2f}.png"
    if not f.exists():
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(VID / f"{stem}.mp4"), "-frames:v", "1", "-y", str(f)],
                       capture_output=True)
    return Image.open(f).convert("RGB")


def sheet(stem: str, t0: float, t1: float, n: int, name: str, cw: int = 420, fps: float = 30.0):
    imgs = []
    ts = [t0 + k * (t1 - t0) / max(n - 1, 1) for k in range(n)]
    for t in ts:
        im = grab(stem, t)
        ch = int(im.height * cw / im.width)
        im = im.resize((cw, ch))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 108, 18], fill=(0, 0, 0))
        d.text((4, 4), f"{t:7.2f}s", fill=(255, 255, 0))
        d.rectangle([0, im.height - 16, 108, im.height], fill=(0, 0, 0))
        d.text((4, im.height - 14), f"f{int(t*fps)}", fill=(0, 255, 128))
        imgs.append(im)
    ch = max(i.height for i in imgs)
    rows = (len(imgs) + COLS - 1) // COLS
    S = Image.new("RGB", (COLS * cw, rows * ch), (25, 25, 25))
    for i, im in enumerate(imgs):
        S.paste(im, ((i % COLS) * cw, (i // COLS) * ch))
    out = FRM / name
    S.save(out)
    print(f"{name}  {S.size}  {t0:.2f}..{t1:.2f}s  n={n}")


if __name__ == "__main__":
    a = sys.argv[1:]
    stem, t0, t1, n, name = a[0], float(a[1]), float(a[2]), int(a[3]), a[4]
    cw = int(a[5]) if len(a) > 5 else 420
    fps = float(a[6]) if len(a) > 6 else 30.0
    sheet(stem, t0, t1, n, name, cw, fps)
