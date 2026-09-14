"""从剪映曲库缓存的曲子里**挑一段**、另存为工程内 BGM，并导出该段的**拍点表**。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\pick_bgm_segment.py ^
        --src "%LOCALAPPDATA%\\JianyingPro\\User Data\\Cache\\music\\4fdd1e59....mp3" ^
        --beat "%LOCALAPPDATA%\\JianyingPro\\User Data\\Cache\\music\\18f53e55....beat" ^
        --start 26.0 --dur 16.5 ^
        --out projects\\game-001\\bgm\\jy_4fdd1e59_26.0s.wav

## 为什么是"挑一段"而不是整曲
成片只有 16 秒左右，整曲 169 秒既浪费、又会在草稿里留一条超长音轨。

## 为什么起点要吸附到剪映自己的拍点
`AudioSegment` 只收本地文件 ⇒ **剪映曲库不能被程序引用**（`references/environment.md`）。
但用户在剪映面板里下载过的曲子会落在 `Cache\\music\\`，并且剪映**顺便算好了一份拍点**
（`<hash>.beat`：`time` 毫秒 + `value` 拍号 + `energy`）。
把取段起点吸附到这些拍点上，"切点落在拍上"就不需要我再估 BPM —— 拍点是剪映的一手产物。

## 输出
1. 48 kHz 立体声 16-bit WAV（**不做归一化/限幅**；成片响度是剪辑决策，别在这步偷偷改）
2. 同目录 `<同名>.beats.json`：段内拍点（相对段起点，秒），供 EDL 对齐切点
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import wave

import imageio_ffmpeg
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

SR = 48000
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def decode_stereo(path: pathlib.Path, start: float, dur: float) -> np.ndarray:
    raw = subprocess.run(
        [FFMPEG, "-v", "error", "-ss", f"{start:.4f}", "-t", f"{dur:.4f}", "-i", str(path),
         "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype="<f4").reshape(-1, 2)


def db(v: float) -> float:
    return 20 * float(np.log10(max(abs(v), 1e-9)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--beat", required=True)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--snap-tol", type=float, default=0.25,
                    help="起点吸附到拍点的容差（秒）；超过就不吸附，只告警")
    a = ap.parse_args()

    src, beat_p = pathlib.Path(a.src), pathlib.Path(a.beat)
    dst = pathlib.Path(a.out)
    for p in (src, beat_p):
        if not p.exists():
            print(f"[ERR] 找不到 {p}")
            return 2

    beat = json.loads(beat_p.read_text(encoding="utf-8"))
    times = np.array(beat["time"], dtype=float) / 1000.0
    values = np.array(beat.get("value") or [0] * len(times), dtype=int)

    # ---- 起点吸附到最近拍点 ----
    i0 = int(np.argmin(np.abs(times - a.start)))
    off = float(times[i0] - a.start)
    if abs(off) <= a.snap_tol:
        print(f"[snap] 起点 {a.start:.3f}s → 拍点 {times[i0]:.3f}s（移动 {off:+.3f}s）")
        start = float(times[i0])
    else:
        print(f"[warn] 最近拍点距请求起点 {off:+.3f}s > 容差 {a.snap_tol}s，不吸附")
        start = a.start

    x = decode_stereo(src, start, a.dur)
    actual = x.shape[0] / SR

    fade = int(0.25 * SR)
    peak_src = float(np.max(np.abs(x)))
    if x.shape[0] > fade:
        x = x.copy()
        x[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]

    pcm = np.clip(x, -1.0, 1.0)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((pcm * 32767.0).astype("<i2").tobytes())

    # ---- 段内拍点（相对段起点）----
    sel = (times >= start) & (times < start + actual + 1e-6)
    rel = np.round(times[sel] - start, 4)
    grid = {
        "source_mp3": src.name,
        "source_beat": beat_p.name,
        "segment_start_s": round(start, 4),
        "duration_s": round(actual, 4),
        "beats_rel_s": [float(v) for v in rel],
        "beat_numbers": [int(v) for v in values[sel]],
        "bar_starts_rel_s": [float(v) for v in rel[values[sel] == 1]],
        "note": ("拍点来自剪映自己的 .beat（第一方产物），不是本项目估计的 BPM。"
                 "切点应落在 beats_rel_s 上；bar_starts_rel_s 是每小节第 1 拍（value==1）。"),
    }
    gp = dst.with_suffix(".beats.json")
    gp.write_text(json.dumps(grid, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[OK] {dst}  {actual:.3f}s / {SR}Hz 立体声 16bit")
    print(f"     段内拍点 {len(rel)} 个；小节起点 {len(grid['bar_starts_rel_s'])} 个："
          f"{grid['bar_starts_rel_s'][:8]}")
    print(f"     源峰值 {db(peak_src):.2f} dBFS（>0 = 原曲母版已削波，非本步引入）"
          f" | 段 RMS {db(float(np.sqrt(np.mean(x ** 2)))):.2f} dBFS")
    print(f"[OK] {gp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
