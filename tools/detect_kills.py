"""检测**玩家自己**的击杀帧。

## 判据（来自用户的口头领域知识）

> "击杀的特征一般是**视频底下出现无畏契约专有击杀特效**，
>  同时**右上角弹出播报**。"

这条信息把检测精度提高了一个档次 —— 而且它解释了之前一直修不掉的问题：

- **右上角播报**里既有**你的击杀**，也有**队友的击杀**，还有**你被击杀**。
  只盯右上角 ⇒ 必然混进大量"跟你无关"的画面。
- **底部击杀特效只在你击杀时出现**。所以：

> ### ★ 判据 = 底部特效上升沿 **且** 右上播报上升沿（±0.8s 内共现）

### 在本项目已知片段上的验证（原 a 段 `4b0460c4`）

| 信号 | 上升沿时刻 |
|---|---|
| 右上播报 | 4.60 · 6.30 · 9.93 · 12.57 · 14.73 · 16.63 |
| 底部特效 | 4.13 · 4.73 · 9.37 · 14.70 · 16.67 |
| **共现（判定为"你的击杀"）** | **4.60 · 9.93 · 14.73 · 16.63** |

**6.30 与 12.57 只有右上、没有底部** ⇒ 大概率是**队友的击杀**。
这正是"太多画面跟击杀毫无关系"的根因 —— 此前我一直在拿队友的击杀当素材。

## 区域标定（素材 1280x720）

- 底部击杀特效：`crop=1280:120:0:600`（下缘 120px 全宽）
- 右上角播报：`crop=320:58:950:18`

## 用法

    .venv\\Scripts\\python.exe tools/detect_kills.py            # 全部 原始素材/
输出：`projects/game-001/analysis2/kills_mine.json`
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
OUT = ROOT / "projects" / "game-001" / "analysis2" / "kills_mine.json"

BOTTOM = "crop=1280:120:0:600"      # 底部击杀特效
TOPRIGHT = "crop=320:58:950:18"     # 右上角播报
SIGMA = 2.5
MERGE = 0.40
MIN_GAP = 0.55
CO_WINDOW = 0.80                    # 两信号共现窗口（秒）
FPS = 30.0


def _edges(path: pathlib.Path, crop: str):
    """返回该区域的逐帧灰度均值信号与上升沿时刻。"""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    p = subprocess.run(
        [ff, "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-vf", f"{crop},scale=128:12,format=gray", "-f", "rawvideo", "-"],
        capture_output=True)
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    w, h = 128, 12
    n = len(a) // (w * h)
    if n < 3:
        return np.zeros(0), []
    sig = a[:n * w * h].reshape(n, h, w).mean(axis=(1, 2))
    d = np.diff(sig)
    thr = d.mean() + SIGMA * d.std()
    idx = sorted((int(i) for i in np.where(d > thr)[0]), key=lambda i: -d[i])
    picked: list[int] = []
    for i in idx:
        if all(abs(i - j) / FPS >= MIN_GAP for j in picked):
            picked.append(i)
    picked.sort()
    times = [round(i / FPS, 3) for i in picked]
    merged: list[float] = []
    for t in times:
        if not merged or t - merged[-1] > MERGE:
            merged.append(t)
    return sig, merged


def detect(path: pathlib.Path) -> dict:
    _, tr = _edges(path, TOPRIGHT)
    _, bo = _edges(path, BOTTOM)
    # 共现：右上沿附近 CO_WINDOW 内有底部沿 ⇒ 判为"你的击杀"
    mine = [t for t in tr if any(abs(t - b) <= CO_WINDOW for b in bo)]
    # 只记底部沿（把右上沿保留下来便于排查）
    return {
        "mine": mine,
        "topright_edges": tr,
        "bottom_edges": bo,
        "n_topright": len(tr),
        "n_mine": len(mine),
    }


def main() -> int:
    files = ([pathlib.Path(a) for a in sys.argv[1:]] if len(sys.argv) > 1
             else sorted((ROOT / "原始素材").glob("*.mp4")))
    out: dict[str, dict] = {}
    print("=== 玩家自身击杀帧检测（底部特效 ∩ 右上播报）===")
    print(f"{'素材':10} {'右上沿':>6} {'底部沿':>6} {'你的击杀':>7}  时刻")
    for f in files:
        r = detect(f)
        out[f.stem[:8]] = {"file": f.name, **r}
        print(f"  {f.stem[:8]:10} {r['n_topright']:6} {len(r['bottom_edges']):6} "
              f"{r['n_mine']:7}  " + " ".join(f"{t:.2f}" for t in r["mine"][:14]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tot = sum(r["n_mine"] for r in out.values())
    raw = sum(r["n_topright"] for r in out.values())
    print(f"\n  合计: 右上沿 {raw} 个 → **你自己的击杀 {tot} 个**"
          f"（滤掉了 {raw - tot} 个队友击杀/自己死亡）")
    print(f"  [OK] 已写出 {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
