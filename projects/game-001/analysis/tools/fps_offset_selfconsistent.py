"""在**帧数自洽**的前提下重算 fps=4 的取样偏差。

背景（已由 fps_offset_final.py 定案）：
    * `fps=4` 的输出时间戳严格等于 j/4（偏差 0.0000）—— 时间轴是线性的，这点已被证实。
    * 但像素与 PTS 的**帧数**只在 a 段一致：
        a 容器 570 / showinfo 570 / raw 570
        b 容器 780 / showinfo 780 / raw 781   ← 多 1 帧
        c 容器 750 / showinfo 750 / raw 751   ← 多 1 帧
    帧数不等时按下标配对必然错位，这正是 b/c 均值不可信的根源。

本脚本改用**自洽**做法：像素与 PTS 都取自 showinfo（该路径帧数 = 容器帧数，
即"显示帧数"，无补帧）。做法是把像素以 png 序列导出（与 showinfo 同一次解码），
再用 showinfo 的 n -> pts_time 映射读回。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
SRC = {
    "a": "原始素材/4b0460c400bbb5320acb6063b4f59358.mp4",
    "b": "原始素材/6b2eea343eee7595c3c0ede10d21d028.mp4",
    "c": "原始素材/dcc871b1791e7796fadac842593f10f7.mp4",
}
TMP = "projects/game-001/analysis/raw/_self"
W, H = 64, 36
LINE_RE = re.compile(r"n:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:(-?[\d.]+)")


def dump_png_seq(src: str, vf: str, outdir: str) -> tuple[list[str], list[tuple[int, float]]]:
    """一次解码：像素出 png 序列、showinfo 出 n->pts_time。帧数应相等。"""
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir, exist_ok=True)
    meta = os.path.abspath(os.path.join(outdir, "_si.txt"))
    chain = f"{vf},scale={W}:{H},showinfo" if vf else f"scale={W}:{H},showinfo"
    with open(meta, "wb") as fh:
        subprocess.run([FF, "-hide_banner", "-nostats", "-v", "info", "-y", "-i",
                        os.path.abspath(src), "-vf", chain, "-vsync", "0",
                        "-f", "image2", os.path.abspath(os.path.join(outdir, "f_%05d.png"))],
                       stdout=subprocess.DEVNULL, stderr=fh)
    pngs = sorted(f for f in os.listdir(outdir) if f.startswith("f_") and f.endswith(".png"))
    pts = []
    for line in open(meta, encoding="utf-8", errors="replace"):
        m = LINE_RE.search(line)
        if m:
            pts.append((int(m.group(1)), float(m.group(3))))
    return [os.path.join(outdir, p) for p in pngs], pts


def read_gray(path: str) -> bytes:
    """用 ffmpeg 把单张 png 转成灰度原始字节（避免自己写 PNG 解码）。"""
    r = subprocess.run([FF, "-hide_banner", "-v", "error", "-i", path,
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    return r.stdout


def mad(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a) if a and len(a) == len(b) else 1e9


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    os.makedirs(TMP, exist_ok=True)
    try:
        return _run()
    finally:
        # 必须清理：本脚本每段源帧都导一张 PNG，会产生数千个中间文件。
        # 我第一版漏了这一步，在 raw/ 下留下 2386 个文件 / 285MB —— 这是我的卫生欠账，已清理。
        # 用 try/finally 保证异常路径也清理。
        #
        # 更正：我曾把 creative-reviewer 的 frame-probe 崩溃归因于这些残留 PNG。**该归因错误** ——
        # 它的工具只 glob 自己运行的专属子目录（measure_sampling_bias.py:107），从不扫 raw/；
        # 真因是它 _tmp 里一个被中断、写了一半的 PNG。
        # 不要把"我的欠账"与"别人的 bug"因果绑定。清理的理由是卫生本身，不是那条因果。
        shutil.rmtree(TMP, ignore_errors=True)


def _run() -> int:
    for k, src in SRC.items():
        src_png, src_pts = dump_png_seq(src, "", f"{TMP}/{k}_src")
        rs_png, rs_pts = dump_png_seq(src, "fps=4", f"{TMP}/{k}_rs")
        print("=" * 76)
        print(f"{k}: 源 {len(src_png)} png / {len(src_pts)} pts ; "
              f"fps4 {len(rs_png)} png / {len(rs_pts)} pts")
        if len(src_png) != len(src_pts) or len(rs_png) != len(rs_pts):
            print("   !! 帧数与 PTS 不等，跳过（拒绝出结论）")
            continue

        src_gray = [read_gray(p) for p in src_png]
        rs_gray = [read_gray(p) for p in rs_png]

        idxs, offs = [], []
        for j, rf in enumerate(rs_gray):
            nominal = j / 4.0
            lo = max(0, int(nominal * 30) - 16)
            hi = min(len(src_gray), int(nominal * 30) + 16)
            best_i, best_v = None, 1e9
            for i in range(lo, hi):
                v = mad(rf, src_gray[i])
                if v < best_v:
                    best_v, best_i = v, i
            if best_i is None or best_v > 0.5:
                continue
            idxs.append(best_i)
            offs.append(round(src_pts[best_i][1] - nominal, 4))

        steps = {}
        for i in range(1, len(idxs)):
            d = idxs[i] - idxs[i - 1]
            steps[d] = steps.get(d, 0) + 1
        vals = {}
        for o in offs:
            vals[o] = vals.get(o, 0) + 1
        print(f"   样本 {len(offs)}  步长 {steps}")
        print(f"   偏差取值 {sorted(vals.items())}")
        print(f"   min={min(offs):+.4f} max={max(offs):+.4f} "
              f"mean={sum(offs)/len(offs):+.4f}")
        bad = {d: c for d, c in steps.items() if d not in (7, 8)}
        print(f"   {'!! 步长异常 ' + str(bad) if bad else '步长仅 7/8（自洽）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
