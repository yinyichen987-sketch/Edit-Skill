"""逐帧音频能量分析 —— 为高光定位提供音频侧证据。

思路：
    直接把音轨解码成 48kHz 单声道 s16 PCM，在 Python 里做分帧特征，
    这样时间轴和视觉帧一一对应，不依赖任何解析文本的脆弱正则。

特征（帧长 1024 @48k ≈ 21.3ms，帧移 480 @48k = 10ms 精确）：
    rms_db      整段 RMS（dBFS）
    band_db     2–8kHz 带能量 —— VALORANT 枪声/击杀音/技能音的主频带
    sub_db      80–300Hz 带能量 —— 脚步/爆炸低频，用于区分人声与枪声
    flux        频谱通量（相邻帧频谱差的 L2），对瞬态最敏感
    centroid    频谱质心（Hz），区分低频脚步声与高频枪声

用法：
    python audio_energy.py <video> -o out.json [--hop 480] [--frame 1024]
"""
from __future__ import annotations

import argparse
import cmath
import json
import math
import os
import struct
import subprocess
import sys

import imageio_ffmpeg

SR = 48000


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def decode_mono(path: str, sr: int = SR) -> list[float]:
    """解码为单声道 float 样本。"""
    cmd = [
        ffmpeg_exe(), "-hide_banner", "-nostats", "-v", "error",
        "-i", path,
        "-ac", "1", "-ar", str(sr), "-f", "s16le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace"))
    raw = proc.stdout
    n = len(raw) // 2
    vals = struct.unpack("<%dh" % n, raw[: n * 2])
    return [v / 32768.0 for v in vals]


def frame_features(samples: list[float], sr: int, frame: int, hop: int,
                   dft_bins: int = 128) -> list[dict]:
    """按帧算特征。DFT 只算 dft_bins 个频点以保证速度。"""
    import array

    window = [0.5 - 0.5 * math.cos(2 * math.pi * i / (frame - 1)) for i in range(frame)]
    # 频率网格：只均匀取前 1/4 的频点（0–12kHz 覆盖我们关心的全部内容）
    freqs = [k * sr / frame for k in range(dft_bins)]
    two_pi = 2 * math.pi
    n_frames = max(0, (len(samples) - frame) // hop + 1)

    out: list[dict] = []
    prev_mag: list[float] | None = None

    for fi in range(n_frames):
        off = fi * hop
        seg = samples[off: off + frame]
        if len(seg) < frame:
            break
        sw = [seg[i] * window[i] for i in range(frame)]

        rms = math.sqrt(sum(v * v for v in sw) / frame)
        rms_db = 20 * math.log10(rms) if rms > 1e-9 else -120.0

        mags = []
        for k in range(dft_bins):
            acc = 0j
            w = two_pi * k / frame
            for i in range(0, frame, 2):  # 每 2 点抽样，速度翻倍
                acc += sw[i] * cmath.exp(-1j * w * i)
            mags.append(abs(acc))

        ssum = sum(mags) or 1e-12
        centroid = sum(freqs[k] * mags[k] for k in range(dft_bins)) / ssum

        band = sum(mags[k] ** 2 for k in range(dft_bins)
                   if 2000.0 <= freqs[k] <= 8000.0)
        sub = sum(mags[k] ** 2 for k in range(dft_bins)
                  if 80.0 <= freqs[k] <= 300.0)
        band_db = 10 * math.log10(band / frame) if band > 1e-12 else -120.0
        sub_db = 10 * math.log10(sub / frame) if sub > 1e-12 else -120.0

        if prev_mag is None:
            flux = 0.0
        else:
            d = 0.0
            for k in range(dft_bins):
                diff = mags[k] - prev_mag[k]
                if diff > 0:
                    d += diff * diff
            flux = math.sqrt(d) / (ssum / dft_bins + 1e-12)
        prev_mag = mags

        out.append({
            "t": round(off / sr, 4),
            "rms_db": round(rms_db, 2),
            "band_db": round(band_db, 2),
            "sub_db": round(sub_db, 2),
            "flux": round(flux, 4),
            "centroid": round(centroid, 1),
        })
    return out


def integrate(frames: list[dict], window_s: float = 0.25) -> list[dict]:
    """把 10ms 帧聚合成 250ms 窗，便于和高光时间码对齐。"""
    if not frames:
        return []
    hop_s = frames[1]["t"] - frames[0]["t"] if len(frames) > 1 else 0.01
    per = max(1, int(round(window_s / hop_s)))
    out = []
    for i in range(0, len(frames), per):
        chunk = frames[i: i + per]
        if not chunk:
            continue
        out.append({
            "start": chunk[0]["t"],
            "end": round(chunk[-1]["t"] + hop_s, 4),
            "rms_db": round(max(c["rms_db"] for c in chunk), 2),
            "band_db": round(max(c["band_db"] for c in chunk), 2),
            "sub_db": round(max(c["sub_db"] for c in chunk), 2),
            "flux": round(max(c["flux"] for c in chunk), 4),
            "centroid": round(sum(c["centroid"] for c in chunk) / len(chunk), 1),
        })
    return out


def detect_peaks(frames: list[dict], key: str, time_key: str = "t",
                 min_gap: float = 0.35, rel_db: float = 6.0) -> list[dict]:
    """相对峰值检测：高于全局中位数 + rel_db 的局部极大值。"""
    if not frames:
        return []
    vals = sorted(f[key] for f in frames)
    median = vals[len(vals) // 2]
    peaks: list[dict] = []
    for i, f in enumerate(frames):
        v = f[key]
        if v < median + rel_db:
            continue
        prev_v = frames[i - 1][key] if i > 0 else v
        next_v = frames[i + 1][key] if i + 1 < len(frames) else v
        if v < prev_v or v < next_v:
            continue
        if peaks and f[time_key] - peaks[-1]["time"] < min_gap:
            if v > peaks[-1]["value"]:
                peaks[-1] = {"time": f[time_key], "value": v}
            continue
        peaks.append({"time": f[time_key], "value": v})
    return [{"time": p["time"], "value": p["value"], "key": key} for p in peaks]


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="逐帧音频能量分析")
    ap.add_argument("video")
    ap.add_argument("-o", "--output")
    ap.add_argument("--frame", type=int, default=1024)
    ap.add_argument("--hop", type=int, default=480)
    args = ap.parse_args()

    samples = decode_mono(args.video)
    frames = frame_features(samples, SR, args.frame, args.hop)
    windows = integrate(frames)

    rms_vals = sorted(f["rms_db"] for f in frames)
    band_vals = sorted(f["band_db"] for f in frames)
    result = {
        "source": os.path.abspath(args.video),
        "sample_rate": SR,
        "duration_s": round(len(samples) / SR, 4),
        "frame_ms": round(args.frame / SR * 1000, 2),
        "hop_ms": round(args.hop / SR * 1000, 2),
        "stats": {
            "rms_db_median": round(rms_vals[len(rms_vals) // 2], 2),
            "rms_db_p95": round(rms_vals[int(len(rms_vals) * 0.95)], 2),
            "band_db_median": round(band_vals[len(band_vals) // 2], 2),
            "band_db_p95": round(band_vals[int(len(band_vals) * 0.95)], 2),
        },
        "peaks_rms": detect_peaks(frames, "rms_db"),
        "peaks_band": detect_peaks(frames, "band_db"),
        "peaks_flux": detect_peaks(frames, "flux", rel_db=0.0, min_gap=0.2),
        "windows_250ms": windows,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"[OK] {args.output}  frames={len(frames)}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
