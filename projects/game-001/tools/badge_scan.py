"""按「视觉形状」找瓦的 HUD 事件，而不是靠单色阈值。

背景（本机实测到的坑）：
- 「洋红/紫描边」在瓦里**到处都是**（技能特效、命中标记、被打中时的红色渐晕），
  用洋红占比当击杀判据会把**技能光效**判成击杀（`b61cc53d` 6.567s 就是一整屏洋红技能）。
- 顶级赛事观战 HUD 的「击杀卡片条」在**右下**，几张卡片横排，
  每张卡 = 迷你英雄头像 + 击杀者名 + 武器白图标 + 右侧被击杀者名（洋红色块）。
  形状特征：**大片接近纯白**（武器剪影）**贴着大面积洋红**，两者在同一水平带内相邻。

本工具输出**逐帧的候选时刻**，产出的是"候选"而不是"结论"——
必须再用 `crop_at.py` 抽帧目视确认（`verify_kill_frames.py` 的纪律）。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\badge_scan.py b61cc53d --t0 0 --t1 29
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\badge_scan.py b61cc53d --t0 0 --t1 29 --full
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
OUT = ROOT / "projects" / "game-001" / "verification" / "badge_scan"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720

WHITE_TH = 235
WHITE_TOL = 12
MAG_TH = 40


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


def row_metrics(fr: np.ndarray):
    f = fr.astype(np.int16)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    near_white = (r >= WHITE_TH) & (g >= WHITE_TH) & (b >= WHITE_TH) & \
                 (np.abs(r - g) <= WHITE_TOL) & (np.abs(g - b) <= WHITE_TOL)
    magenta = (r - g > MAG_TH) & (b - g > MAG_TH)
    return near_white, magenta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=None)
    ap.add_argument("--rows", default="8:100", help="search band y0:y1 (default 8:100 = 顶级赛 HUD 卡片条)")
    ap.add_argument("--min-white", type=int, default=900, help="该带内近白像素下限")
    ap.add_argument("--min-mag", type=int, default=250, help="该带内洋红像素下限")
    a = ap.parse_args()

    y0, y1 = (int(v) for v in a.rows.split(":"))
    t1 = a.t1 if a.t1 is not None else 29.0
    fr = decode(a.short, a.t0, t1)
    n = fr.shape[0]
    ts = a.t0 + np.arange(n) / 30.0
    nw, mg = row_metrics(fr)
    band_w = nw[:, y0:y1, :].sum(axis=(1, 2))
    band_m = mg[:, y0:y1, :].sum(axis=(1, 2))
    print(f"[{a.short}] n={n} band y{y0}-{y1}  near-white med={np.median(band_w):.0f} "
          f"magenta med={np.median(band_m):.0f}")

    hit = (band_w >= a.min_white) & (band_m >= a.min_mag)
    segs = []
    i = 0
    while i < n:
        if hit[i]:
            j = i
            while j + 1 < n and hit[j + 1]:
                j += 1
            segs.append((i, j))
            i = j + 1
        else:
            i += 1

    print(f"  候选段（近白≥{a.min_white} 且 洋红≥{a.min_mag} 同时成立）: {len(segs)}")
    for i, j in segs:
        peak_w = int(band_w[i:j + 1].max())
        peak_m = int(band_m[i:j + 1].max())
        print(f"   {ts[i]:7.3f} ~ {ts[j]:7.3f}  {(j - i + 1) * 33.3:5.0f} ms  "
              f"peakWhite={peak_w:6d} peakMag={peak_m:6d}")

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{a.short}_{a.t0:.2f}-{t1:.2f}_y{y0}-{y1}.json"
    dst.write_text(json.dumps({
        "t": ts.tolist(), "band_white": band_w.tolist(), "band_magenta": band_m.tolist(),
        "segments": [[float(ts[i]), float(ts[j])] for i, j in segs],
    }), encoding="utf-8")
    print(f"[OK] {dst.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
