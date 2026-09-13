"""Crop + measure the 剪映-style UI of BV1ue8y6XE2M (击杀结尾) and BV1qx5463Exr (卡点)."""
from __future__ import annotations

import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parents[4]
FRM = ROOT / "projects" / "game-001" / "research" / "_frames"


def load(stem: str, t: float) -> Image.Image:
    return Image.open(FRM / f"f_{stem}_{t:07.2f}.png").convert("RGB")


def crop(stem: str, t: float, box, name: str, scale: float = 3.0):
    im = load(stem, t).crop(box)
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    im.save(FRM / name)
    print(f"{name} {im.size}  {stem}@{t}s crop={box}")


def rows_white(stem: str, t: float, white_min=200, min_px=6):
    a = np.asarray(load(stem, t), dtype=np.float32)
    w = (a.min(axis=2) > white_min)
    cnt = w.sum(axis=1)
    out = []
    start = None
    for y, c in enumerate(cnt):
        if c > min_px and start is None:
            start = y
        elif c <= min_px and start is not None:
            if y - start >= 2:
                out.append((start, y - 1, int(cnt[start:y].max())))
            start = None
    return a.shape[0], out


if __name__ == "__main__":
    print("=== white-text rows, BV1ue8y6XE2M ===")
    for t in (0.5, 5.0, 8.0, 22.0, 40.0, 55.0, 60.0):
        H, r = rows_white("BV1ue8y6XE2M", t)
        print(f"  @{t}s (H={H}): " + "; ".join(f"{a}-{b}(max{c})" for a, b, c in r))
    print("\n=== white-text rows, BV1qx5463Exr ===")
    for t in (6.0, 12.0, 30.0):
        H, r = rows_white("BV1qx5463Exr", t)
        print(f"  @{t}s (H={H}): " + "; ".join(f"{a}-{b}(max{c})" for a, b, c in r))
