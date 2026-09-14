"""把若干时刻的 HUD 带子拼成一张图，用来**肉眼核对击杀帧**。

## 为什么需要它

`detect_kills.py` 给出的击杀时刻，在此之前**从来没有被目视核对过** —— 全是信号处理的自证。
本轮就是靠"把横幅带子抽出来看一眼"，才发现底部标定截错了位置
（详情见 `detect_kills.py` 文件头的 ⚠️ 段 与 `references/kill-extraction.md`）。

**结论：击杀帧的提取必须有目视环节。** 这个脚本就是那个环节的入口。

## 用法

    # 看 4b0460c4 在 14.73s 附近到底有没有击杀横幅
    .venv\\Scripts\\python.exe tools/verify_kill_frames.py 原始素材\\4b0460c4....mp4 14.73

    # 一次核对多个时刻（每个时刻一张图）
    .venv\\Scripts\\python.exe tools/verify_kill_frames.py <视频> 4.60 9.97 14.73 16.73

输出：
  · `--outdir` 下每个时刻一张 PNG：**上=全画面上半，下=横幅带（y 按 --y0/--y1）**，
    并按 `--span/--step` 在时刻前后各抽几帧，纵向叠放。行序见打印。
  · 终端同时给出**数值代理**：横幅带里的洋红像素占比 + 带内高频能量。
    （只是代理，不是判据：本项目的击杀横幅是带洋红描边的半透明图形，
     占比很低，实测真横幅约 0.03、无横幅约 0.00 —— 数量级差 10 倍，但仍需目视确认。）
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

import numpy as np

try:
    import imageio_ffmpeg
    import imageio.v3 as iio
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (ImportError, AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]


def grab(ff: str, src: pathlib.Path, t: float) -> np.ndarray | None:
    p = subprocess.run(
        [ff, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(src),
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    if a.size < 1280 * 720 * 3:
        return None
    return a[:1280 * 720 * 3].reshape(720, 1280, 3)


def banner_proxy(img: np.ndarray) -> tuple[float, float]:
    """击杀横幅的数值代理：(洋红像素占比, 带内横向高频能量)。"""
    band = img[505:620, 380:900].astype(np.int16)
    R, G, B = band[..., 0], band[..., 1], band[..., 2]
    mag = ((R > 90) & (B > 110) & (G < 0.72 * np.maximum(R, B))
           & (np.abs(R - B) < 110)).mean()
    g = band.mean(axis=2)
    hf = np.abs(np.diff(g, axis=1)).mean()
    return round(float(mag), 4), round(float(hf), 2)


def main() -> int:
    ap = argparse.ArgumentParser(description="拼 HUD 带子图，肉眼核对击杀帧")
    ap.add_argument("video")
    ap.add_argument("times", nargs="+", type=float)
    ap.add_argument("--outdir", default=str(ROOT / "projects/game-001/ref-analysis/verify"))
    ap.add_argument("--span", type=float, default=0.4, help="时刻前后各看多久（秒）")
    ap.add_argument("--step", type=float, default=0.2, help="抽样间隔（秒）")
    ap.add_argument("--y0", type=int, default=380, help="带子上边界（720p 坐标）")
    ap.add_argument("--y1", type=int, default=720, help="带子下边界")
    ap.add_argument("--scale", type=int, default=2, help="下采样倍数")
    args = ap.parse_args()

    src = pathlib.Path(args.video)
    if not src.exists():
        print(f"[FAIL] 找不到 {src}", file=sys.stderr)
        return 2
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    n = int(round(2 * args.span / args.step)) + 1
    offsets = [round(-args.span + i * args.step, 3) for i in range(n)]

    print(f"=== {src.name} ===")
    print(f"带子 y{args.y0}~{args.y1}，每个时刻抽 {n} 帧：{offsets}")
    print(f"{'时刻':>8} {'洋红占比':>9} {'带内高频':>9}   图")
    for t in args.times:
        rows, ok = [], True
        for off in offsets:
            img = grab(ff, src, t + off)
            if img is None:
                ok = False
                break
            rows.append(img[args.y0:args.y1, :, :][::args.scale, ::args.scale])
            rows.append(np.full((3, rows[-1].shape[1], 3), 255, np.uint8))
        if not ok:
            print(f"{t:8.2f}  [skip] 抽帧失败（超出时长？）")
            continue
        stack = np.concatenate(rows[:-1], axis=0)
        p = outdir / f"verify_{src.stem[:8]}_{str(t).replace('.', 'p')}.png"
        iio.imwrite(p, stack)
        mag, hf = banner_proxy(grab(ff, src, t))
        print(f"{t:8.2f} {mag:9.4f} {hf:9.2f}   {p.name}")
    print(f"\n图在 {outdir}；行序 = " + " ".join(f"{o:+.1f}" for o in offsets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
