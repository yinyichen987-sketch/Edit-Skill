"""带裁剪标记命名的抽帧（frame_at.py 的 crop 文件名不含裁剪框，会互相覆盖）。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\crop_at.py <short> <t> <W:H:X:Y> [--k N]
输出：projects/game-001/verification/frames/<short>_t<t>_WxH_X_Y[_k].png
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

import imageio.v3 as iio
import imageio_ffmpeg
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
OUT = ROOT / "projects" / "game-001" / "verification" / "frames"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def grab(short: str, t: float, crop: str, k: int = 1, tag: str = ""):
    w, h, x, y = (int(v) for v in crop.split(":"))
    src = next(SRC.glob(f"{short}*.mp4"))
    raw = subprocess.run(
        [FFMPEG, "-v", "error", "-ss", f"{t:.4f}", "-i", str(src),
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True,
    ).stdout
    img = iio.imread(raw)[:, :, :3][y:y + h, x:x + w]
    if k > 1:
        img = np.repeat(np.repeat(img, k, axis=0), k, axis=1)
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{short}_t{t:.3f}_{w}x{h}_{x}_{y}{tag}{f'_k{k}' if k > 1 else ''}.png"
    iio.imwrite(dst, img)
    print(f"[OK] {dst.name}  ({img.shape[1]}x{img.shape[0]})")
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    ap.add_argument("t", type=float)
    ap.add_argument("crop", nargs="+", help="一个或多个 W:H:X:Y")
    ap.add_argument("--k", type=int, default=1)
    a = ap.parse_args()
    for c in a.crop:
        grab(a.short, a.t, c, a.k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
