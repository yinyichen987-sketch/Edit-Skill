"""Measure KILL-MOMENT treatment in real high-view VALORANT montages.

These are the six Bilibili reference montages already downloaded into 参考视频/.
Nothing here is a web claim: every number is decoded from the actual files.

For each video we compute, per frame:
  luma_mean   global brightness  -> white/black flash detection
  mad         mean abs diff vs previous frame -> freeze + cut detection

Derived events:
  FREEZE  : run of >= MIN_FREEZE consecutive frames with mad < FREEZE_MAD
  FLASH_W : luma spikes >= FLASH_K x local median
  FLASH_B : luma drops  <= local median / FLASH_K
  CUT     : mad spike >= CUT_K x local median

Audio: RMS envelope per frame -> transient peaks (kill sounds / hitmarkers).
Reported: freeze durations in ms AND frames, flash durations, and the audio-visual
offset between each freeze start and the nearest audio transient.
"""
from __future__ import annotations

import json
import pathlib
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
OUT = ROOT / "projects" / "game-001" / "research" / "killmoment.json"
FF = imageio_ffmpeg.get_ffmpeg_exe()

GW, GH = 320, 180
FREEZE_MAD = 1.6          # mean abs diff (0-255) below which frames are "identical"
MIN_FREEZE = 3            # frames
FLASH_K = 1.55            # multiple of local median luma
CUT_K = 3.0               # multiple of local median mad

TARGETS = [
    ("BV19m3uzhECJ", 0, None),
    ("BV1mbPsz5EeK", 0, None),
    ("BV1U1kJBrEd7", 0, None),
    ("BV1C9826mEZ8", 0, 150),
    ("BV1hzKn6ZEBD", 0, 150),
    ("BV11c6GBrEPm", 0, 150),
]


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
    return np.frombuffer(raw[: n * GW * GH], dtype=np.uint8).reshape(n, GH, GW).astype(np.float32)


def audio_env(path, t0, t1, fps):
    cmd = [FF, "-hide_banner", "-loglevel", "error"]
    if t0:
        cmd += ["-ss", f"{t0}"]
    if t1:
        cmd += ["-to", f"{t1}"]
    cmd += ["-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
            "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    a = np.frombuffer(raw[: len(raw) // 4 * 4], dtype=np.float32)
    spf = 16000 / fps
    n = int(len(a) / spf)
    if n < 2:
        return np.zeros(0)
    return np.array([float(np.sqrt((a[int(i * spf):int((i + 1) * spf)] ** 2).mean() + 1e-12))
                     for i in range(n)])


def med_filt(x, w):
    if len(x) < w:
        return np.full_like(x, np.median(x) if len(x) else 0.0)
    pad = np.pad(x, w // 2, mode="edge")
    return np.array([np.median(pad[i:i + w]) for i in range(len(x))])


report = {}
for stem, t0, t1 in TARGETS:
    p = VID / f"{stem}.mp4"
    if not p.exists():
        print(f"  !! missing {p.name}")
        continue
    probe = subprocess.run([FF, "-hide_banner", "-i", str(p)],
                           capture_output=True, text=True, errors="replace").stderr
    import re
    m = re.search(r"([\d.]+) fps", probe)
    fps = float(m.group(1)) if m else 30.0
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe)
    dur_s = (int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3))) if dur else 0
    if t1 is None:
        t1 = dur_s
    print(f"\n=== {stem}  fps={fps}  分析区间 {t0}-{t1:.1f}s ===")

    G = decode(p, t0, t1, fps)
    if len(G) < 10:
        print("  解码帧数不足")
        continue
    luma = G.reshape(len(G), -1).mean(axis=1)
    mad = np.concatenate([[0.0], np.abs(np.diff(G, axis=0)).reshape(len(G) - 1, -1).mean(axis=1)])
    base_luma = med_filt(luma, 61)
    base_mad = med_filt(mad, 61)

    # --- freeze runs ---
    freezes = []
    i = 1
    while i < len(mad):
        if mad[i] < FREEZE_MAD:
            j = i
            while j + 1 < len(mad) and mad[j + 1] < FREEZE_MAD:
                j += 1
            if j - i + 2 >= MIN_FREEZE:
                freezes.append((round(t0 + (i - 1) / fps, 3), round((j - i + 2) / fps, 3),
                                (j - i + 2)))
            i = j + 1
        else:
            i += 1

    # --- flashes ---
    whites = [(round(t0 + k / fps, 3), round(float(luma[k] / max(base_luma[k], 1e-6)), 2))
              for k in range(len(luma)) if luma[k] > FLASH_K * max(base_luma[k], 1e-6)
              and luma[k] > 110]
    blacks = [(round(t0 + k / fps, 3), round(float(luma[k] / max(base_luma[k], 1e-6)), 2))
              for k in range(len(luma)) if luma[k] < base_luma[k] / 2.2 and base_luma[k] > 25]

    # --- cuts ---
    cuts = [round(t0 + k / fps, 3) for k in range(len(mad))
            if mad[k] > CUT_K * max(base_mad[k], 0.8)]

    # --- audio transients ---
    env = audio_env(p, t0, t1, fps)
    trans = []
    if len(env) > 8:
        eb = med_filt(env, 41)
        for k in range(1, len(env) - 1):
            if env[k] > 3.0 * max(eb[k], 1e-7) and env[k] >= env[k - 1] and env[k] >= env[k + 1]:
                if not trans or (k - trans[-1]) / fps > 0.12:
                    trans.append(k)
    trans_t = [round(t0 + k / fps, 3) for k in trans]

    print(f"  帧数 {len(G)}   检出 定格 {len(freezes)} 个 / 白闪 {len(whites)} 帧 / "
          f"黑场 {len(blacks)} 帧 / 切点 {len(cuts)} 个 / 音频瞬态 {len(trans_t)} 个")

    if freezes:
        durs_ms = [f[1] * 1000 for f in freezes]
        print(f"  定格时长 (ms): 中位 {np.median(durs_ms):.0f}  最短 {min(durs_ms):.0f}  "
              f"最长 {max(durs_ms):.0f}  n={len(freezes)}")
        print(f"  定格时长 (帧): 中位 {np.median([f[2] for f in freezes]):.1f}  "
              f"分布 {sorted(set(f[2] for f in freezes))}")
        print(f"  定格出现率: {len(freezes)/(len(G)/fps)*60:.1f} 次/分")
    if whites:
        print(f"  白闪样本 (t, 亮度倍数): {whites[:12]}")
    if blacks:
        print(f"  黑场样本 (t, 亮度比): {blacks[:12]}")
    if cuts:
        rate = len(cuts) / (len(G) / fps) * 60
        d = np.diff(cuts) * 1000
        print(f"  切点密度 {rate:.1f} 切/分；镜长中位 {np.median(d):.0f} ms，"
              f"最短 {d.min():.0f} ms" if len(d) else "")

    # freeze -> nearest audio transient offset
    if freezes and trans_t:
        offs = []
        for ft, fd, fn in freezes:
            near = min(trans_t, key=lambda x: abs(x - ft))
            offs.append(round((ft - near) * 1000))
        print(f"  定格起点 − 最近音频瞬态 (ms): 中位 {np.median(offs):.0f}  "
              f"范围 {min(offs)}..{max(offs)}  n={len(offs)}")

    report[stem] = {
        "fps": fps, "duration_s": round(dur_s, 2),
        "analysed_s": [t0, round(float(t1), 2)],
        "n_frames": int(len(G)),
        "freezes": [{"t": f[0], "dur_ms": round(f[1] * 1000), "frames": f[2]} for f in freezes],
        "white_flash_times": [w[0] for w in whites],
        "black_frame_times": [b[0] for b in blacks],
        "cut_times": cuts,
        "cut_rate_per_min": round(len(cuts) / (len(G) / fps) * 60, 2),
        "audio_transient_times": trans_t,
        "freeze_minus_audio_ms": [round((ft - min(trans_t, key=lambda x: abs(x - ft))) * 1000)
                                  for ft, _, _ in freezes] if (freezes and trans_t) else [],
    }

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n[OK] -> {OUT.relative_to(ROOT)}")
