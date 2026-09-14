"""逐帧扫「击杀帧」信号 —— 给人工/读图核对提供**帧级**证据。

## 为什么需要这个工具

`tools/detect_kills.py` 用的是「底部带 ∩ 右上带」的**上升沿**，它只能给出
**30fps 量化后的候选时刻**，而且底部那条（legacy `crop=...:600`）已被实测证明截错了位置
（见 `.dsh/skills/jianying-edit/references/kill-extraction.md`）。
本工具换一条不依赖切点、也不依赖旧标定的路子：

| 信号 | 区域（1280x720） | 依据 |
|---|---|---|
| `magenta` 洋红（横幅描边色）占比 | 中部横幅带 `x380..900, y500..625` | 横幅是洋红/紫色描边（`zoom_killfeed.py` 已用同色系，L1 实测） |
| 5 个敌人头像的**饱和度** | 顶部头像条 `x~528..1254, y~2..48` | 阵亡头像会**去色变灰**（`count_enemy_hud.py` 第 6 轮 v3，分离明显但受击会抖） |

两条都只是**代理信号**，所以本工具**只输出证据，不下判定**。
判定由 `label_kill_frames.py` 读图后落进 `kills_groundtruth.json`。

## 用法

    .venv\\Scripts\\python.exe projects\\game-001\\tools\\scan_killframes.py b61cc53d
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\scan_killframes.py b61cc53d --times 6.2 6.8 --out xxx.json

输出（默认）：
    projects/game-001/verification/killscan/<short>_frames.json   逐帧信号
    projects/game-001/verification/killscan/<short>_summary.json 每个候选的峰值与首帧
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
CAND = ROOT / "projects" / "game-001" / "analysis2" / "kills_mine.json"

W, H = 1280, 720
FPS = 30.0

# ── 区域标定：**2026-09-14 本轮实测重标**，不是抄来的 ──────────────────────
# 旧标定（kill-extraction.md）的横幅带 y500..625 在这条素材上量到的是**武器皮肤的
# 检视动画**（整屏洋红），而真正的击杀横幅是**从下往上滑过画面中部**的一条，
# 起始位置比原来记的更低。所以这里不再写死一条窄带，而是：
#   ① 直接对下方大半屏做**色相筛选**（只认「洋红/红紫」这类颜色）；
#   ② 把命中的 y 中位数当作横幅所在高度，用全片的 (帧号, y) 轨迹反推它的运动。
BANNER = (0, 300, W, 700)          # 下 300..700（含横幅全程）
# 顶部计分板右侧 4 个敌人头像（实测 x900..1010, y20..70 的饱和度与击杀同步跳变）
PORTRAITS = (900, 20, 1010, 70)
N_PORTRAITS = 4

MAGENTA_MARGIN = 30               # min(R,B) - G 的门限
MAGENTA_MIN_RB = 70               # min(R,B) 的门限（排除暗部噪声）
RED_MIN_R = 120                   # 纯红判据（R 很高、G 很低、B 也不高）
RED_MAX_GB = 90


def _decode(path: pathlib.Path) -> np.ndarray:
    """整条素材解码成 (n, H, W, 3) uint8。1280x720 的几十秒素材约 1~3 GB，可接受。"""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    p = subprocess.run(
        [ff, "-v", "error", "-i", str(path), "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True)
    buf = np.frombuffer(p.stdout, dtype=np.uint8)
    if buf.size % (H * W * 3):
        raise SystemExit(f"[FAIL] 解码字节数 {buf.size} 不是帧大小的整数倍")
    return buf.reshape(-1, H, W, 3)


def _magenta(frames: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回 (洋红占比, 纯红占比, 命中像素的 y 中位数)。

    两个判据分开报，是因为它们对应**不同的 UI**：
      · 洋红 = 击杀横幅（magenta/pink 渐变 + 描边）
      · 纯红 = 武器皮肤检视、受击红屏等干扰源
    只报一个数会把两者混成一条曲线（本轮就是这么先踩了一脚的）。
    """
    x0, y0, x1, y1 = BANNER
    band = frames[:, y0:y1, x0:x1, :].astype(np.int16)
    r, g, b = band[..., 0], band[..., 1], band[..., 2]
    mb = np.minimum(r, b)
    mag = (mb - g > MAGENTA_MARGIN) & (mb > MAGENTA_MIN_RB)
    red = (r > RED_MIN_R) & (g < RED_MAX_GB) & (b < RED_MAX_GB)
    frac_m = mag.mean(axis=(1, 2))
    frac_r = red.mean(axis=(1, 2))
    ys = np.full(len(frames), np.nan)
    for i in range(len(frames)):
        rows = np.where(mag[i].any(axis=1))[0]
        if rows.size:
            ys[i] = y0 + float(np.median(rows))
    return frac_m, frac_r, ys


def _portrait_sat(frames: np.ndarray) -> np.ndarray:
    x0, y0, x1, y1 = PORTRAITS
    strip = frames[:, y0:y1, x0:x1, :].astype(np.int16)
    sat = strip.max(axis=3) - strip.min(axis=3)          # 饱和度代理
    w = strip.shape[2] // N_PORTRAITS
    out = np.zeros((strip.shape[0], N_PORTRAITS), dtype=np.float32)
    for i in range(N_PORTRAITS):
        out[:, i] = sat[:, :, i * w:(i + 1) * w].mean(axis=(1, 2))
    return out


def _merge_region(idx: list[int], max_gap: int = 3) -> list[list[int]]:
    """把相邻帧号合成区间（横幅会持续十几帧）。"""
    runs: list[list[int]] = []
    for i in idx:
        if runs and i - runs[-1][1] <= max_gap:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    return runs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short", help="素材短名，如 b61cc53d")
    ap.add_argument("--times", type=float, nargs="*", default=None,
                    help="只看这些候选时刻（默认取 kills_mine.json 里该素材的候选）")
    ap.add_argument("--window", type=float, default=1.2, help="每个候选的分析半径（秒）")
    ap.add_argument("--out", default=None, help="逐帧 JSON 输出路径")
    a = ap.parse_args()

    src = next(SRC.glob(f"{a.short}*.mp4"), None)
    if src is None:
        print(f"[FAIL] 原始素材/ 下找不到 {a.short}*.mp4", file=sys.stderr)
        return 2

    if a.times:
        cands = sorted(a.times)
    else:
        data = json.loads(CAND.read_text(encoding="utf-8"))
        if a.short not in data:
            print(f"[FAIL] {CAND.name} 里没有 {a.short}", file=sys.stderr)
            return 2
        cands = list(data[a.short]["mine"])

    frames = _decode(src)
    n = frames.shape[0]
    print(f"=== 逐帧击杀信号 · {src.name} · {n} 帧 @ {FPS:g}fps "
          f"({n / FPS:.3f}s) ===")
    mag, red, ymid = _magenta(frames)
    sat = _portrait_sat(frames)

    defs = {
        "magenta": (mag, "击杀横幅（洋红）", max(0.003, float(mag.mean() + 2.0 * mag.std()))),
        "red": (red, "纯红干扰源（皮肤检视/受击）", max(0.003, float(red.mean() + 2.0 * red.std()))),
    }
    runs_by_kind: dict[str, list[list[int]]] = {}
    print(f"\n{'信号':>8} {'均值':>9} {'标准差':>9} {'门限':>9} {'区间数':>6}")
    for kind, (sig, label, thr) in defs.items():
        runs = _merge_region([i for i in range(n) if sig[i] > thr], max_gap=3)
        runs_by_kind[kind] = runs
        print(f"{label[:8]:>8} {sig.mean():9.5f} {sig.std():9.5f} {thr:9.5f} {len(runs):6}")

    print(f"\n=== 洋红横幅区间（全片，共 {len(runs_by_kind['magenta'])} 段）===")
    print(f"{'#':>3} {'起(s)':>8} {'止(s)':>8} {'帧数':>5} {'y中位轨迹(首→末)':>22} {'y斜率':>9}")
    banner_runs: list[dict] = []
    for k, r in enumerate(runs_by_kind["magenta"], 1):
        ys = ymid[r[0]:r[1] + 1]
        ok = ~np.isnan(ys)
        y0 = float(ys[ok][0]) if ok.any() else float("nan")
        y1 = float(ys[ok][-1]) if ok.any() else float("nan")
        slope = ((y1 - y0) / max(1, r[1] - r[0])) if ok.any() else float("nan")
        banner_runs.append({
            "frames": r, "start_s": round(r[0] / FPS, 4), "end_s": round(r[1] / FPS, 4),
            "n": r[1] - r[0] + 1, "y_first": y0, "y_last": y1, "y_slope_px_per_frame": slope,
        })
        print(f"{k:3} {r[0] / FPS:8.3f} {r[1] / FPS:8.3f} {r[1] - r[0] + 1:5} "
              f"{y0:10.1f} → {y1:7.1f} {slope:9.2f}")

    detail: dict[str, dict] = {}
    summary: dict[str, dict] = {}
    for t in cands:
        c = int(round(t * FPS))
        lo, hi = max(0, c - int(round(a.window * FPS))), min(n, c + int(round(a.window * FPS)) + 1)
        wmag = mag[lo:hi]
        idx = [i for i in range(lo, hi) if mag[i] > defs["magenta"][2]]
        rl = _merge_region(idx, max_gap=3)
        # 最近的一段洋红区间（可能上界越出窗口，所以用全片轨迹就近匹配）
        nearest = None
        if rl:
            nearest = min(rl, key=lambda r: abs(0.5 * (r[0] + r[1]) - c))
        peak = lo + int(np.argmax(wmag)) if wmag.size else c
        base = sat[max(0, c - 6):c].mean(axis=0) if c >= 1 else sat[c]
        after = sat[c:min(n, c + 30)].mean(axis=0)
        drop = base - after
        detail[f"{t:.3f}"] = {
            "candidate_s": t,
            "candidate_frame": c,
            "magenta_peak_s": round(peak / FPS, 4),
            "magenta_peak_frame": int(peak),
            "magenta_nearest_run": None if nearest is None else {
                "frames": nearest,
                "start_s": round(nearest[0] / FPS, 4),
                "end_s": round(nearest[1] / FPS, 4),
                "n": nearest[1] - nearest[0] + 1,
            },
            "red_at_candidate": round(float(red[c]), 5),
            "y_median_at_candidate": None if np.isnan(ymid[c]) else round(float(ymid[c]), 1),
            "portrait_sat_before": [round(float(v), 2) for v in base],
            "portrait_sat_after": [round(float(v), 2) for v in after],
            "portrait_sat_drop": [round(float(v), 2) for v in drop],
        }
        summary[f"{t:.3f}"] = {
            "nearest_run_start_s": None if nearest is None else round(nearest[0] / FPS, 4),
            "nearest_run_frames": 0 if nearest is None else nearest[1] - nearest[0] + 1,
            "magenta_peak_s": round(peak / FPS, 4),
            "magenta_at_candidate": round(float(mag[c]), 5),
            "red_at_candidate": round(float(red[c]), 5),
            "sat_drop_max": round(float(drop.max()), 2) if drop.size else 0.0,
        }

    OUTDIR.mkdir(parents=True, exist_ok=True)
    dst = pathlib.Path(a.out) if a.out else OUTDIR / f"{a.short}_frames.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps({
        "file": src.name, "fps": FPS, "n_frames": n,
        "banner_box": BANNER, "portraits_box": PORTRAITS,
        "thresholds": {k: v[2] for k, v in defs.items()},
        "banner_runs": banner_runs,
        "red_runs": [[r[0], r[1]] for r in runs_by_kind["red"]],
        "candidates": detail,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUTDIR / f"{a.short}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{'候选':>8} {'最近洋红段起':>12} {'段帧数':>6} {'洋红峰':>8} "
          f"{'候选处洋红':>10} {'候选处纯红':>10} {'头像掉幅':>8}")
    for t in cands:
        s = summary[f"{t:.3f}"]
        fr = "—" if s["nearest_run_start_s"] is None else f"{s['nearest_run_start_s']:.3f}"
        print(f"{t:8.3f} {fr:>12} {s['nearest_run_frames']:6} {s['magenta_peak_s']:8.3f} "
              f"{s['magenta_at_candidate']:10.5f} {s['red_at_candidate']:10.5f} "
              f"{s['sat_drop_max']:8.2f}")
    print(f"\n[OK] {dst.relative_to(ROOT)}")
    print(f"[OK] {(OUTDIR / f'{a.short}_summary.json').relative_to(ROOT)}")
    print("     下一步：label_kill_frames.py 出证据图 → 读图判定 → 写 groundtruth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
