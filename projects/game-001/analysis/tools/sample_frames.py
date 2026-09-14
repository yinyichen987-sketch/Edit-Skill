"""按精确时间点抽取参考帧，供人工/下游复核。

为什么要这个脚本：
    素材 b、c 是 VFR（各有 1 处真实丢帧间隔），因此「第 N 帧 ÷ 30」不成立。
    所有结论必须能以「时间(秒)」复现。本脚本用 -ss 精确到帧地取帧，
    文件名直接编码时间，任何人可据此复查同一点。

用法：
    python sample_frames.py            # 抽取 material-analysis.json 里全部高光时间码
"""
from __future__ import annotations

import json
import os
import re
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
    """取 t 时刻（t 之后的第一个帧）的单帧，写为 JPEG。"""
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-v", "error",
        "-ss", f"{t:.4f}", "-i", src, "-frames:v", "1", "-q:v", "2", "-y", out,
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        print(f"   [FAIL] {out}: {proc.stderr.decode('utf-8','replace')[:200]}")
        return False
    return os.path.exists(out) and os.path.getsize(out) > 0


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    with open(os.path.join(ROOT, "material-analysis.json"), encoding="utf-8") as fh:
        data = json.load(fh)

    outdir = os.path.join(ROOT, "verify")
    os.makedirs(outdir, exist_ok=True)

    made = 0
    for clip in data["clips"]:
        key = clip["key"]
        src = SRC[key]
        for hl in clip["highlights"]:
            hid = hl["id"]
            # 取高光起点与其内部峰值参考点各 1 帧
            points = [("s", hl["start"])]
            mid = hl["start"] + hl["duration"] / 2
            points.append(("m", round(mid, 4)))
            for tag, t in points:
                name = f"{key}_{hid}_{tag}_{t:.2f}s.jpg".replace(" ", "")
                path = os.path.join(outdir, name)
                if grab(src, t, path):
                    made += 1

    print(f"[OK] 抽取 {made} 帧 → {outdir}")
    print("文件命名规则：<clip>_<highlight_id>_<s=起点/m=中点>_<时间秒>.jpg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
