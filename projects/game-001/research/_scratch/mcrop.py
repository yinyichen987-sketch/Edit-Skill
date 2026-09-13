"""Crop a rectangle out of an already-extracted frame and upscale, so read_image can read UI text."""
from __future__ import annotations

import sys
import pathlib

from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FR = pathlib.Path(__file__).resolve().parent.parent / "_frames"


def crop(stem: str, t: float, box, out: str, scale=1.0):
    src = FR / f"{stem}_{t:07.2f}.png"
    if not src.exists():
        print(f"!! missing {src}")
        return
    im = Image.open(src).convert("RGB")
    l, tp, r, b = box
    c = im.crop((l, tp, r, b))
    if scale != 1.0:
        c = c.resize((int(c.width * scale), int(c.height * scale)))
    dst = FR / out
    c.save(dst)
    print(f"{dst}  {im.size} -> {c.size}  box={box}")


if __name__ == "__main__":
    a = sys.argv[1:]
    stem = a[0]
    t = float(a[1])
    box = tuple(int(x) for x in a[2].split(","))
    out = a[3]
    sc = float(a[4]) if len(a) > 4 else 1.0
    crop(stem, t, box, out, sc)
