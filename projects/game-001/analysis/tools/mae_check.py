"""MAE 复核（干净路径）：用 ffmpeg 把帧导成 PNG，再算灰度 MAE。

为什么重做：
    之前我在同一个进程里用 raw 文件缓存帧数据，b 段解码出 781 帧（实际 780）、
    c 段 751（实际 750）——多出 1 帧说明帧集合本身不可靠，基于它的 MAE 结论不能采信。
    这里改成：ffmpeg 直接导出指定帧号的 PNG，再读像素计算，每一步都可单独核对。
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import zlib

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
SRC = {
    "a": "原始素材/4b0460c400bbb5320acb6063b4f59358.mp4",
    "b": "原始素材/6b2eea343eee7595c3c0ede10d21d028.mp4",
    "c": "原始素材/dcc871b1791e7796fadac842593f10f7.mp4",
}
TMP = "projects/game-001/analysis/raw/_mae_tmp"


def read_png_gray(path: str) -> tuple[int, int, bytes]:
    """极简 PNG 读取（只支持 8bit 灰度/真彩、非隔行）—— 避免依赖 Pillow。"""
    data = open(path, "rb").read()
    pos = 8
    w = h = None
    idat = b""
    bitdepth = colortype = None
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bitdepth, colortype = struct.unpack(">IIBB", body[:10])
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
        pos += 12 + ln
    raw = zlib.decompress(idat)
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[colortype]
    stride = w * ch
    out = bytearray()
    prev = bytearray(stride)
    p = 0
    for _ in range(h):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        prev = line
        # 转灰度
        if ch == 1:
            out += line
        else:
            for i in range(0, stride, ch):
                out.append((line[i] * 77 + line[i + 1] * 150 + line[i + 2] * 29) >> 8)
    return w, h, bytes(out)


def grab_frames(clip: str, indices: list[int], scale: str = "320:180") -> dict[int, bytes]:
    src = SRC[clip]
    os.makedirs(TMP, exist_ok=True)
    for f in os.listdir(TMP):
        os.remove(os.path.join(TMP, f))
    expr = "+".join(f"eq(n\\,{n})" for n in indices)
    dst = f"{TMP}/f%02d.png"
    subprocess.run([FF, "-hide_banner", "-v", "error", "-y", "-i", src,
                    "-vf", f"select='{expr}',scale={scale}", "-vsync", "0",
                    "-frames:v", str(len(indices)), dst], capture_output=True)
    files = sorted(os.listdir(TMP))
    out = {}
    for n, f in zip(indices, files):
        _, _, px = read_png_gray(os.path.join(TMP, f))
        out[n] = px
    return out


def mae(a: bytes, b: bytes) -> float:
    if len(a) != len(b) or not a:
        return -1.0
    return sum(abs(a[i] - b[i]) for i in range(len(a))) / len(a)


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print("=" * 74)
    print("用导出的 PNG 直接算相邻帧 MAE（干净路径）")
    print("=" * 74)

    # 声称的跳变点附近，逐对检查 (n-2,n-1) (n-1,n) (n,n+1)
    checks = [("b", [329, 330, 331, 332], "声称跳变 11.000s"),
              ("b", [388, 389, 390, 391], "声称跳变 12.967s"),
              ("c", [61, 62, 63, 64], "声称跳变 2.067s"),
              ("c", [100, 101, 102, 103], "声称跳变 3.367s")]
    for clip, idx, note in checks:
        fr = grab_frames(clip, idx)
        print(f"\n{clip}  {note}   （帧号 -> 相邻 MAE）")
        for i in range(len(idx) - 1):
            a, b = idx[i], idx[i + 1]
            if a in fr and b in fr:
                print(f"   n={a}->{b}  MAE={mae(fr[a], fr[b]):8.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
