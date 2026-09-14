"""Refined kill-moment measurement.

V1 used mad < 1.6 which also catches "low motion" gameplay. A genuine freeze frame
(定格) is an EXACT duplicate of the previous frame, so v2 uses max abs diff <= 1 on the
full-resolution luma and requires the run to end with a real change.

Also reports flash / black EVENTS as contiguous runs (allowing 1-frame gaps), with
durations in frames and ms, and the per-video distribution.

Cut-rate detection is deliberately NOT reported: frame-difference cut detection is
unreliable on continuous FPS footage (motion and effects dominate the signal), a failure
mode already documented in this workspace.
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

ROOT = pathlib.Path(__file__).resolve().parents[3]
VID = ROOT / "参考视频"
OUT = ROOT / "projects" / "game-001" / "research" / "killmoment2.json"
FF = imageio_ffmpeg.get_ffmpeg_exe()
GW, GH = 480, 270
DUP_TOL = 1.0

TARGETS = ["BV19m3uzhECJ", "BV1mbPsz5EeK", "BV1U1kJBrEd7",
           "BV1C9826mEZ8", "BV1hzKn6ZEBD", "BV11c6GBrEPm"]


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
    """Contiguous True runs, tolerating `gap` False frames inside a run."""
    out = []
    i = 0
    n = len(mask)
    while i < n:
        if mask[i]:
            j = i
            k = i
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
print("=== 参考成片：定格 / 白闪 / 黑场（严格口径）===")
for stem in TARGETS:
    p = VID / f"{stem}.mp4"
    if not p.exists():
        continue
    pr = subprocess.run([FF, "-hide_banner", "-i", str(p)],
                        capture_output=True, text=True, errors="replace").stderr
    fps = float(re.search(r"([\d.]+) fps", pr).group(1))
    dm = re.search(r"Duration: (\d+):(\d+):([\d.]+)", pr)
    dur = int(dm.group(1)) * 3600 + int(dm.group(2)) * 60 + float(dm.group(3))
    t1 = dur if dur < 200 else 180.0

    G = decode(p, 0, t1, fps)
    if len(G) < 10:
        continue
    n = len(G)
    mad = np.abs(np.diff(G, axis=0)).reshape(n - 1, -1)
    mad_max = mad.max(axis=1)
    mad_mean = mad.mean(axis=1)
    luma = G.reshape(n, -1).mean(axis=1)
    base = med(luma, 61)
    span = t1

    # --- true freeze frames: exact duplicates ---
    dup = mad_max <= DUP_TOL
    fr_runs = [(a, b) for a, b in runs(dup, gap=0) if b - a + 1 >= 2]
    fr_ms = [(b - a + 2) / fps * 1000 for a, b in fr_runs]

    # --- flash events ---
    fw = luma > 1.5 * np.maximum(base, 1e-6)
    fw &= luma > 120
    w_runs = runs(fw, gap=1)
    w_ms = [(b - a + 1) / fps * 1000 for a, b in w_runs]
    fb = (luma < base / 2.2) & (base > 25)
    b_runs = runs(fb, gap=1)
    b_ms = [(b - a + 1) / fps * 1000 for a, b in b_runs]

    print(f"\n--- {stem}  {fps}fps  分析 {span:.0f}s  ({n} 帧) ---")
    print(f"  严格定格帧 (相邻帧完全相同): {len(fr_runs)} 段")
    if fr_ms:
        print(f"    时长 ms: 中位 {np.median(fr_ms):.0f} | 分布 "
              f"{sorted(set(int(round(x)) for x in fr_ms))}")
        print(f"    时长 帧: 中位 {np.median([b-a+2 for a,b in fr_runs]):.1f} | "
              f"分布 {sorted(set(b-a+2 for a,b in fr_runs))}")
        print(f"    起点 s : {[round(a/fps,2) for a,b in fr_runs][:20]}")
    print(f"  白闪事件: {len(w_runs)} 段" + (
        f" | 时长 ms 中位 {np.median(w_ms):.0f}, 分布 "
        f"{sorted(set(int(round(x)) for x in w_ms))}" if w_ms else ""))
    print(f"  黑场事件: {len(b_runs)} 段" + (
        f" | 时长 ms 中位 {np.median(b_ms):.0f}, 分布 "
        f"{sorted(set(int(round(x)) for x in b_ms))}" if b_ms else ""))

    rep[stem] = {
        "fps": fps, "analysed_s": round(span, 2), "frames": n,
        "freeze_runs": [{"t": round(a / fps, 3), "frames": b - a + 2,
                         "ms": round((b - a + 2) / fps * 1000)} for a, b in fr_runs],
        "white_flash_events": [{"t": round(a / fps, 3), "frames": b - a + 1,
                                "ms": round((b - a + 1) / fps * 1000)} for a, b in w_runs],
        "black_events": [{"t": round(a / fps, 3), "frames": b - a + 1,
                          "ms": round((b - a + 1) / fps * 1000)} for a, b in b_runs],
        "max_luma_ratio": round(float((luma / np.maximum(base, 1e-6)).max()), 2),
    }

allf = [r["ms"] for v in rep.values() for r in v["freeze_runs"]]
if allf:
    print(f"\n=== 汇总：严格定格帧时长 (n={len(allf)}) ===")
    print(f"  中位 {np.median(allf):.0f} ms | 四分位 "
          f"{np.percentile(allf,25):.0f} / {np.percentile(allf,75):.0f} ms | "
          f"范围 {min(allf)}..{max(allf)} ms")
    import collections
    c = collections.Counter(round(x) for x in allf)
    print(f"  最常见的时长: {c.most_common(8)}")

OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n[OK] -> {OUT.relative_to(ROOT)}")
