"""用 showinfo 逐帧 dump PTS，实测每段素材是 CFR 还是 VFR。

只读取 PTS 事实，不改动任何素材。
输出：帧数、各相邻 PTS 差值的分布、异常间隔（>1.5 帧）、首帧 PTS。
"""
from __future__ import annotations

import collections
import json
import os
import re
import subprocess
import sys

import imageio_ffmpeg

SHOWINFO_RE = re.compile(r"n:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:(-?[\d.]+)")


def dump_pts(path: str) -> list[tuple[int, float]]:
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-nostats",
        "-i", path, "-vf", "showinfo", "-an", "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)  # showinfo 写 stderr
    text = proc.stderr.decode("utf-8", "replace")
    out = []
    for m in SHOWINFO_RE.finditer(text):
        out.append((int(m.group(1)), float(m.group(3))))
    return out


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    avail = sys.argv[1:]
    if not avail:
        print("usage: fps_probe.py <video> [video...]")
        return 2

    report = []
    for path in avail:
        pts = dump_pts(path)
        if not pts:
            print(f"[FAIL] {path}: 没有解析到 showinfo 帧")
            continue
        pts.sort()
        times = [t for _, t in pts]
        deltas = [round(times[i + 1] - times[i], 6) for i in range(len(times) - 1)]

        counter = collections.Counter(deltas)
        base = 1.0 / 30.0
        gaps = [(pts[i][0], round(times[i], 6), round(deltas[i], 6))
                for i in range(len(deltas)) if deltas[i] > base * 1.5]

        nominal_n = len(times) * base
        actual_span = times[-1] - times[0]

        rec = {
            "path": path,
            "frame_count_parsed": len(times),
            "first_pts_time_s": round(times[0], 6),
            "last_pts_time_s": round(times[-1], 6),
            "pts_span_s": round(actual_span, 6),
            "nominal_span_if_30fps_s": round(nominal_n, 6),
            "span_deficit_s": round(nominal_n - actual_span, 6),
            "distinct_delta_values": dict(sorted(counter.items())),
            "gap_count_gt_1.5frames": len(gaps),
            "gaps": gaps[:20],
            "verdict": "CFR" if len(counter) <= 2 else f"VFR ({len(counter)} 种间隔)",
        }
        report.append(rec)

        print("=" * 74)
        print(path)
        print(f"  帧数(解析)      {rec['frame_count_parsed']}")
        print(f"  首帧 pts_time   {rec['first_pts_time_s']}")
        print(f"  末帧 pts_time   {rec['last_pts_time_s']}")
        print(f"  PTS 跨度        {rec['pts_span_s']}s")
        print(f"  若恒定30fps的名义跨度 {rec['nominal_span_if_30fps_s']}s")
        print(f"  跨度缺口        {rec['span_deficit_s']}s  (≈{rec['span_deficit_s']*30:.2f} 帧)")
        print(f"  间隔取值种类    {list(rec['distinct_delta_values'].keys())}")
        print(f"  >1.5帧的间隔数  {rec['gap_count_gt_1.5frames']}")
        for n, t, d in rec["gaps"][:8]:
            print(f"      n={n:5d}  t={t:9.6f}s  Δ={d:.6f}s (≈{d*30:.2f} 帧)")
        print(f"  判定            {rec['verdict']}")

    # 输出路径基于本脚本位置推导，避免依赖 CWD（否则只在仓库根运行时可用）
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "raw")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "fps_probe.json")

    # 合并式写入：按**规范化绝对路径**去重，保留其它条目。
    # 用绝对路径而非原始字符串，否则「相对路径跑一次、绝对路径再跑一次」会留下重复条目。
    existing: list[dict] = []
    if os.path.exists(out_path):
        try:
            loaded = json.load(open(out_path, encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
        except (json.JSONDecodeError, OSError):
            existing = []
    seen = {os.path.abspath(r.get("path") or "") for r in report}
    merged = [r for r in existing
              if os.path.abspath(r.get("path") or "") not in seen] + report
    merged.sort(key=lambda r: os.path.abspath(r.get("path") or ""))

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
    print("=" * 74)
    print(f"[OK] {out_path}  （本次 {len(report)} 条，累计 {len(merged)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
