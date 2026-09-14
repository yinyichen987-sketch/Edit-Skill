"""L1: frame-exact event scan for a single tutorial video.

Prints, per frame index: exact-black frames, near-black frames, near-white frames and
big frame-to-frame jumps, so transition *mechanisms* can be verified frame by frame
instead of guessed.

usage: python events_exact.py <stem> [t0] [t1]
"""
from __future__ import annotations

import pathlib
import re
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


def decode(path, t0, t1, fps, w=480, h=270):
    cmd = [FF, "-hide_banner", "-loglevel", "error"]
    if t0:
        cmd += ["-ss", str(t0)]
    if t1:
        cmd += ["-to", str(t1)]
    cmd += ["-i", str(path), "-vf", f"fps={fps},scale={w}:{h}",
            "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (w * h)
    return np.frombuffer(raw[: n * w * h], dtype=np.uint8).reshape(n, h, w)


def main():
    stem = sys.argv[1]
    t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    t1 = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    p = VID / f"{stem}.mp4"
    pr = subprocess.run([FF, "-hide_banner", "-i", str(p)],
                        capture_output=True, text=True, errors="replace").stderr
    fps = float(re.search(r"([\d.]+) fps", pr).group(1))
    G = decode(p, t0, t1, fps)
    n = len(G)
    lum = G.reshape(n, -1).mean(axis=1)
    dark = G.reshape(n, -1) < 16
    frac_dark = dark.mean(axis=1)
    frac_bright = (G.reshape(n, -1) > 235).mean(axis=1)
    d = np.abs(np.diff(G.astype(np.int16), axis=0)).reshape(max(n - 1, 1), -1).mean(axis=1)

    print(f"== {stem} t={t0}..{t1 or 'end'} fps={fps} frames={n}")
    print("-- frac<16 >=0.90 (near/completely black) --")
    for i in range(n):
        if frac_dark[i] >= 0.90:
            print(f"   f{i:5d}  t={(t0 + i / fps):7.3f}s  lum={lum[i]:6.1f}  frac<16={frac_dark[i]:.3f}")
    print("-- frac>235 >=0.40 (near white) --")
    for i in range(n):
        if frac_bright[i] >= 0.40:
            print(f"   f{i:5d}  t={(t0 + i / fps):7.3f}s  lum={lum[i]:6.1f}  frac>235={frac_bright[i]:.3f}")
    print("-- big jumps mean|d| > 60 --")
    for i in range(len(d)):
        if d[i] > 60:
            print(f"   f{i:5d}->{i+1:5d}  t={(t0 + i / fps):7.3f}->{(t0 + (i + 1) / fps):7.3f}s  d={d[i]:6.1f}")


if __name__ == "__main__":
    main()
