"""把某条素材某时刻的整帧导出（可放大），用于**目视核准**击杀/横幅/播报。

与 `zoom_killfeed.py` 的分工：那个只抽 feed/横幅窄带（快，但读不出小字）；
这个出**整帧或任意框**，配 `--k` 放大，用来读击杀播报里的小字。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\frame_at.py <short> <t> [--crop W:H:X:Y] [--k 4]
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\frame_at.py 4c58efb4 4.667 --crop 620:60:660:2 --k 3
输出：projects/game-001/verification/frames/<short>_t<t>[_crop].png
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    ap.add_argument("t", type=float)
    ap.add_argument("--crop", default=None, help="W:H:X:Y（1280x720 坐标）")
    ap.add_argument("--k", type=int, default=1, help="放大倍数（最近邻）")
    a = ap.parse_args()

    src = next(SRC.glob(f"{a.short}*.mp4"))
    raw = subprocess.run(
        [FFMPEG, "-v", "error", "-ss", f"{a.t:.4f}", "-i", str(src),
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True,
    ).stdout
    img = iio.imread(raw)[:, :, :3]

    tag = ""
    if a.crop:
        w, h, x, y = (int(v) for v in a.crop.split(":"))
        img = img[y:y + h, x:x + w]
        tag = "_crop"
    if a.k > 1:
        img = np.repeat(np.repeat(img, a.k, axis=0), a.k, axis=1)
        tag += f"_k{a.k}"

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{a.short}_t{a.t:.3f}{tag}.png"
    iio.imwrite(dst, img)
    print(f"[OK] {dst.relative_to(ROOT)}  ({img.shape[1]}x{img.shape[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
