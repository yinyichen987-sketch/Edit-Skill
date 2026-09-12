"""定案：fps=4 时间偏差到底是多少，以及 sidecar 帧数为何是 781/751。

两条独立路径各自自洽，避免"两侧配错下标"：
  A) showinfo 侧：每行同时给出该帧的 n（输出序）与该帧 pts_time —— 天然自洽，无需配对
  B) 像素侧：raw 解码帧数 + pymediainfo 容器帧数

关键诊断：**逐帧列出 passthrough 解码中 pts_time 不递增的位置** ——
若 781 帧里有 1 帧是重复帧（同一 PTS 出现两次），那就是"多出来的帧"，
它会使其后所有下标偏移 1，正是 b/c 均值偏大的机制。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import imageio_ffmpeg

try:
    from pymediainfo import MediaInfo
except ImportError:
    MediaInfo = None

FF = imageio_ffmpeg.get_ffmpeg_exe()
SRC = {
    "a": "原始素材/4b0460c400bbb5320acb6063b4f59358.mp4",
    "b": "原始素材/6b2eea343eee7595c3c0ede10d21d028.mp4",
    "c": "原始素材/dcc871b1791e7796fadac842593f10f7.mp4",
}
TMP = "projects/game-001/analysis/raw/_final"
LINE_RE = re.compile(r"n:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:(-?[\d.]+)")


def showinfo_frames(src: str, vf: str) -> list[tuple[int, float]]:
    """返回 [(n, pts_time)]。showinfo 写 stderr（info 级）。

    注意：必须把 `showinfo` **追加到滤镜链里**。我先前误传 `vf="null"` 导致链里
    没有 showinfo，于是日志里一条 pts_time 都没有 —— 空列表却不报错，静默得出错误结论。
    """
    os.makedirs(TMP, exist_ok=True)
    meta = os.path.abspath(os.path.join(TMP, "si.txt"))
    if os.path.exists(meta):
        os.remove(meta)
    chain = f"{vf},showinfo" if vf else "showinfo"
    with open(meta, "wb") as fh:
        subprocess.run([FF, "-hide_banner", "-nostats", "-v", "info", "-y", "-i",
                        os.path.abspath(src), "-vf", chain, "-an", "-f", "null", os.devnull],
                       stdout=subprocess.DEVNULL, stderr=fh)
    out = []
    for line in open(meta, encoding="utf-8", errors="replace"):
        m = LINE_RE.search(line)
        if m:
            out.append((int(m.group(1)), float(m.group(3))))
    return out


def raw_count(src: str, vf: str) -> int:
    raw = os.path.abspath(os.path.join(TMP, "px.rgb"))
    if os.path.exists(raw):
        os.remove(raw)
    subprocess.run([FF, "-hide_banner", "-nostats", "-v", "error", "-y", "-i",
                    os.path.abspath(src), "-vf", f"{vf},scale=160:90",
                    "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", raw],
                   capture_output=True)
    return (os.path.getsize(raw) // (160 * 90 * 3)) if os.path.exists(raw) else 0


def container_frames(src: str) -> int | None:
    if MediaInfo is None:
        return None
    for t in MediaInfo.parse(src).tracks:
        if t.track_type == "Video" and t.frame_count:
            return int(t.frame_count)
    return None


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    report = {}
    for k, src in SRC.items():
        pas = showinfo_frames(src, "null")                 # 源时间轴
        fps4 = showinfo_frames(src, "fps=4")               # 重采样
        n_pas_raw = raw_count(src, "null")
        cc = container_frames(src)

        # 找 pts_time 非递增（重复帧）位置
        dup = []
        for i in range(1, len(pas)):
            if pas[i][1] <= pas[i - 1][1]:
                dup.append({"idx": i, "prev_pts": pas[i - 1][1], "pts": pas[i][1]})

        # fps=4 的输出帧：showinfo 给的 pts_time 即其时间戳；与标称 j/4 比对
        ts = [t for _, t in fps4]
        dev = [round(ts[j] - j / 4.0, 4) for j in range(len(ts))]

        report[k] = {
            "container_frames": cc,
            "passthrough_showinfo_frames": len(pas),
            "passthrough_raw_frames": n_pas_raw,
            "duplicate_pts_positions": dup,
            "fps4_frames": len(fps4),
            "fps4_timestamp_deviation_min": min(dev) if dev else None,
            "fps4_timestamp_deviation_max": max(dev) if dev else None,
        }

        print("=" * 78)
        print(f"{k}  ({src})")
        print(f"  容器帧数(pymediainfo)        {cc}")
        print(f"  passthrough showinfo 帧数    {len(pas)}")
        print(f"  passthrough raw 解码帧数     {n_pas_raw}")
        print(f"  **非递增(重复/补)帧位置**    {len(dup)} 处")
        for d in dup[:5]:
            print(f"       idx={d['idx']}  prev_pts={d['prev_pts']}  pts={d['pts']}")
        if ts:
            print(f"  fps=4 帧数                   {len(fps4)}")
            print(f"  fps=4 自身时间戳 vs j/4 偏差  min={min(dev):+.4f}  max={max(dev):+.4f}"
                  f"  (这一项是「滤镜输出的时间戳本身」偏差，与内容取样无关)")
            print(f"  fps=4 时间戳取值集合         {sorted(set(dev))[:6]}")

    json.dump(report, open("projects/game-001/analysis/raw/fps_offset_final.json", "w",
                           encoding="utf-8"), ensure_ascii=False, indent=2)
    print()
    print("[OK] projects/game-001/analysis/raw/fps_offset_final.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
