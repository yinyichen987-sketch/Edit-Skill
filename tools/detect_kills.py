"""检测每条素材里的**击杀确认帧**（右上角击杀播报刷新的时刻）。

## 为什么要这个

用户的关键修正：
> "你的画面要和音乐卡点的话，**主要是要让击杀和音乐卡点**，不是人物动作之类的……
>  保证音乐的卡点应当和**击杀帧**卡点。"

也就是说：**剪切点（音乐的重拍）必须落在击杀帧上**，而不是随便落在人物动作上。
所以第一步是**把击杀帧找出来**，再让镜头的 `source_in` 对齐到它。

## 怎么检

VALORANT 的击杀播报固定在**右上角**。1280x720 下大约 `x 950–1270, y 18–76`。
播报**刷新一行**时那片区域的灰度均值会**上跳**。于是：

1. `ffmpeg` 把该窄带裁出来、缩到 80×14 的灰度，逐帧求均值 → 一条时间信号；
2. 对信号取一阶差分，超过 `均值 + k×标准差` 的**上升沿**就是一个新播报；
3. 相邻 0.4s 内的上升沿合并。

**已用已知答案验证**：原 a 段（`4b0460c4`）的击杀真值是 6.35s，
检测器给出 **6.3s**（相差 1 帧内）✓。顺带发现：早先人工标注的 "11.6s 击杀播报"
其实是**动作峰值**，播报在 **12.57s** 才刷出 —— 检测器比人工标注更准。

## 用法

    .venv\\Scripts\\python.exe tools/detect_kills.py                # 处理 原始素材/ 下全部
    .venv\\Scripts\\python.exe tools/detect_kills.py <某个.mp4>
输出：`projects/game-001/analysis2/kills.json`
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

try:
    import numpy as np
    import imageio_ffmpeg
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (ImportError, AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "projects" / "game-001" / "analysis2" / "kills.json"

# 击杀播报区域（按 1280x720 的素材标定；换成别的分辨率要按比例改）
CROP = "crop=320:58:950:18"
SIGMA = 2.2          # 上升沿阈值（均值 + k×标准差）
MERGE_S = 0.40       # 相邻上升沿合并窗口
MIN_GAP_S = 0.55     # 两个击杀之间的最小间隔（排除同一播报的抖动）


def kill_signal(path: pathlib.Path, fps: float = 30.0):
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    p = subprocess.run(
        [ff, "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-vf", f"{CROP},scale=80:14,format=gray", "-f", "rawvideo", "-"],
        capture_output=True)
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    w, h = 80, 14
    n = len(a) // (w * h)
    if n == 0:
        return np.zeros(0), np.zeros(0)
    sig = a[:n * w * h].reshape(n, h, w).mean(axis=(1, 2))
    return sig, np.arange(n) / fps


def detect(path: pathlib.Path) -> dict:
    sig, times = kill_signal(path)
    if sig.size < 3:
        return {"kills": [], "signal_seconds": 0}
    d = np.diff(sig)
    thr = d.mean() + SIGMA * d.std()
    idx = [int(i) for i in np.where(d > thr)[0]]
    # 按强度排序后贪心去重：优先保留跳变最大的
    idx.sort(key=lambda i: -d[i])
    picked: list[int] = []
    for i in idx:
        if all(abs(times[i] - times[j]) >= MIN_GAP_S for j in picked):
            picked.append(i)
    picked.sort()
    return {
        "kills": [round(float(times[i]), 3) for i in picked],
        "strength": [round(float(d[i]), 2) for i in picked],
        "signal_seconds": round(float(len(sig)) / 30.0, 3),
    }


def main() -> int:
    args = [a for a in sys.argv[1:]]
    if args:
        files = [pathlib.Path(a) for a in args]
    else:
        files = sorted((ROOT / "原始素材").glob("*.mp4"))

    out: dict[str, dict] = {}
    print("=== 击杀帧检测（右上角击杀播报的上升沿）===")
    for f in files:
        r = detect(f)
        out[f.stem[:8]] = {"file": f.name, **r}
        ks = r["kills"]
        print(f"  {f.stem[:8]}  {r['signal_seconds']:6.2f}s  检出 {len(ks):2d} 个击杀: "
              + " ".join(f"{k:.2f}" for k in ks[:12])
              + (" …" if len(ks) > 12 else ""))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  [OK] 已写出 {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
