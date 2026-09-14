"""扫描每条素材的**逐帧运动量**，用来把剪切点snap到"动作间隙"。

## 为什么要这个（来自本轮学习）
Premiere Gal 的 [Hide Jump Cuts Like a PRO](https://www.youtube.com/watch?v=wVmi89tBORc)
（16.6 万播放）与剪映教程都强调同一条**最基础、也最有效**的规则：

> "切割**不要切在画面动作的中间**（如人物抬手到一半被切断）——
>  画面会有'跳跃感'，观众会觉得卡顿。
>  正确做法：**等一个完整动作结束，在动作间隙切割**。"

> "切割后若动作衔接不自然，**按帧微调**直到动作衔接流畅。"

这条规则是**可以算出来的**：动作"间隙"= 逐帧差分（运动量）的**局部极小值**。
所以本脚本：

1. 把每条素材缩到很小（64×36 灰度）后逐帧取均值，得到**光流近似信号**；
2. 算出**逐帧运动量** `|Δ|`；
3. 输出整条信号，供 `build_by_exclusion.py` 把切点 snap 到附近的运动量低点。

## 局限（要说清楚）
- 缩到 64×36 后只剩"整幅画面的变化强度"，**区分不出是哪一块在动**
  （比如"人物抬手"与"镜头甩动"在数值上可能相同）；
- 因此它是**启发式**：把切点挪到"画面整体比较静"的时刻，
  比不上真正的人工逐帧微调，但比"在任意位置硬切"好得多。

用法：`.venv\\Scripts\\python.exe tools/motion_scan.py`
输出：`projects/game-001/analysis2/motion.json`
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np

try:
    import imageio_ffmpeg
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (ImportError, AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "原始素材"
OUT = ROOT / "projects" / "game-001" / "analysis2" / "motion.json"
W, H, FPS = 64, 36, 30.0


def motion(path: pathlib.Path) -> list[float]:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    p = subprocess.run(
        [ff, "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"],
        capture_output=True)
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    n = len(a) // (W * H)
    if n < 3:
        return []
    f = a[:n * W * H].reshape(n, H, W).astype(np.int16)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    # 归一化到 0–1，避免不同素材量纲不一致
    mx = float(d.max()) or 1.0
    return [round(float(x) / mx, 5) for x in d]


def main() -> int:
    if len(sys.argv) > 1:
        files = [pathlib.Path(a) for a in sys.argv[1:]]
    else:
        files = sorted(SRC.glob("*.mp4"))

    out: dict[str, dict] = {}
    print("=== 逐帧运动量扫描（64x36 灰度差分，已归一化）===")
    for f in files:
        sig = motion(f)
        out[f.stem[:8]] = {"file": f.name, "fps": FPS, "n": len(sig), "motion": sig}
        if sig:
            arr = np.array(sig)
            # 运动量最低的若干时刻（= 动作间隙候选）
            k = max(1, len(arr) // 60)          # 约每 2 秒取一个低点
            idx = np.argsort(arr)[:k * 3]
            idx.sort()
            lows = [round(i / FPS, 2) for i in idx]
            print(f"  {f.stem[:8]}  {len(sig)} 帧  均值 {arr.mean():.3f}  "
                  f"静点示例 {lows[:10]}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out), encoding="utf-8")
    print(f"\n  [OK] 已写出 {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
