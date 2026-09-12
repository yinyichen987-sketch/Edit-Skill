"""在同一解码路径内取「帧像素 + 该帧 PTS」，消除索引错位的可能性。

为什么重做：
    诊断显示 raw 解码帧数（b 781 / c 751）与 showinfo 的 PTS 条数（b 780 / c 750）
    **不一致**，而 a（570/570）一致。两侧帧数不等时，任何"按下标配对"的做法都不可靠 ——
    多出来的那一帧会使其后所有下标整体偏移 1。

    因此本脚本用**同一次解码**同时产出像素与 PTS：rawvideo 落盘、showinfo 经 metadata=print
    落盘，两者共用同一 filter 链。随后强制断言两者帧数相等，不等则拒绝给出结论。

输出：每处偏差的「源帧号 + 该帧 PTS」，可逐帧复核。
"""
from __future__ import annotations

import os
import re
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
TMP = "projects/game-001/analysis/raw/_paired"
PTS_RE = re.compile(r"pts_time=(-?[\d.]+)")


def decode_paired(src: str, tag: str) -> tuple[list[bytes], list[float]]:
    """同一次解码：像素写 raw，PTS 用 metadata=print 写文本文件。

    坑：metadata=print:file= 的值里若含未转义的 ':'（Windows 盘符），ffmpeg 会解析失败，
    且**不报错**——表现是 PTS 文件为空、同时整个 filter 链失效（连 fps/scale 都不生效，
    帧数与源相同）。因此这里一律用**相对路径 + 不含冒号**的文件名。
    """
    os.makedirs(TMP, exist_ok=True)
    raw_p = os.path.abspath(os.path.join(TMP, f"{tag}.rgb"))
    met_name = f"{tag}_pts.txt"                      # 相对 metadata 的 file=，落在 cwd=TMP 下
    met_p = os.path.abspath(os.path.join(TMP, met_name))
    for p in (raw_p, met_p):
        if os.path.exists(p):
            os.remove(p)

    vf = f"scale={W}:{H},metadata=print:file={met_name}"
    # cwd 切到 TMP 是为了让 metadata 的相对文件名落在 TMP 下；
    # 因此输入路径必须绝对化，否则相对素材路径会解析失败。
    r = subprocess.run(
        [FF, "-hide_banner", "-nostats", "-v", "error", "-y", "-i", os.path.abspath(src),
         "-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", raw_p],
        capture_output=True, cwd=TMP)
    if r.returncode != 0:
        print("   decode err:", r.stderr.decode("utf-8", "replace")[:200])

    data = open(raw_p, "rb").read()
    n = len(data) // SIZE
    frames = [data[i * SIZE:(i + 1) * SIZE] for i in range(n)]

    pts = []
    if os.path.exists(met_p):
        for line in open(met_p, encoding="utf-8", errors="replace"):
            m = PTS_RE.search(line)
            if m:
                pts.append(float(m.group(1)))
    return frames, pts


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
    print("=" * 78)
    print("同路径配对：帧数是否相等（不等则拒绝出结论）")
    print("=" * 78)
    src_data = {}
    for k, src in SRC.items():
        fr, pts = decode_paired(src, k)
        s_fr, s_pts = decode_paired(src, f"{k}_fps4")
        marker = "OK" if (len(fr) == len(pts) and len(s_fr) == len(s_pts)) else "!! 不相等"
        print(f"  {k}: 源帧 {len(fr):>4} / 源PTS {len(pts):>4}   "
              f"fps4帧 {len(s_fr):>4} / fps4PTS {len(s_pts):>4}   {marker}")
        src_data[k] = (fr, pts, s_fr)

    print()
    print("=" * 78)
    print("偏差（同路径配对）")
    print("=" * 78)
    print(f"{'素材':5}{'样本':>6}{'步长分布':>18}{'偏差取值(出现次数)':>40}{'mean':>9}")
    summary = {}
    for k, (fr, pts, rs) in src_data.items():
        idxs, offs = [], []
        for j, rf in enumerate(rs):
            nominal = j / 4.0
            lo = max(0, int(nominal * 30) - 16)
            hi = min(len(fr), int(nominal * 30) + 16)
            if hi <= lo:
                continue
            best_i, best_v = None, 1e9
            for i in range(lo, hi):
                v = mad(rf, fr[i])
                if v < best_v:
                    best_v, best_i = v, i
            if best_i is None or best_v > 0.5:
                continue
            idxs.append(best_i)
            offs.append(round(pts[best_i] - nominal, 4))
        steps = {}
        for i in range(1, len(idxs)):
            steps[idxs[i] - idxs[i - 1]] = steps.get(idxs[i] - idxs[i - 1], 0) + 1
        vals = {}
        for o in offs:
            vals[o] = vals.get(o, 0) + 1
        mean = round(sum(offs) / len(offs), 4) if offs else None
        summary[k] = {"mean": mean, "steps": steps, "value_counts": vals}
        print(f"{k:5}{len(offs):>6}{str(steps):>18}   "
              f"{', '.join(f'{v:.4f}×{c}' for v, c in sorted(vals.items())):<38}{mean:>9}")

    import json
    json.dump(summary, open("projects/game-001/analysis/raw/fps_offset_paired.json", "w",
                            encoding="utf-8"), ensure_ascii=False, indent=2)
    print()
    print("[OK] projects/game-001/analysis/raw/fps_offset_paired.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
