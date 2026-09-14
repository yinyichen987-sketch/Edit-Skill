"""在**右上角播报卡条**里数「有几条击杀卡」——利用形状而不是颜色。

本机目视确认的卡片结构（1280x720，`4b0460c4` @10.7 / `b61cc53d` @11.0，见
`verification/frames/*_640x96_640_8_k3.png`）：

    [迷你英雄头像] [击杀者名] [高亮竖条] [武器白色剪影] [十字/图标] [被击杀者名牌(队伍色)] [被击杀者头像]

⇒ **一行卡片 = 左侧有彩色头像 + 中段以近白色为主（武器剪影）**。
聊天/播报文字行只有文字，**没有头像也没有大片近白**。据此可以机械区分。

判据（逐帧，在给定搜索带内）：
  1. 对每一行 y 统计「近白像素数」→ 取 8 行平滑；
  2. 近白行数 ≥ MINWHITE（默认 8 行）→ 归为一个「白团」；
  3. 白团左侧 x∈[xL0,xL1] 内必须有「彩色饱和度高的像素」≥ MINCOL（头像）；
  4. 白团之间用 ≥GAP 行的非白行分隔，才算两条不同卡片。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\feed_rows.py b61cc53d --t0 0 --t1 29
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

import imageio_ffmpeg
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
OUT = ROOT / "projects" / "game-001" / "verification" / "feed_rows"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720


def decode(short: str, t0: float, t1: float) -> np.ndarray:
    src = next(SRC.glob(f"{short}*.mp4"))
    raw = subprocess.run(
        [FFMPEG, "-v", "error", "-ss", f"{t0:.4f}", "-i", str(src), "-t", f"{t1 - t0:.4f}",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    a = np.frombuffer(raw, dtype=np.uint8)
    n = a.size // (W * H * 3)
    return a[: n * W * H * 3].reshape(n, H, W, 3)


def count_cards(fr: np.ndarray, y0: int, y1: int, xL0: int, xL1: int,
                xw0: int, xw1: int, min_white: int, min_col: int, gap: int) -> int:
    f = fr.astype(np.int16)
    sub = f[y0:y1]
    r, g, b = sub[..., 0], sub[..., 1], sub[..., 2]
    white = ((r >= 225) & (g >= 225) & (b >= 225) &
             (np.abs(r - g) <= 14) & (np.abs(g - b) <= 14))
    col = ((sub.max(axis=2) - sub.min(axis=2)) > 60)
    wrow = white[:, xw0:xw1].sum(axis=1)
    crow = col[:, xL0:xL1].sum(axis=1)
    hot = (wrow >= min_white) & (crow >= min_col)
    # 形态学闭运算：先膨胀 gap 行再腐蚀，合并被 1~2 行非白切开的白团
    k = max(1, gap)
    if k > 1:
        ker = np.ones(k, dtype=bool)
        hot = np.convolve(hot.astype(np.int8), ker, mode="same") > 0
        hot = np.convolve(hot.astype(np.int8), ker, mode="same") >= k
    segs = 0
    prev = False
    for v in hot:
        if v and not prev:
            segs += 1
        prev = bool(v)
    return segs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=None)
    ap.add_argument("--band", default="8:130", help="搜索带 y0:y1")
    ap.add_argument("--portrait-x", default="660:760", help="头像所在 x 范围")
    ap.add_argument("--weapon-x", default="800:1000", help="武器白色剪影所在 x 范围")
    ap.add_argument("--min-white", type=int, default=20)
    ap.add_argument("--min-col", type=int, default=12)
    ap.add_argument("--gap", type=int, default=3)
    a = ap.parse_args()

    y0, y1 = (int(v) for v in a.band.split(":"))
    xL0, xL1 = (int(v) for v in a.portrait_x.split(":"))
    xw0, xw1 = (int(v) for v in a.weapon_x.split(":"))
    t1 = a.t1 if a.t1 is not None else 29.0
    fr = decode(a.short, a.t0, t1)
    n = fr.shape[0]
    ts = a.t0 + np.arange(n) / 30.0
    cards = np.array([count_cards(fr[i], y0, y1, xL0, xL1, xw0, xw1,
                                  a.min_white, a.min_col, a.gap) for i in range(n)])
    print(f"[{a.short}] n={n} band y{y0}-{y1} 卡片数分布: "
          + ", ".join(f"{v}:{int((cards == v).sum())}" for v in sorted(set(cards.tolist()))))
    print("  卡片数变化时刻（上行→下行）:")
    for i in range(1, n):
        if cards[i] != cards[i - 1]:
            print(f"   {ts[i]:7.3f}  {cards[i-1]} -> {cards[i]}")
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{a.short}_{a.t0:.2f}-{t1:.2f}.json"
    dst.write_text(json.dumps({"t": ts.tolist(), "cards": cards.tolist()}), encoding="utf-8")
    print(f"[OK] {dst.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
