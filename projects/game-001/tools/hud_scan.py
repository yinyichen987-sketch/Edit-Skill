"""找「敌人阵亡那一帧」：对顶部敌人头像条逐帧做与"该条纹自身历史"的差分。

思路（与 `kill_timeline.py` 的固定带子不同）：
- 瓦的顶栏有一排**敌人头像 + 血条**。某人阵亡时，其头像**去色变灰**、血条消失、
  并且顶部会弹出一条**击杀播报**（该播报也在顶部区域）。
- 因此「顶部条」的变化量是击杀的候选信号，但它同时被**玩家自己的准星/手臂/技能特效**
  污染（那些也在顶部区域）——所以这里把顶部条**切成横条块**分别统计，
  谁在变就能看出是左（自己队/比分）还是右（敌人）。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\hud_scan.py b61cc53d --t0 5.5 --t1 9.0
输出 JSON + 控制台按块的逐帧变化表（只打印有变化的帧）。
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
OUT = ROOT / "projects" / "game-001" / "verification" / "hud_scan"
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
    return a[: n * W * H * 3].reshape(n, H, W, 3).astype(np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    ap.add_argument("--t0", type=float, required=True)
    ap.add_argument("--t1", type=float, required=True)
    ap.add_argument("--thr", type=int, default=26)
    a = ap.parse_args()

    fr = decode(a.short, a.t0, a.t1)
    n = fr.shape[0]
    ts = a.t0 + np.arange(n) / 30.0
    print(f"[{a.short}] n={n}  {a.t0:.2f}~{a.t1:.2f}s  thr={a.thr}")

    # 顶栏：y0..y96 全宽；横切成 8 块（每块 160px）看是谁在变
    top = fr[:, 0:96, :, :]
    blocks = [top[:, :, i * 160:(i + 1) * 160, :] for i in range(8)]
    d = [np.abs(np.diff(b, axis=0)).max(axis=3) for b in blocks]
    frac = [ (dd > a.thr).mean(axis=(1, 2)) for dd in d ]  # 每块：长度 n-1

    rows = []
    for i in range(1, n):
        f = [float(frac[b][i - 1]) for b in range(8)]
        tot = float(np.mean(f))
        rows.append((i, float(ts[i]), tot, f))
    rows_sorted = sorted(rows[1:], key=lambda r: -r[2])[:25]
    print("  帧变化最大的 25 帧（t, 总变化, 8 块各自变化）")
    for i, t, tot, f in sorted(rows_sorted, key=lambda r: r[1]):
        print(f"   t={t:7.3f} tot={tot:.4f}  " + " ".join(f"{v:.3f}" for v in f))

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{a.short}_{a.t0:.2f}-{a.t1:.2f}.json"
    dst.write_text(json.dumps({"t": [r[1] for r in rows], "tot": [r[2] for r in rows],
                               "blocks": [r[3] for r in rows]}), encoding="utf-8")
    print(f"[OK] {dst.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
