"""L1 audio analysis: onsets / beat intervals for the tutorial clips.

Decodes mono 44.1k f32 with ffmpeg, then:
  * short-time RMS envelope (1024 hop)
  * spectral-flux onset strength
  * peak picking -> onset times
  * inter-onset intervals (IOI) + implied BPM
No number is asserted that this script did not compute.
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
SR = 44100


def decode(stem: str) -> np.ndarray:
    p = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-i",
                        str(VID / f"{stem}.mp4"), "-vn", "-ac", "1",
                        "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    return np.frombuffer(p.stdout, dtype=np.float32)


def analyse(stem: str, fps_env: float = 50.0):
    x = decode(stem)
    n = int(SR / fps_env)
    m = len(x) // n
    fr = x[:m * n].reshape(m, n)
    rms = np.sqrt((fr ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-12)
    # spectral flux via STFT
    win = 1024
    hop = int(SR / fps_env)
    frames = []
    hann = np.hanning(win)
    for i in range(0, len(x) - win, hop):
        frames.append(np.abs(np.fft.rfft(x[i:i + win] * hann)))
    S = np.array(frames)
    flux = np.maximum(0, np.diff(S, axis=0)).sum(axis=1)
    flux = flux / (flux.max() + 1e-12)
    med = np.median(flux)
    mad = np.median(np.abs(flux - med)) + 1e-9
    thr = med + 6 * mad
    peaks = []
    for i in range(2, len(flux) - 2):
        if flux[i] > thr and flux[i] == flux[i - 2:i + 3].max():
            peaks.append(i / fps_env)
    print(f"\n=== {stem} ===")
    print(f"  duration {len(x)/SR:.2f}s   envelope fps={fps_env}  "
          f"dBFS med={np.median(db):.1f} p95={np.percentile(db,95):.1f} max={db.max():.1f}")
    print(f"  onset threshold={thr:.3f}  peaks={len(peaks)}  "
          f"peaks/s={len(peaks)/(len(x)/SR):.2f}")
    if len(peaks) > 2:
        ioi = np.diff(peaks)
        ioi = ioi[(ioi > 0.15) & (ioi < 3.0)]
        if len(ioi):
            print(f"  IOI med={np.median(ioi)*1000:.0f}ms  "
                  f"IQR={np.percentile(ioi,25)*1000:.0f}-{np.percentile(ioi,75)*1000:.0f}ms  "
                  f"implied BPM={60/np.median(ioi):.1f}")
    print("  first 25 onsets (s): " + ", ".join(f"{p:.2f}" for p in peaks[:25]))
    # loudest moments (drops)
    k = np.argsort(db)[-8:][::-1]
    print("  loudest envelope frames (s): " + ", ".join(f"{i/fps_env:.2f}({db[i]:.1f}dB)" for i in sorted(k)))
    return peaks, db


if __name__ == "__main__":
    for s in ("BV1ue8y6XE2M", "BV1qx5463Exr", "BV1o94y1a76h"):
        analyse(s)
