"""L1 measurement of flash / black / static-run events in the tutorial videos.

Reuses the exact-duplicate + near-white + near-black definitions from
projects/game-001/research/killmoment2.py, but scoped to the 5 tutorial clips so it
finishes quickly and reports per-event timestamps.

Output: JSON next to this file + a readable printout.
"""
from __future__ import annotations

import json
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
OUT = pathlib.Path(__file__).resolve().parent / "beat_events.json"
FF = imageio_ffmpeg.get_ffmpeg_exe()
GW, GH = 480, 270
DUP_TOL = 1.0

TARGETS = ["BV1fEbK6xEaP", "BV1LguyzoEbz", "BV1EahSzYEc8", "BV1M9KB6GEQA", "BV1zz4y1N7Dp"]


def decode(path, t0, t1, fps):
    cmd = [FF, "-hide_banner", "-loglevel", "error"]
    if t0:
        cmd += ["-ss", f"{t0}"]
    if t1:
        cmd += ["-to", f"{t1}"]
    cmd += ["-i", str(path), "-vf", f"fps={fps},scale={GW}:{GH}",
            "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (GW * GH)
    return np.frombuffer(raw[: n * GW * GH], dtype=np.uint8).reshape(n, GH, GW).astype(np.int16)


def runs(mask, gap=1):
    out = []
    i, n = 0, len(mask)
    while i < n:
        if mask[i]:
            j = k = i
            while k < n:
                if mask[k]:
                    j = k
                    k += 1
                elif k + gap < n and mask[k + gap]:
                    k += gap
                else:
                    break
            out.append((i, j))
            i = max(j + 1, k)
        else:
            i += 1
    return out


def med(x, w):
    if len(x) < w:
        return np.full(len(x), float(np.median(x)) if len(x) else 0.0)
    pad = np.pad(x, w // 2, mode="edge")
    return np.array([np.median(pad[i:i + w]) for i in range(len(x))])


rep = {}
for stem in TARGETS:
    p = VID / f"{stem}.mp4"
    if not p.exists():
        print("missing", stem)
        continue
    pr = subprocess.run([FF, "-hide_banner", "-i", str(p)],
                        capture_output=True, text=True, errors="replace").stderr
    fps = float(re.search(r"([\d.]+) fps", pr).group(1))
    dm = re.search(r"Duration: (\d+):(\d+):([\d.]+)", pr)
    dur = int(dm.group(1)) * 3600 + int(dm.group(2)) * 60 + float(dm.group(3))

    G = decode(p, 0, dur, fps)
    if len(G) < 10:
        continue
    n = len(G)
    mad = np.abs(np.diff(G, axis=0)).reshape(n - 1, -1)
    mad_max = mad.max(axis=1)
    luma = G.reshape(n, -1).mean(axis=1)
    base = med(luma, 61)

    dup = mad_max <= DUP_TOL
    fr = [(a, b) for a, b in runs(dup, gap=0) if b - a + 1 >= 2]
    fw = (luma > 1.5 * np.maximum(base, 1e-6)) & (luma > 120)
    wr = runs(fw, gap=1)
    fb = (luma < base / 2.2) & (base > 25)
    br = runs(fb, gap=1)
    # long near-static runs (freeze-like) using mean abs diff
    mad_mean = mad.mean(axis=1)
    still = mad_mean < 0.8
    sr = [(a, b) for a, b in runs(still, gap=0) if b - a + 1 >= 3]

    def dump(rr, extra=0):
        return [{"t": round(a / fps, 3), "end": round((b + 1 + extra) / fps, 3),
                 "frames": b - a + 1 + extra, "ms": round((b - a + 1 + extra) / fps * 1000)}
                for a, b in rr]

    print(f"\n--- {stem}  {fps}fps  {dur:.2f}s  ({n} frames analysed) ---")
    print(f"  严格重复帧段(>=2帧): {len(fr)}")
    for e in dump(fr, 1)[:40]:
        print(f"     {e['t']:7.2f}s  {e['ms']:5d}ms  {e['frames']}f")
    print(f"  白闪事件(近白): {len(wr)}")
    for e in dump(wr):
        print(f"     {e['t']:7.2f}s  {e['ms']:5d}ms  {e['frames']}f")
    print(f"  黑场事件(近黑): {len(br)}")
    for e in dump(br)[:60]:
        print(f"     {e['t']:7.2f}s  {e['ms']:5d}ms  {e['frames']}f")
    print(f"  低运动静帧段(mean|d|<0.8, >=3帧): {len(sr)}")
    for e in dump(sr)[:40]:
        print(f"     {e['t']:7.2f}s  {e['ms']:5d}ms  {e['frames']}f")

    rep[stem] = {
        "fps": fps, "duration_s": round(dur, 2), "frames": n,
        "dup_runs": dump(fr, 1), "white_flash": dump(wr), "black": dump(br),
        "low_motion_runs": dump(sr),
    }

OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n[OK] -> {OUT}")
