"""核验 `fps=4` 抽帧的时间偏差：输出帧 k 的内容到底取自源时间轴的哪个 PTS？

方法（全部落盘，不用管道，避免 ffmpeg stderr 死锁；帧只写一次，避免幽灵帧错位）：
  1. 源帧：整段 passthrough 解码为 PNG，并从 showinfo 取每帧 pts_time
  2. 重采样帧：`-vf fps=4` 解码为 PNG；第 k 帧（k 从 0 计）标称时间 = k/4
  3. 对每个重采样帧，在源帧集合里找 MAD 最小的那一个（窗口 ±16 帧）
  4. 报告 offset = 源帧PTS - k/4

判据：若 offset 恒为正且约 +0.10s，说明 fps 滤镜的输出时间戳比其内容真实时刻**滞后**。
"""
from __future__ import annotations

import os
import subprocess
import sys

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
SRC = {
    "a": "原始素材/4b0460c400bbb5320acb6063b4f59358.mp4",
    "b": "原始素材/6b2eea343eee7595c3c0ede10d21d028.mp4",
    "c": "原始素材/dcc871b1791e7796fadac842593f10f7.mp4",
}
W, H = 160, 90
SIZE = W * H * 3
ROOT = "projects/game-001/analysis/raw/_fpschk"


def decode_to_raw(path: str, raw_out: str, vf: str) -> None:
    subprocess.run([FF, "-hide_banner", "-nostats", "-v", "error", "-y", "-i", path,
                    "-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", raw_out],
                   capture_output=True)


def dump_pts(path: str, vf: str, meta_out: str) -> list[float]:
    # 注意：不能加 `-v error` —— showinfo 的输出是 info 级，会被静默吞掉，
    # 导致 PTS 列表为空、后续匹配全部落空。这是我自己踩到的坑。
    with open(meta_out, "wb") as fh:
        subprocess.run([FF, "-hide_banner", "-nostats", "-v", "info", "-y", "-i", path,
                        "-vf", f"{vf},showinfo", "-an", "-f", "null", os.devnull],
                       stdout=subprocess.DEVNULL, stderr=fh)
    pts = []
    for line in open(meta_out, encoding="utf-8", errors="replace"):
        if "pts_time:" in line:
            try:
                pts.append(float(line.split("pts_time:")[1].split()[0]))
            except (IndexError, ValueError):
                pass
    return pts


def split_frames(raw_path: str) -> list[bytes]:
    data = open(raw_path, "rb").read()
    n = len(data) // SIZE
    return [data[i * SIZE:(i + 1) * SIZE] for i in range(n)]


def mad(a: bytes, b: bytes) -> float:
    return sum(abs(a[i] - b[i]) for i in range(len(a))) / len(a) if len(a) == len(b) else 1e9


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    os.makedirs(ROOT, exist_ok=True)
    print(f"{'clip':5} {'匹配帧数':>8} {'min':>9} {'max':>9} {'mean':>9}  判定")
    print("-" * 60)
    summary = {}
    for key, src in SRC.items():
        s_raw = f"{ROOT}/{key}_src.raw"
        r_raw = f"{ROOT}/{key}_fps4.raw"
        for p in (s_raw, r_raw):
            if os.path.exists(p):
                os.remove(p)

        decode_to_raw(src, s_raw, f"scale={W}:{H}")
        decode_to_raw(src, r_raw, f"fps=4,scale={W}:{H}")
        src_pts = dump_pts(src, f"scale={W}:{H}", f"{ROOT}/{key}_src.txt")

        src_fr = split_frames(s_raw)
        rs_fr = split_frames(r_raw)
        n = min(len(src_fr), len(src_pts))
        src_fr = src_fr[:n]
        src_pts = src_pts[:n]

        offsets, ambiguities = [], 0
        for k, rf in enumerate(rs_fr):
            nominal = k / 4.0
            # 在标称位置附近 ±16 源帧内找最相似帧
            lo = max(0, int(nominal * 30) - 16)
            hi = min(n, int(nominal * 30) + 16)
            best_i, best_v = None, 1e9
            for i in range(lo, hi):
                v = mad(rf, src_fr[i])
                if v < best_v:
                    best_v, best_i = v, i
            if best_i is None:
                continue
            # 歧义检查：若最优值不为 0，匹配不可信
            if best_v > 0.5:
                ambiguities += 1
                continue
            offsets.append(src_pts[best_i] - nominal)

        if not offsets:
            print(f"{key:5} 无有效匹配")
            continue
        mn, mx = min(offsets), max(offsets)
        mean = sum(offsets) / len(offsets)
        verdict = ("系统性滞后（恒正）" if mn > 0 else
                   "系统性超前（恒负）" if mx < 0 else "双向抖动")
        print(f"{key:5} {len(offsets):>8} {mn:>+9.4f} {mx:>+9.4f} {mean:>+9.4f}  {verdict}"
              + (f"  (歧义 {ambiguities} 帧已跳过)" if ambiguities else ""))
        summary[key] = {"matched": len(offsets), "min": mn, "max": mx, "mean": mean,
                        "ambiguous_skipped": ambiguities}

    print("-" * 60)
    means = [v["mean"] for v in summary.values()]
    if means:
        print(f"三段 mean 偏差范围: {min(means):+.4f} ~ {max(means):+.4f} s")
        print("→ 若三段同级，则偏差来自 fps 滤镜本身，与 CFR/VFR 无关。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
