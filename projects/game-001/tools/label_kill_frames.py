"""出「击杀帧候选」的证据图 —— 供人（或 agent 的读图能力）**逐帧目视判定**。

每个候选时刻出一张 PNG，纵向四条，同一 x 轴对齐、每格 = 1 帧：

| 条 | 内容 | 作用 |
|---|---|---|
| ① | 整帧（缩到 640 宽） | 看发生了什么（对枪/结算/死亡） |
| ② | **中部横幅带** `y495..640` 放大 | 看那条洋红描边的「击杀横幅」（`kill-extraction.md` 实测 y522~613） |
| ③ | **右上 killfeed** `x790..1275, y0..110` 放大 2x | **判定谁是击杀者/被杀者**，最权威 |
| ④ | 顶部敌人头像条 `x520..1270, y0..56` 放大 2x | 阵亡头像去色变灰 |

**为什么必须看图**：`kill-extraction.md` §2 已实证 —— 信号给的时刻可能是误报
（战术面板弹出、弹匣变化都会点亮底带）。本工具只产证据，判定写进 `kills_groundtruth.json`。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\label_kill_frames.py b61cc53d 6.2 6.8 9.567
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\label_kill_frames.py b61cc53d --auto --pad 6

输出：projects/game-001/verification/killlabels/<short>_c<t>.png
"""
from __future__ import annotations

import argparse
import json
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
OUT = ROOT / "projects" / "game-001" / "verification" / "killlabels"
CAND = ROOT / "projects" / "game-001" / "analysis2" / "kills_mine.json"

W, H = 1280, 720
FPS = 30.0
PAD = 6                      # 候选前后各看几帧
BANNER_BOX = (360, 495, 920, 640)     # x0,y0,x1,y1（横幅带，留余量）
FEED_BOX = (790, 0, 1275, 110)        # 右上 killfeed
PORTRAIT_BOX = (520, 0, 1270, 56)     # 顶部敌人头像条
ROW_H = 216                  # 横幅带放大后的目标高度（原带高 145 → 整数倍缩放）


def _decode(path: pathlib.Path) -> np.ndarray:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    p = subprocess.run(
        [ff, "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.uint8).reshape(-1, H, W, 3)


def _scale_to_h(img: np.ndarray, h: int) -> np.ndarray:
    """最近邻缩放到指定高度（保持宽高比），不做插值以免糊掉小字。"""
    k = max(1, round(h / img.shape[0]))
    return np.repeat(np.repeat(img, k, axis=0), k, axis=1)


def _scale_to_w(img: np.ndarray, w: int) -> np.ndarray:
    k = max(1, round(w / img.shape[1]))
    return np.repeat(np.repeat(img, k, axis=0), k, axis=1)


def _label_strip(width: int, text: str, height: int = 22) -> np.ndarray:
    """整条色带 + 左侧高对比色块。**不画字**：贴图不做字体渲染，文字写进文件名与 JSON。"""
    strip = np.full((height, width, 3), 25, np.uint8)
    strip[:, :60] = (0, 200, 255)
    return strip


def _norm_row(img: np.ndarray, width: int) -> np.ndarray:
    """把**整条**（已横向拼好的）行重采样到精确 width 宽。

    ⚠️ 必须对**拼好的整行**归一化，不能对每格单独归一化：
    每格变成 width 宽再横向拼接，总宽就成了 width × 格数（实测 13 格 → 17550px），
    四个条的总宽互不相同，`np.concatenate(axis=0)` 直接报维度不匹配。
    """
    w = img.shape[1]
    if w != width:
        idx = (np.arange(width) * w // width) % w
        img = img[:, idx]
    return img


def _panel(frames: np.ndarray, center: int) -> np.ndarray:
    """拼一张证据图：素材首帧 + 整帧（缩小）+ 三条放大带。

    每一行的宽度先各自拼好，最后统一重采样到同一 width，再纵向拼接。
    """
    lo = max(0, center - PAD)
    hi = min(frames.shape[0], center + PAD + 1)
    sel = frames[lo:hi]
    width = 675 * 2
    gap = lambda h=6: np.full((h, width, 3), 200, np.uint8)   # noqa: E731

    def band(box, h_target, stride=3):
        x0, y0, x1, y1 = box
        rows = [_scale_to_h(f[y0:y1, x0:x1], h_target)[::stride, ::stride] for f in sel]
        return _norm_row(np.concatenate(rows, axis=1), width)

    full = _norm_row(np.concatenate([f[::5, ::5] for f in sel], axis=1), width)
    ban = band(BANNER_BOX, 145, stride=2)
    feed = band(FEED_BOX, 110, stride=3)
    port = band(PORTRAIT_BOX, 56, stride=3)
    first = _norm_row(_scale_to_w(frames[0], width), width)
    return np.concatenate([first, gap(10), full, gap(), ban,
                           gap(), feed, gap(), port], axis=0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    ap.add_argument("times", nargs="*", type=float)
    ap.add_argument("--auto", action="store_true",
                    help="不传 times 时从 kills_mine.json 取该素材的候选")
    a = ap.parse_args()

    src = next(SRC.glob(f"{a.short}*.mp4"), None)
    if src is None:
        print(f"[FAIL] 原始素材/ 下找不到 {a.short}*.mp4", file=sys.stderr)
        return 2
    times = a.times
    if not times and a.auto:
        data = json.loads(CAND.read_text(encoding="utf-8"))
        times = list(data[a.short]["mine"])
    if not times:
        print("[FAIL] 没给时刻；用 --auto 取候选或显式传时刻", file=sys.stderr)
        return 2

    frames = _decode(src)
    n = frames.shape[0]
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"=== 击杀候选证据图 · {src.name}（{n} 帧 / {n / FPS:.3f}s）===")
    for t in sorted(times):
        c = int(round(t * FPS))
        if not 0 <= c < n:
            print(f"  [SKIP] {t} → 帧 {c} 越界")
            continue
        sheet = _panel(frames, c)
        dst = OUT / f"{a.short}_c{t:.3f}.png"
        iio.imwrite(dst, sheet)
        print(f"  [OK] {dst.name}  中心帧 {c}（{c / FPS:.4f}s），"
              f"窗口 {max(0, c - PAD) / FPS:.3f}~{min(n, c + PAD + 1) / FPS:.3f}s，"
              f"{sheet.shape[1]}x{sheet.shape[0]}")
    print(f"\n每张图 4 条（自上而下）：整帧 / 横幅带 y495-640 / 右上 killfeed / 顶部头像条")
    print(f"每格 = 1 帧 @30fps，中心格外扩 {PAD} 帧；输出目录 {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
