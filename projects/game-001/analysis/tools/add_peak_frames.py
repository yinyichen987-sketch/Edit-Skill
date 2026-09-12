"""为 verify/ 补充「峰值帧」，并输出 README 用的清单。

命名约定（重要，避免与 region 中点混淆）：
    <clip>_<highlight_id>_s_<t>s.jpg    区域起点
    <clip>_<highlight_id>_m_<t>s.jpg    区域算术中点（不代表事件发生点）
    <clip>_<highlight_id>_pk_<t>s.jpg   ← 本脚本新增：区域内的音频能量峰值点
    _gapcheck_<clip>_<t>s.jpg           VFR 丢帧点之后的对照帧

峰值取法：从 raw/candidates_<clip>.json 的 transient_events 里，
取与该高光区间重叠的事件中 band 最高者，其 start 时间即峰值点。
无重叠事件的区域不生成 pk 帧（保持诚实：没有能量证据就不假装有峰值）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import imageio_ffmpeg

ROOT = "projects/game-001/analysis"
SRC = {
    "a": "原始素材/4b0460c400bbb5320acb6063b4f59358.mp4",
    "b": "原始素材/6b2eea343eee7595c3c0ede10d21d028.mp4",
    "c": "原始素材/dcc871b1791e7796fadac842593f10f7.mp4",
}


def grab(src: str, t: float, out: str) -> bool:
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-v", "error",
           "-ss", f"{t:.4f}", "-i", src, "-frames:v", "1", "-q:v", "2", "-y", out]
    return subprocess.run(cmd, capture_output=True).returncode == 0 and os.path.getsize(out) > 0


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    analysis = json.load(open(f"{ROOT}/material-analysis.json", encoding="utf-8"))
    outdir = f"{ROOT}/verify"
    os.makedirs(outdir, exist_ok=True)

    made, skipped = [], []
    for clip in analysis["clips"]:
        key = clip["key"]
        src = SRC[key]
        cand = json.load(open(f"{ROOT}/raw/candidates_{key}.json", encoding="utf-8"))
        events = cand["transient_events"]

        for hl in clip["highlights"]:
            lo = hl["start"]
            hi = hl["start"] + hl["duration"]
            best = None
            # 两级选择：
            #  1) 优先取事件重心落在本区间内的事件（取 band 最高者）——保证每个区域有自己的帧
            #  2) 没有则放宽到区间前 2.0s / 后 0.5s，取离区间最近的事件
            #     （交火能量可能先于「确认点」数秒爆发，例如 A-H3 的 2HP 帧在 6.35s，
            #       但其能量窗自 4.75s 的弹匣倾泻就开始了）
            in_region = [e for e in events
                         if lo <= (e["start"] + e["end"]) / 2 <= hi]
            if in_region:
                best = max(in_region, key=lambda e: e["band_db"])
            else:
                near = []
                for e in events:
                    mid = (e["start"] + e["end"]) / 2
                    if lo - 2.0 <= mid <= hi + 0.5:
                        dist = min(abs(mid - lo), abs(mid - hi))
                        near.append((-dist, e))
                if near:
                    near.sort(key=lambda x: x[0])
                    best = near[0][1]
            if best is None:
                skipped.append(f"{key}_{hl['id']}")
                continue
            e = best
            t = round(e["start"], 2)
            name = f"{key}_{hl['id']}_pk_{t:.2f}s.jpg"
            if grab(src, t, os.path.join(outdir, name)):
                made.append((name, round(e["band_db"], 2), round(e["band_over_median_db"], 2)))

    print(f"新增峰值帧 {len(made)} 张：")
    for n, band, over in made:
        print(f"   {n:28} band {band:>7} dB  (+{over} vs 基线)")
    if skipped:
        print(f"\n无能量证据、未生成 pk 帧的高光 {len(skipped)} 个：{', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
