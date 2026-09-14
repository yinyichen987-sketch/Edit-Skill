"""L1 colour measurement of the two VALORANT-specific grading tutorials.

Samples frames at a fixed step across each video, computes per-frame mean RGB,
mean HSV saturation, and a luma p5/p95 contrast spread, then prints a table so
before/after grade segments can be compared objectively (no guessing).
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image
import imageio_ffmpeg

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(r"C:\Users\18930\Desktop\Edit skill")
VID = ROOT / "参考视频" / "教学"
FF = imageio_ffmpeg.get_ffmpeg_exe()
TMP = ROOT / "projects" / "game-001" / "research" / "_frames" / "_cmeas"
TMP.mkdir(parents=True, exist_ok=True)


def stats(stem: str, t: float):
    f = TMP / f"{stem}_{t:.2f}.png"
    if not f.exists():
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(VID / f"{stem}.mp4"), "-frames:v", "1", "-y", str(f)],
                       capture_output=True)
    if not f.exists():
        return None
    im = np.asarray(Image.open(f).convert("RGB"), dtype=np.float32) / 255.0
    # exclude the bilibili caption strip at the very bottom where the host burns data
    im = im[: int(im.shape[0] * 0.92)]
    mr, mg, mb = im[..., 0].mean(), im[..., 1].mean(), im[..., 2].mean()
    mx = im.max(axis=2)
    mn = im.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0).mean()
    luma = 0.2126 * im[..., 0] + 0.7152 * im[..., 1] + 0.0722 * im[..., 2]
    p5, p95 = np.percentile(luma, 5), np.percentile(luma, 95)
    return float(mr), float(mg), float(mb), float(sat), float(p5), float(p95), float(p95 - p5)


def run(stem: str, t0: float, t1: float, step: float):
    print(f"\n=== {stem}  {t0:.0f}-{t1:.0f}s step {step}s ===")
    print(f"{'t':>7} {'R':>6} {'G':>6} {'B':>6} {'sat':>6} {'p5':>6} {'p95':>6} {'spread':>7}")
    t = t0
    while t < t1:
        s = stats(stem, t)
        if s:
            print(f"{t:7.1f} {s[0]:6.3f} {s[1]:6.3f} {s[2]:6.3f} {s[3]:6.3f} "
                  f"{s[4]:6.3f} {s[5]:6.3f} {s[6]:7.3f}")
        t += step


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "kfk":
        run("BV1KFKz6MEmL", float(a[1]), float(a[2]), float(a[3]))
    else:
        run(a[0], float(a[1]), float(a[2]), float(a[3]))
