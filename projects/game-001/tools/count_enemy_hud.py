"""数「敌方存活头像」—— 做一份**人类可读的击杀台账**，用来替代纯信号判据。

## 为什么需要它（本项目已经踩过的坑）

`analysis2/kills_mine*.json` 是**信号判据**产出的时间戳。第 4 轮已实证：
旧标定带（`y600~720`）只截到击杀横幅下缘 14px，**任何 HUD 变化都会误触发**
（`4b0460c4 @16.733` 目视确认是战术计分板，不是击杀）。

本轮目视又撞到两处**与信号不一致**：
- `4c58efb4 @1.433`：信号报击杀，放大看右上角 **5 个敌人头像全亮**。
- `b61cc53d @6.2`：右上角只有 **4 个亮**，`:10.0` 是 5 个 —— 位置对不上。

⇒ 不抽样了，**把"存活敌人数"沿时间整条数出来**。

## 判据演进（两次失败，别再用亮度）

| 版本 | 判据 | 结果 |
|---|---|---|
| v1 | 全局阈值 = 整条均值 P85 × 0.78 | ❌ 受击态（血条变红）把存活判成阵亡，2~5 乱跳 |
| v2 | 逐头像时间维归一化（P90 存活 / P10 阵亡 取中点） | ❌ 头像条是**彩色**的，`gray` 转换后存活/阵亡的灰度差被手机 HUD 的渐变底吃掉 |
| **v3（本版）** | **饱和度**：瓦的阵亡头像会**去色变灰** ⇒ 逐头像取 `mean(max(RGB)-min(RGB))` | ✅ 存活≈60~110，阵亡≈0~20，分离明显 |

## 用法

    .venv\\Scripts\\python.exe projects\\game-001\\tools\\count_enemy_hud.py 4c58efb4 b61cc53d
输出：projects/game-001/verification/hud/<short>.json（逐 0.5s 的 5 个饱和度 + 存活数）
"""
from __future__ import annotations

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
OUT = ROOT / "projects" / "game-001" / "verification" / "hud"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

HUD = (795, 4, 385, 36)      # x, y, w, h —— 1280x720 上的敌方头像条（实测）
FPS = 2.0


def frames(short: str) -> tuple[np.ndarray, list[float]]:
    src = next(SRC.glob(f"{short}*.mp4"))
    x, y, w, h = HUD
    raw = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(src),
         "-vf", f"fps={FPS},crop={w}:{h}:{x}:{y}",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    arr = np.frombuffer(raw, dtype=np.uint8)
    n = arr.size // (w * h * 3)
    return arr[: n * w * h * 3].reshape(n, h, w, 3), [i / FPS for i in range(n)]


def saturation(frame: np.ndarray) -> list[float]:
    """每个头像的"平均饱和度"：阵亡头像被去色 ⇒ 该值塌到接近 0。"""
    _, w, _ = frame.shape
    seg = w // 5
    out = []
    for i in range(5):
        part = frame[:, i * seg:(i + 1) * seg].astype(np.float32)
        sat = part.max(axis=2) - part.min(axis=2)
        out.append(float(sat.mean()))
    return out


def main() -> int:
    shorts = sys.argv[1:] or ["4c58efb4"]
    OUT.mkdir(parents=True, exist_ok=True)
    for short in shorts:
        arr, ts = frames(short)
        sat = np.array([saturation(f) for f in arr])              # (n, 5)
        lo = np.percentile(sat, 5, axis=0)
        hi = np.percentile(sat, 95, axis=0)
        thr = lo + (hi - lo) * 0.45          # 偏"存活"一侧：宁可漏判阵亡，不可误判
        alive_mat = sat >= thr[None, :]
        alive = alive_mat.sum(axis=1).astype(int)

        rows = [{"t": round(t, 3), "alive": int(a), "sat": [round(float(v), 1) for v in s]}
                for t, a, s in zip(ts, alive, sat)]
        OUT.joinpath(f"{short}.json").write_text(json.dumps(
            {"short": short, "hud_box": HUD, "fps": FPS, "metric": "mean saturation per portrait",
             "per_portrait_thr": [round(float(v), 1) for v in thr],
             "per_portrait_lo": [round(float(v), 1) for v in lo],
             "per_portrait_hi": [round(float(v), 1) for v in hi],
             "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

        print(f"=== {short} ===  饱和度高/低 {np.round(hi,1)} / {np.round(lo,1)}  阈值 {np.round(thr,1)}")
        prev = None
        for t, a in zip(ts, alive):
            if a != prev:
                print(f"   t={t:6.1f}s  存活敌人 {a}/5")
                prev = a
        print(f"   → projects/game-001/verification/hud/{short}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
