"""Draw coordinate rulers on real VALORANT frames so HUD regions can be read off by eye.

Outputs (into research/_hud/):
  full_grid_<clip>_<t>.png     full frame + 100px grid, labelled
  tr_killfeed.png              top-right crop, 4x zoom, 10px ruler
  bottom_banner.png            bottom strip crop, 4x zoom, 10px ruler
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

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
OUT = ROOT / "projects" / "game-001" / "research" / "_hud"
OUT.mkdir(parents=True, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()

CLIP = SRC / "4b0460c400bbb5320acb6063b4f59358.mp4"
W, H = 1280, 720


def grab(t: float) -> Image.Image:
    p = OUT / f"raw_{t:.3f}.png"
    if not p.exists():
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(CLIP), "-frames:v", "1", "-y", str(p)],
                       capture_output=True)
    return Image.open(p).convert("RGB")


def grid(img: Image.Image, step=100, zoom=1) -> Image.Image:
    im = img.resize((img.width * zoom, img.height * zoom), Image.NEAREST).convert("RGB")
    d = ImageDraw.Draw(im)
    for x in range(0, img.width + 1, step):
        d.line([(x * zoom, 0), (x * zoom, im.height)], fill=(255, 0, 0), width=1)
        d.text((x * zoom + 2, 2), str(x), fill=(255, 255, 0))
    for y in range(0, img.height + 1, step):
        d.line([(0, y * zoom), (im.width, y * zoom)], fill=(255, 0, 0), width=1)
        d.text((2, y * zoom + 2), str(y), fill=(0, 255, 255))
    return im


def ruler(img: Image.Image, origin, zoom=4, step=10, axis="both") -> Image.Image:
    im = img.resize((img.width * zoom, img.height * zoom), Image.NEAREST).convert("RGB")
    d = ImageDraw.Draw(im)
    ox, oy = origin
    if axis in ("both", "x"):
        for x in range(0, img.width + 1, step):
            real = ox + x
            col = (255, 0, 0) if real % 50 == 0 else (255, 140, 0)
            d.line([(x * zoom, 0), (x * zoom, 12)], fill=col, width=1)
            if real % 50 == 0:
                d.text((x * zoom + 1, 1), str(real), fill=(255, 255, 0))
    if axis in ("both", "y"):
        for y in range(0, img.height + 1, step):
            real = oy + y
            col = (0, 255, 0) if real % 50 == 0 else (0, 180, 255)
            d.line([(0, y * zoom), (12, y * zoom)], fill=col, width=1)
            if real % 50 == 0:
                d.text((1, y * zoom + 1), str(real), fill=(0, 255, 255))
    return im


# full frame with grid (feed present)
img = grab(4.75)
grid(img, step=100, zoom=1).save(OUT / "full_grid_4.75.png")
img2 = grab(4.30)
grid(img2, step=100, zoom=1).save(OUT / "full_grid_4.30.png")

# top-right kill feed, generous crop then 4x with ruler
tr = img.crop((900, 0, 1280, 160))
ruler(tr, (900, 0), zoom=4).save(OUT / "tr_killfeed.png")

# bottom strip
bo = img.crop((0, 580, 1280, 720))
ruler(bo, (0, 580), zoom=2).save(OUT / "bottom_banner.png")

# bottom-centre detail
bc = img.crop((380, 580, 900, 720))
ruler(bc, (380, 580), zoom=3).save(OUT / "bottom_center.png")

print("wrote:")
for p in sorted(OUT.glob("*.png")):
    print(f"  {p.relative_to(ROOT)}  {Image.open(p).size}")
