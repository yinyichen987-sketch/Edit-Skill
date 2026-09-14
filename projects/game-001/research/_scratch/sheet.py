"""Generic contact-sheet builder for tutorial mining.

usage:
  python sheet.py <stem> <t0> <t1> <n> <outname> [fps] [cols] [cw]

Extracts n frames evenly in [t0,t1], tiles them into one PNG with a timestamp
burned into each tile, so a single read_image call shows many moments.
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


def main():
    a = sys.argv[1:]
    stem = a[0]
    t0, t1 = float(a[1]), float(a[2])
    n = int(a[3])
    name = a[4]
    fps = float(a[5]) if len(a) > 5 else 30.0
    cols = int(a[6]) if len(a) > 6 else 3
    cw = int(a[7]) if len(a) > 7 else 620
    imgs = []
    for k in range(n):
        t = t0 + (t1 - t0) * k / max(n - 1, 1)
        p = frame(stem, t)
        if not p.exists():
            print(f"  !! missing {t:.2f}")
            continue
        im = Image.open(p).convert("RGB")
        ch = max(1, int(im.height * cw / im.width))
        im = im.resize((cw, ch))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 150, 26], fill=(0, 0, 0))
        d.text((6, 7), f"{t:.2f}s", fill=(255, 255, 0))
        imgs.append(im)
    ch = max(i.height for i in imgs)
    rows = (len(imgs) + cols - 1) // cols
    S = Image.new("RGB", (cols * cw, rows * ch), (18, 18, 18))
    for i, im in enumerate(imgs):
        S.paste(im, ((i % cols) * cw, (i // cols) * ch))
    S.save(OUT / name)
    print(f"  {name}  {S.size}  {len(imgs)} frames  t={t0:.2f}..{t1:.2f}")


def tile_existing(stem: str, times, name: str, cols: int = 2, cw: int = 620):
    imgs = []
    for t in times:
        p = frame(stem, t)
        if not p.exists():
            print(f"  !! missing {t:.2f}")
            continue
        im = Image.open(p).convert("RGB")
        ch = max(1, int(im.height * cw / im.width))
        im = im.resize((cw, ch))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 150, 26], fill=(0, 0, 0))
        d.text((6, 7), f"{t:.2f}s", fill=(255, 255, 0))
        imgs.append(im)
    ch = max(i.height for i in imgs)
    rows = (len(imgs) + cols - 1) // cols
    S = Image.new("RGB", (cols * cw, rows * ch), (18, 18, 18))
    for i, im in enumerate(imgs):
        S.paste(im, ((i % cols) * cw, (i // cols) * ch))
    S.save(OUT / name)
    print(f"  {name}  {S.size}  {len(imgs)} frames")


if __name__ == "__main__":
    if sys.argv[1] == "tile":
        stem = sys.argv[2]
        name = sys.argv[3]
        cols = int(sys.argv[4])
        cw = int(sys.argv[5])
        times = [float(x) for x in sys.argv[6:]]
        tile_existing(stem, times, name, cols, cw)
    else:
        main()
