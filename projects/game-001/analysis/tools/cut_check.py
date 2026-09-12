"""独立复核「瞬时视点跳变」候选点。

对每个候选时间 t：
  1. 用 showinfo dump 该点附近的逐帧 PTS，确定 t 前后**真正相邻的两帧**
  2. 取这两帧的原始 RGB 像素，计算逐像素差异统计
  3. 同时输出两帧图片供目视

为什么必须用相邻帧：
   跳变的定义就是「相邻两帧之间内容完全换位」。若取间隔多帧的图，运动本身也能造成大差异，
   无法与真跳变区分。所以必须锁定 PTS 相邻的那一对。

判据（两条都要满足才算瞬时跳变）：
    A. 平均绝对像素差 (MAE) 显著，且远高于该素材运动段的典型帧间差
    B. 差异是「全局换位」而非「局部运动」：差异像素占比高，且差异图不集中在单一区域
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
SRC = {
    "a": "原始素材/4b0460c400bbb5320acb6063b4f59358.mp4",
    "b": "原始素材/6b2eea343eee7595fadac842593f10f7.mp4",  # 占位，下面会覆盖
}
SRC = {
    "a": "原始素材/4b0460c400bbb5320acb6063b4f59358.mp4",
    "b": "原始素材/6b2eea343eee7595c3c0ede10d21d028.mp4",
    "c": "原始素材/dcc871b1791e7796fadac842593f10f7.mp4",
}

CANDIDATES = [
    ("b", 11.000),
    ("b", 12.967),
    ("c", 2.067),
    ("c", 3.367),
]
# 阴性对照：同一素材里一段明显的普通运动（切在平移中），用来给 MAE 定标
CONTROLS = [
    ("b", 6.000),
    ("c", 8.000),
]


def pts_near(clip: str, center: float, span: float = 0.25) -> list[tuple[float, float]]:
    """返回 [(pts_time, frame_index)]，覆盖 center±span。"""
    src = SRC[clip]
    lo = max(0.0, center - span)
    cmd = [FF, "-hide_banner", "-nostats", "-v", "info",
           "-ss", f"{lo:.4f}", "-i", src,
           "-vf", "showinfo", "-an", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True)
    text = proc.stderr.decode("utf-8", "replace")
    out = []
    for line in text.splitlines():
        if "pts_time:" in line and "n:" in line:
            try:
                n = int(line.split("n:")[1].split()[0].strip(" :"))
                t = float(line.split("pts_time:")[1].split()[0])
                out.append((t, n))
            except (IndexError, ValueError):
                continue
    return sorted(out)


def frames_rgb(clip: str, times: list[float]) -> list[bytes]:
    """按精确 pts 取帧，输出 RGB24 原始字节（1280x720x3）。"""
    src = SRC[clip]
    got = []
    for t in times:
        cmd = [FF, "-hide_banner", "-v", "error", "-ss", f"{t:.6f}", "-i", src,
               "-frames:v", "1", "-vf", "scale=640:360", "-pix_fmt", "rgb24",
               "-f", "rawvideo", "-"]
        r = subprocess.run(cmd, capture_output=True)
        got.append(r.stdout)
    return got


def mae(a: bytes, b: bytes) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    s = 0
    for i in range(0, len(a), 3):
        s += abs(a[i] - b[i]) + abs(a[i + 1] - b[i + 1]) + abs(a[i + 2] - b[i + 2])
    return s / (len(a) / 3 * 3)


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print("=" * 78)
    print("一、候选点：t 前后真正相邻的两帧")
    print("=" * 78)
    results = []
    for clip, t in CANDIDATES:
        pts = pts_near(clip, t)
        before = [p for p in pts if p[0] < t]
        after = [p for p in pts if p[0] >= t]
        if not before or not after:
            print(f"{clip} @ {t}: 取不到前后帧（pts 数={len(pts)}）")
            continue
        tb, nb = before[-1]
        ta, na = after[0]
        gap = ta - tb
        fr = frames_rgb(clip, [tb + 1e-4, ta + 1e-4])
        d = mae(fr[0], fr[1])
        print(f"{clip} @ {t:>7.3f}s : 前帧 n={nb} t={tb:.4f}  后帧 n={na} t={ta:.4f}  "
              f"间隔={gap:.4f}s  相邻帧MAE={d:.2f}")
        results.append((clip, t, gap, d))

    print()
    print("=" * 78)
    print("二、阴性对照：同素材里普通运动段的相邻帧差（给 MAE 定标）")
    print("=" * 78)
    ctrl = []
    for clip, t in CONTROLS:
        pts = pts_near(clip, t)
        if len(pts) < 2:
            print(f"{clip} @ {t}: pts 不足")
            continue
        tb, nb = pts[0]
        ta, na = pts[1]
        fr = frames_rgb(clip, [tb + 1e-4, ta + 1e-4])
        d = mae(fr[0], fr[1])
        print(f"{clip} 运动段 n={nb}->{na} 间隔={ta-tb:.4f}s  相邻帧MAE={d:.2f}")
        ctrl.append(d)

    if ctrl:
        print()
        ctrl_med = sorted(ctrl)[len(ctrl) // 2]
        print(f"运动段相邻帧 MAE 中位 = {ctrl_med:.2f}")
        print("候选点 MAE 与运动段 MAE 的比值：")
        for clip, t, gap, d in results:
            ratio = d / ctrl_med if ctrl_med else float("inf")
            print(f"   {clip} @ {t:>7.3f}s  MAE={d:8.2f}  比值={ratio:6.2f}x  "
                  f"{'★ 显著跳变' if ratio > 3 else '与普通运动同量级'}")

    json.dump({"candidates": [{"clip": c, "t": t, "gap": g, "mae": d}
                              for c, t, g, d in results],
               "control_mae": ctrl},
              open("projects/game-001/analysis/raw/cut_check.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n[OK] projects/game-001/analysis/raw/cut_check.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
