"""按帧号精确取「跳变前 / 跳变后」两帧，供目视确证。

用 select 按帧号 n 取帧（比按时间 seek 更适合跨跳变点，避免 ±1 帧歧义），
输出 PNG（避免 YUV->JPEG 的 full-range 兼容问题）。
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
# (clip, 跳变后的帧号) —— 取 n-1 与 n 两帧
JUMPS = [("b", 331), ("b", 390), ("c", 63), ("c", 102)]
OUT = "projects/game-001/analysis/cutcheck"


def two_frames(clip: str, n: int) -> bool:
    src = SRC[clip]
    a, b = n - 1, n
    expr = f"select='eq(n\\,{a})+eq(n\\,{b})'"
    dst = f"{OUT}/{clip}_jump{n:04d}_%d.png"
    cmd = [FF, "-hide_banner", "-v", "error", "-y", "-i", src,
           "-vf", expr, "-vsync", "0", "-frames:v", "2", dst]
    r = subprocess.run(cmd, capture_output=True)
    got = [f for f in os.listdir(OUT) if f.startswith(f"{clip}_jump{n:04d}_")] if os.path.isdir(OUT) else []
    if r.returncode != 0 or len(got) < 2:
        print(f"  [FAIL] {clip} n={n}: {r.stderr.decode('utf-8','replace')[:200]}")
        return False
    print(f"  [OK] {clip} 跳变帧 n={n}: 已取 n={a} 与 n={b}")
    return True


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    print("取「跳变前/后」相邻帧：")
    ok = sum(two_frames(c, n) for c, n in JUMPS)
    print(f"\n完成 {ok}/{len(JUMPS)} → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
