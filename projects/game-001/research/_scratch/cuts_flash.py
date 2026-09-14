"""L1 shot/flash detection on the demo montages inside the tutorials.

For each clip: decode a small greyscale proxy at 30fps, then per frame compute
  * mean luminance (flash = big positive spike, black = big negative)
  * mean abs frame difference (cut = spike)
and report spike times. Only these two cheap signals are used; no editing
timeline is inferred beyond what the proxy shows.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import numpy as np
import imageio_ffmpeg

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parents[4]
VID = ROOT / "参考视频" / "教学"
FF = imageio_ffmpeg.get_ffmpeg_exe()


def proxy(stem: str, w: int, h: int, fps: float = 30.0) -> np.ndarray:
    p = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-i",
                        str(VID / f"{stem}.mp4"), "-vf", f"fps={fps},scale={w}:{h}",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    n = a.size // (w * h)
    return a[:n * w * h].reshape(n, h, w).astype(np.float32)


def report(stem: str, t0: float, t1: float, w=160, h=90, fps=30.0,
           dthr=9.0, lthr=55.0, dark=25.0):
    a = proxy(stem, w, h, fps)
    lum = a.reshape(len(a), -1).mean(axis=1)
    md = np.abs(np.diff(a, axis=0)).reshape(len(a) - 1, -1).mean(axis=1)
    i0, i1 = int(t0 * fps), min(int(t1 * fps), len(lum))
    print(f"\n=== {stem}  window {t0:.1f}..{t1:.1f}s  ({len(a)} frames total) ===")
    cuts = [(i / fps) for i in range(i0, min(i1, len(md))) if md[i] > dthr]
    # collapse clusters
    merged = []
    for t in cuts:
        if merged and t - merged[-1][-1] < 0.10:
            merged[-1].append(t)
        else:
            merged.append([t])
    print(f"  frame-diff threshold {dthr} -> {len(merged)} cut candidates in window")
    if merged:
        ct = [g[0] for g in merged]
        print("  cuts (s): " + ", ".join(f"{t:.2f}" for t in ct))
        if len(ct) > 2:
            io = np.diff(ct)
            io = io[io > 0.08]
            print(f"  cut IOI med={np.median(io)*1000:.0f}ms  "
                  f"range {io.min()*1000:.0f}-{io.max()*1000:.0f}ms  "
                  f"cuts/min={len(ct)/((t1-t0)/60):.2f}")
    for name, thr, sign in (("flash", lthr, +1), ("black", dark, -1)):
        base = np.median(lum[i0:i1]) if i1 > i0 else 1
        ev = []
        for i in range(i0 + 1, i1):
            if sign > 0 and lum[i] - lum[i - 1] > thr:
                ev.append((i / fps, lum[i]))
            elif sign < 0 and lum[i - 1] - lum[i] > thr:
                ev.append((i / fps, lum[i]))
        print(f"  {name} events (lum step>{thr}): " +
              (", ".join(f"{t:.2f}(L{v:.0f})" for t, v in ev) if ev else "none"))
    print(f"  lum: min={lum[i0:i1].min():.0f} med={np.median(lum[i0:i1]):.0f} max={lum[i0:i1].max():.0f}")


if __name__ == "__main__":
    # 击杀结尾 demo (after the tutorial's construction, the "看效果" part)
    report("BV1ue8y6XE2M", 40.0, 70.4)
    # 卡点 demo
    report("BV1qx5463Exr", 45.0, 67.0)
    # opening treatments
    report("BV1ue8y6XE2M", 0.0, 12.0)
    report("BV1qx5463Exr", 0.0, 14.0)
