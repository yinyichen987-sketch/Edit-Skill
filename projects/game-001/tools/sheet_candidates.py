"""目视核对素材候选窗口：把每个候选区间抽成联系表（contact sheet）。

用途：`make_single_v3.py` 选素材前，**先看一眼**候选窗口里到底有没有真实的连杀，
而不是只信 `analysis2/kills_mine_measured.json` 的时间戳（那是信号判据，本项目已因
"信号自证不算验证"踩过一次坑 —— 见 `docs/lessons.md` 第 4 轮）。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\sheet_candidates.py

输出：projects/game-001/verification/candidates/<short>_<t0>-<t1>.png
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import imageio_ffmpeg
import numpy as np
import imageio.v3 as iio

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
OUT = ROOT / "projects" / "game-001" / "verification" / "candidates"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# (short, t0, t1, 步长) —— 区间来自 analysis2/kills_mine_measured.json + multikill_clusters.json
CANDIDATES = [
    ("7f0d8287", 33.0, 41.5, 0.25),    # 33.5 / 38.4 / 39.6 三杀
    ("b61cc53d", 5.5, 14.5, 0.25),     # 6.2/6.8 + 9.6/10.7/11.8 五杀
    ("38cc4903", 0.0, 11.5, 0.25),     # 1.3/2.2/2.9 + 6.8/8.7/10.4 六杀
    ("4c58efb4", 0.0, 8.5, 0.25),      # 1.4/2.1/4.7/7.3 四杀
    ("58b8e283", 19.5, 29.0, 0.25),    # 20.9/21.8/26.6/27.2 四杀
]


def grab(path: pathlib.Path, t: float) -> np.ndarray:
    out = subprocess.run(
        [FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", str(path),
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True,
    ).stdout
    img = iio.imread(out)
    if img.ndim == 2:
        img = np.stack([img] * 3, axis=-1)
    return img[:, :, :3]


def sheet(short: str, t0: float, t1: float, step: float) -> pathlib.Path:
    src = next(SRC.glob(f"{short}*.mp4"))
    times = [round(t0 + i * step, 3) for i in range(int((t1 - t0) / step) + 1)]
    cols = 6
    rows = (len(times) + cols - 1) // cols
    tw, th = 320, 180
    canvas = np.zeros((rows * (th + 14), cols * tw, 3), dtype=np.uint8)

    for idx, t in enumerate(times):
        r, c = divmod(idx, cols)
        frame = grab(src, t)
        # 最近邻缩放到缩略图尺寸（不引入插值模糊）
        ys = (np.arange(th) * frame.shape[0] // th)
        xs = (np.arange(tw) * frame.shape[1] // tw)
        thumb = frame[ys][:, xs]
        canvas[r * (th + 14): r * (th + 14) + th, c * tw:(c + 1) * tw] = thumb
        # 左侧 4px 深色标记，方便数格子（每格 = step 秒）
        canvas[r * (th + 14): r * (th + 14) + 4, c * tw:(c + 1) * tw] = (0, 90, 200)

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{short}_{t0:.1f}-{t1:.1f}.png"
    iio.imwrite(dst, canvas)
    print(f"[OK] {dst.relative_to(ROOT)}  {len(times)} 帧 × {step}s  起点 {t0}s")
    return dst


def main() -> int:
    for short, t0, t1, step in CANDIDATES:
        sheet(short, t0, t1, step)
    print("\n读法：左上→右下，逐格 +%.2fs（每格左上角有蓝条）。" % CANDIDATES[0][3])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
