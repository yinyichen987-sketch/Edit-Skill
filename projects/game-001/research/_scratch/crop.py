# -*- coding: utf-8 -*-
"""Crop + upscale a region of a frame so small UI text becomes readable."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

# regions in fractions of (w,h): name -> (l,t,r,b)
REGIONS = {
    "right": (0.63, 0.06, 1.00, 0.62),   # 剪映 right parameter panel
    "left": (0.00, 0.05, 0.30, 0.62),    # left material/effect panel
    "top": (0.00, 0.00, 1.00, 0.07),     # top tab bar
    "sub": (0.05, 0.78, 1.00, 1.00),     # burned-in subtitles
    "rail": (0.00, 0.44, 1.00, 0.53),    # toolbar icons
    "tl": (0.00, 0.50, 1.00, 0.95),      # timeline
}


def crop(src, region, out, scale=2.6):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    l, t, r, b = REGIONS[region]
    box = (int(l * w), int(t * h), int(r * w), int(b * h))
    c = im.crop(box)
    c = c.resize((int(c.width * scale), int(c.height * scale)), Image.LANCZOS)
    c.save(out, quality=95)
    return out, c.size


if __name__ == "__main__":
    src = sys.argv[1]
    region = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else "crop_out.jpg"
    scale = float(sys.argv[4]) if len(sys.argv) > 4 else 2.6
    o, size = crop(src, region, out, scale)
    print(o, size)
