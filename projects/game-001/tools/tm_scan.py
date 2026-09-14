"""模板匹配找「播报卡出现」的时刻（不依赖颜色阈值，也不依赖固定坐标）。

为什么不用颜色/固定带子：
- `b61cc53d` @6.567 有一整屏洋红技能特效 ⇒ 洋红占比判据会把技能判成击杀；
- `kill-extraction.md` 里标定的「底部横幅带 y520~620」**与准星重合**（准星就在画面正中
  y≈520~613），本工具的作者目视确认：那条带子里的洋红其实是**准星命中标记**。
- 观战 HUD 的播报卡在**不同片段里 x 位置不同**（4b0460c4 的武器剪影在 x≈1030~1160，
  b61cc53d 在 x≈780~900），固定坐标会漏。

做法：**从一条素材里抠出一张"卡上武器剪影"小图当模板**，在另一条素材上做
归一化互相关（NCC），逐帧取最大响应。卡出现/消失 ⇒ 响应曲线出现台阶 ⇒ 取上升沿。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\tm_scan.py <short> --tmpl-x 1030 --tmpl-y 96 --tmpl-w 130 --tmpl-h 40 --t0 0 --t1 30
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
OUT = ROOT / "projects" / "game-001" / "verification" / "tm_scan"
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


def ncc_map_max(img: np.ndarray, tmpl: np.ndarray, search: tuple[int, int, int, int]) -> float:
    """在 search=(x0,y0,x1,y1) 内滑动模板，返回最大归一化互相关。"""
    x0, y0, x1, y1 = search
    th, tw = tmpl.shape[:2]
    t = tmpl - tmpl.mean()
    tn = np.sqrt((t * t).sum())
    if tn == 0:
        return 0.0
    best = -1.0
    step = 2
    for yy in range(y0, y1 - th + 1, step):
        for xx in range(x0, x1 - tw + 1, step):
            win = img[yy:yy + th, xx:xx + tw]
            w = win - win.mean()
            wn = np.sqrt((w * w).sum())
            if wn == 0:
                continue
            v = float((w * t).sum() / (wn * tn))
            if v > best:
                best = v
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    ap.add_argument("--tmpl-from", default="4b0460c4", help="抠模板的素材 short")
    ap.add_argument("--tmpl-t", type=float, default=10.8)
    ap.add_argument("--tmpl", default="1030:96:130:40", help="X:Y:W:H 模板框（1280x720）")
    ap.add_argument("--search", default="700:60:1280:200", help="X0:Y0:X1:Y1 搜索范围")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=None)
    ap.add_argument("--thr", type=float, default=0.55)
    a = ap.parse_args()

    tx, ty, tw, th = (int(v) for v in a.tmpl.split(":"))
    s = tuple(int(v) for v in a.search.split(":"))
    tf = decode(a.tmpl_from, a.tmpl_t, a.tmpl_t + 0.04)[0]
    tmpl = tf[ty:ty + th, tx:tx + tw]
    print(f"模板 {a.tmpl_from}@{a.tmpl_t}s x{tx}y{ty} {tw}x{th} 形状={tmpl.shape}")

    t1 = a.t1 if a.t1 is not None else 29.0
    fr = decode(a.short, a.t0, t1)
    n = fr.shape[0]
    ts = a.t0 + np.arange(n) / 30.0
    resp = np.array([ncc_map_max(fr[i], tmpl, s) for i in range(n)])
    print(f"[{a.short}] n={n} resp med={np.median(resp):.3f} p90={np.percentile(resp, 90):.3f} max={resp.max():.3f}")
    segs = []
    i = 0
    hot = resp >= a.thr
    while i < n:
        if hot[i]:
            j = i
            while j + 1 < n and hot[j + 1]:
                j += 1
            segs.append((i, j))
            i = j + 1
        else:
            i += 1
    print(f"  响应≥{a.thr} 的连续段: {len(segs)}")
    for i, j in segs:
        print(f"   {ts[i]:7.3f} ~ {ts[j]:7.3f}  {(j - i + 1) * 33.3:5.0f} ms  peak={resp[i:j+1].max():.3f}")
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{a.short}_{a.t0:.2f}-{t1:.2f}_tmpl{tx}_{ty}.json"
    dst.write_text(json.dumps({"t": ts.tolist(), "resp": resp.tolist(),
                               "segments": [[float(ts[i]), float(ts[j])] for i, j in segs]}),
                   encoding="utf-8")
    print(f"[OK] {dst.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
