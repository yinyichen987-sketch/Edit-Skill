"""把 4 处跳变从「点」改标为「不安全窗口」：给出内容变化那一对相邻帧的真实 PTS。

为什么：跳变不是瞬时点，而是发生在**一对相邻帧之间**。用单一时间码（尤其经帧号换算得到的
名义值）会让下游以为边界精确到毫秒。正确口径是区间。

同时核对：b 段第一个跳变窗口是否与 VFR 丢帧点重合（两者应是同一个区间）。
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
    "b": "原始素材/6b2eea343eee7595c3c0ede10d21d028.mp4",
    "c": "原始素材/dcc871b1791e7796fadac842593f10f7.mp4",
}
# 由 mae_check.py 实测得到的「内容变化的一对相邻帧」（前帧号, 后帧号）
# 注意 c 段第二处：正确帧对是 #101->#102，不是 #100->#101。
# 我最初的 mae_check 跑出 100->101（陈旧缓存导致的一帧错位），改用全新解码复核后为 101->102，
# 并以直接 seek 到 t=3.37 目视确认该帧仍是「室外庭院」（即尚未切）。已按注释固化。
CUTS = [("b", 329, 330, "11.000"), ("b", 388, 389, "12.967"),
        ("c", 62, 63, "2.067"), ("c", 101, 102, "3.367")]


def pts_for(clip: str) -> dict[int, float]:
    """整段 passthrough 解码，取每帧（输出序）pts_time。"""
    tmp = "projects/game-001/analysis/raw/_win.txt"
    with open(tmp, "wb") as fh:
        subprocess.run([FF, "-hide_banner", "-nostats", "-v", "info", "-y",
                        "-i", SRC[clip], "-vf", "showinfo", "-an",
                        "-f", "null", os.devnull],
                       stdout=subprocess.DEVNULL, stderr=fh)
    out = {}
    idx = 0
    for line in open(tmp, encoding="utf-8", errors="replace"):
        if "pts_time:" in line and "n:" in line:
            try:
                t = float(line.split("pts_time:")[1].split()[0])
                out[idx] = t
                idx += 1
            except (IndexError, ValueError):
                continue
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
    clip_pts = {k: pts_for(k) for k in SRC}
    for k, d in clip_pts.items():
        print(f"{k}: 解码帧数 {len(d)}")

    print()
    print(f"{'素材':4} {'名义码':>8} {'不安全窗口(真实PTS)':>28} {'宽度ms':>8}  名义码是否落入")
    print("-" * 74)
    rows = []
    for clip, n_prev, n_next, nominal in CUTS:
        pts = clip_pts[clip]
        if n_prev not in pts or n_next not in pts:
            print(f"{clip:4} {nominal:>8}  帧号越界")
            continue
        lo, hi = pts[n_prev], pts[n_next]
        width = (hi - lo) * 1000
        nominal_v = float(nominal)
        inside = lo <= nominal_v <= hi
        print(f"{clip:4} {nominal:>8}   [{lo:.4f}, {hi:.4f}] {width:>13.1f}  "
              f"{'✓' if inside else '✗ 早 ' + f'{lo - nominal_v:.4f}s'}")
        rows.append({"clip": clip, "nominal": nominal_v,
                     "frame_pair": [n_prev, n_next],
                     "unsafe_window_s": [round(lo, 4), round(hi, 4)],
                     "width_ms": round(width, 1),
                     "nominal_inside": inside})

    # b 段第一个跳变窗口 vs VFR 丢帧点
    print()
    print("b 段第一个跳变窗口 vs 已知 VFR 丢帧点：")
    b_win = next((r for r in rows if r["clip"] == "b" and r["nominal"] == 11.0), None)
    if b_win:
        lo, hi = b_win["unsafe_window_s"]
        print(f"   跳变窗口     [{lo}, {hi}]")
        print(f"   丢帧点       10.979688（帧 #329 的 PTS），其后 11.045378")
        same = abs(lo - 10.979688) < 0.002 and abs(hi - 11.045378) < 0.002
        print(f"   → {'同一个区间：跳变与丢帧重合' if same else '不是同一区间，需分别标注'}")

    json.dump(rows, open("projects/game-001/analysis/raw/cut_windows.json", "w",
                         encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n[OK] projects/game-001/analysis/raw/cut_windows.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
