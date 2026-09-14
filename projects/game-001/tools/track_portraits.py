"""逐帧跟踪**双方头像条**的颜色，用来定位「谁在哪一帧阵亡」。

## 这条素材的真实 HUD（2026-09-14 本轮逐帧目视 + 逐像素实测）

`b61cc53d…mp4` 是**观战/直播 HUD**，不是第一人称原生素材。顶部计分板实测布局：

```
y 2..30   计分板主体：绿条(我方 4 头像) + 比分 + 回合计时 + 红条(敌方 4 头像)
y30..40   头像下方的白色名字条
y40..58   ★ 击杀横幅（洋红→粉的渐变带，带皇冠纹章）—— 实测它**从这一带向上滑出**
y58..96   观战者信息卡：我 [武器] 芮娜 / 小耳朵 / 风说想你 …
```

**推断与实测依据**：
- `magenta` 曲线在 6.533~7.433s 命中一整屏，就是这条横幅向上滑过画面的过程（本轮实测）。
- 头像「阵亡 = 去色变灰」这条路在第 6 轮已被验证**分离明显**（`docs/lessons.md` 第 6 轮 §2 v3，存活 ≈54 / 阵亡 ≈14）。
  本工具把它用在**这条素材的双方头像条**上，并且**逐头像**给曲线，不做全局阈值。

## 与旧判据的关系

`tools/detect_kills.py` 用的是「底部特效带 ∩ 右上播报」（legacy 标定），
本轮实测它在**这条观战素材上基本失效**：底部带量到的是武器皮肤检视与技能图标，
不是击杀横幅。本工具换一条**不依赖底部带**的路。

用法：
    .venv\\Scripts\\python.exe projects/game-001/tools/track_portraits.py b61cc53d
    .venv\\Scripts\\python.exe projects/game-001/tools/track_portraits.py b61cc53d --dump-csv

输出：
    projects/game-001/verification/killscan/<short>_portraits.json  逐帧 8 个头像的饱和度
    stdout：每个头像的「骤降事件」列表（帧号 / 秒 / 落差）
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
OUTDIR = ROOT / "projects" / "game-001" / "verification" / "killscan"
W, H = 1280, 720
FPS = 30.0

# 实测（frame 477 / 681 的顶部 70px 放大图）：两条头像带各 4 个头像
BARS = {
    "blue": (285, 4, 570, 34),
    "red": (760, 4, 1035, 34),
}
N_PER_BAR = 4
# 头像「名字白条」列，用来分隔头像（白条居中于头像下方）
SAT_DEATH_DROP = 8.0        # 一帧内饱和度掉这么多即记一次「骤降」
DEATH_SETTLE = 4            # 连续几帧保持低值才算真阵亡（排除受击抖动）


def _decode(path: pathlib.Path) -> np.ndarray:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    p = subprocess.run([ff, "-v", "error", "-i", str(path), "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.uint8).reshape(-1, H, W, 3)


def _bar_sat(frames: np.ndarray, box) -> np.ndarray:
    x0, y0, x1, y1 = box
    strip = frames[:, y0:y1, x0:x1, :].astype(np.int16)
    sat = strip.max(axis=3) - strip.min(axis=3)
    w = strip.shape[2] // N_PER_BAR
    out = np.zeros((strip.shape[0], N_PER_BAR), dtype=np.float32)
    for i in range(N_PER_BAR):
        out[:, i] = sat[:, :, i * w:(i + 1) * w].mean(axis=(1, 2))
    return out


def _drops(sig: np.ndarray, n_frames: int) -> list[dict]:
    """找「骤降并保持」的事件（帧级）。"""
    events: list[dict] = []
    for i in range(1, n_frames):
        d = float(sig[i - 1] - sig[i])
        if d < SAT_DEATH_DROP:
            continue
        after = sig[i:i + DEATH_SETTLE]
        if after.size >= 2 and float(after.mean()) >= float(sig[i - 1]) - SAT_DEATH_DROP / 2:
            continue                       # 又弹回去了 → 受击/闪光，不是阵亡
        events.append({"frame": i, "s": round(i / FPS, 4),
                       "from": round(float(sig[i - 1]), 2), "to": round(float(sig[i]), 2),
                       "drop": round(d, 2)})
    # 合并 30 帧内的重复上报（同一个头像的连续抖动）
    merged: list[dict] = []
    for e in events:
        if merged and e["frame"] - merged[-1]["frame"] < 30:
            if e["drop"] > merged[-1]["drop"]:
                merged[-1] = e
            continue
        merged.append(e)
    return merged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    ap.add_argument("--dump-csv", action="store_true")
    a = ap.parse_args()

    src = next(SRC.glob(f"{a.short}*.mp4"), None)
    if src is None:
        print(f"[FAIL] 原始素材/ 下找不到 {a.short}*.mp4", file=sys.stderr)
        return 2

    frames = _decode(src)
    n = frames.shape[0]
    print(f"=== 头像饱和度逐帧跟踪 · {src.name} · {n} 帧 ({n / FPS:.3f}s) ===")
    result: dict[str, dict] = {}
    for bar, box in BARS.items():
        sig = _bar_sat(frames, box)
        result[bar] = {"box": box, "sat_mean": [round(float(v), 2) for v in sig.mean(axis=1)]}
        print(f"\n--- {bar} 条 {box} ---  各头像饱和度区间")
        for i in range(N_PER_BAR):
            col = sig[:, i]
            ev = _drops(col, n)
            result[bar][f"slot{i}"] = {
                "mean": round(float(col.mean()), 2),
                "min": round(float(col.min()), 2), "max": round(float(col.max()), 2),
                "drops": ev,
            }
            evs = " ".join(f"{e['s']:.3f}s(-{e['drop']:.0f})" for e in ev) or "—"
            print(f"  头像{i}: 均值 {col.mean():6.2f} 范围 {col.min():6.2f}~{col.max():6.2f}  "
                  f"骤降 {len(ev):2} 次: {evs}")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    dst = OUTDIR / f"{a.short}_portraits.json"
    dst.write_text(json.dumps({"file": src.name, "fps": FPS, "n_frames": n, "bars": result},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[OK] {dst.relative_to(ROOT)}")
    if a.dump_csv:
        csv = OUTDIR / f"{a.short}_portraits.csv"
        with csv.open("w", encoding="utf-8") as fh:
            fh.write("frame,bar,slot,sat\n")
            for bar, box in BARS.items():
                sig = _bar_sat(frames, box)
                for i in range(N_PER_BAR):
                    for f in range(n):
                        fh.write(f"{f},{bar},{i},{sig[f, i]:.2f}\n")
        print(f"[OK] {csv.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
