"""把某条素材某个时刻的**击杀播报区**放大成对照条，用于目视核准击杀时刻。

为什么需要它：本项目 `kill-extraction.md` 记着一次实证的标定错误 —— 旧带子
（`crop=1280:120:0:600`）只截到击杀横幅下缘 14px，任何 HUD 变化都会误触发。
所以"信号给了个时间戳"不等于"那里真有一次击杀"（`docs/lessons.md` 第 4 轮）。
本工具把 1280x720 画面**右上角的击杀 feed 条**与**画面中部偏下的击杀横幅**
同时放大，让人（或 agent 的读图能力）直接读出「谁击杀了谁」。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\zoom_killfeed.py 4c58efb4 1.433 2.100 4.667 7.333

输出：projects/game-001/verification/killfeed/<short>_t<时刻>.png（每个时刻一张，3 帧叠图）
"""
from __future__ import annotations

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
OUT = ROOT / "projects" / "game-001" / "verification" / "killfeed"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# 1280x720 上的裁剪框（实测口径，见 references/kill-extraction.md §4）
#   右上 feed：横向右上角那一条
FEED = "crop=460:30:818:0"
#   中部击杀横幅：y522~613 是实测位置（旧标定 y600 只截到 14px）
BANNER = "crop=520:60:380:518"


def frames(short: str, t: float, n: int = 3, fps: float = 30.0) -> list[np.ndarray]:
    src = next(SRC.glob(f"{short}*.mp4"))
    out = []
    for k in range(n):
        out.append(_one(src, t + k / fps))
    return out


def _one(src: pathlib.Path, t: float) -> np.ndarray:
    raw = subprocess.run(
        [FFMPEG, "-v", "error", "-ss", f"{t:.4f}", "-i", str(src),
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True,
    ).stdout
    return iio.imread(raw)[:, :, :3]


def crop(img: np.ndarray, w: int, h: int, x: int, y: int) -> np.ndarray:
    return img[y:y + h, x:x + w]


def scale(img: np.ndarray, k: int) -> np.ndarray:
    return np.repeat(np.repeat(img, k, axis=0), k, axis=1)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    short = sys.argv[1]
    stamp_list = [float(x) for x in sys.argv[2:]]
    OUT.mkdir(parents=True, exist_ok=True)

    for t in stamp_list:
        fs = frames(short, t)
        row_gap = 8
        panes = []
        for img in fs:
            feed = scale(crop(img, 460, 30, 818, 0), 2)        # 右上 feed
            ban = scale(crop(img, 520, 60, 380, 518), 2)       # 击杀横幅带
            w = max(feed.shape[1], ban.shape[1])
            feed = np.pad(feed, ((0, 0), (0, w - feed.shape[1]), (0, 0)))
            ban = np.pad(ban, ((0, 0), (0, w - ban.shape[1]), (0, 0)))
            gap = np.full((row_gap, w, 3), 40, np.uint8)
            panes.append(np.concatenate([feed, gap, ban], axis=0))
        sep = np.full((panes[0].shape[0], 6, 3), 200, np.uint8)
        sheet = panes[0]
        for p in panes[1:]:
            sheet = np.concatenate([sheet, sep, p], axis=1)
        dst = OUT / f"{short}_t{t:.3f}.png"
        iio.imwrite(dst, sheet)
        print(f"[OK] {dst.relative_to(ROOT)}  （3 帧：t, t+1/30, t+2/30；每张上半=右上 feed，下半=中部横幅）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
