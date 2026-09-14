"""分析剪映曲库缓存里的 BGM 候选：时长、采样率、RMS 包络、段落能量、BPM 一致性。

## 为什么要分析"剪映曲库缓存"

剪映的曲库**不能程序化引用**（`AudioSegment` 只收本地文件，见 `references/environment.md`），
但用户在剪映面板里**试听/下载**过的曲子会落在本机：

```
%LOCALAPPDATA%\\JianyingPro\\User Data\\Cache\\music\\<hash>.mp3      ← 音频本体
%LOCALAPPDATA%\\JianyingPro\\User Data\\Cache\\music\\<hash>.beat     ← 剪映自己算的拍点+能量
```

`.beat` 是**剪映的第一方产物**（`time` / `value` 拍号 / `energy`），比任何第三方 BPM 估计都权威。
本工具把它们读出来，用于给"在剪映里推荐的曲子"选段与对齐切点。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\analyze_bgm_cache.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import imageio_ffmpeg
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

CACHE = pathlib.Path(os.path.expandvars(r"%LOCALAPPDATA%\JianyingPro\User Data\Cache\music"))
SR = 24000
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def decode(path: pathlib.Path) -> np.ndarray:
    """整曲解码成单声道 float32（-ac 1 -ar SR）。"""
    raw = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR),
         "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype="<f4")


def rms_db(x: np.ndarray) -> float:
    if x.size == 0:
        return float("-inf")
    return float(20 * np.log10(max(float(np.sqrt(np.mean(x ** 2))), 1e-9)))


def envelope(x: np.ndarray, win_s: float = 1.0) -> np.ndarray:
    w = int(win_s * SR)
    n = x.size // w
    return np.array([rms_db(x[i * w:(i + 1) * w]) for i in range(n)])


def main() -> int:
    # ⚠️ `.beat` 的文件名 hash **和 mp3 的文件名 hash 不是同一个**（实测：3 个 .beat 里只有
    #    0 个能按同名配到 mp3）。所以只能按**时长最近**配对：.beat 的最后一个拍点
    #    必定落在曲子结束前（`span <= duration`），取 `duration - span` 最小的那首。
    mp3s = sorted(CACHE.glob("*.mp3"))
    bfiles = sorted(CACHE.glob("*.beat"))
    cfg = json.loads((CACHE / "downLoadcfg").read_text(encoding="utf-8"))
    order = {e["path"]: i for i, e in enumerate(cfg["list"])}

    # 先量每首 mp3 的真实时长
    import pymediainfo
    durs: dict[pathlib.Path, float] = {}
    for m in mp3s:
        mi = pymediainfo.MediaInfo.parse(str(m))
        a = mi.audio_tracks[0]
        durs[m] = float(a.duration) / 1000.0

    spans: dict[pathlib.Path, float] = {}
    for b in bfiles:
        spans[b] = json.loads(b.read_text(encoding="utf-8"))["time"][-1] / 1000.0

    print(f"缓存目录：{CACHE}")
    print(f"mp3 {len(mp3s)} 首 / .beat {len(bfiles)} 份（按「时长 - 末拍点」最近配对）\n")

    pairs = []
    used: set[pathlib.Path] = set()
    for b, span in sorted(spans.items(), key=lambda kv: kv[1]):
        best = min((m for m in mp3s if m not in used), key=lambda m: abs(durs[m] - span))
        used.add(best)
        pairs.append((best, b, order.get(best.name, 99)))

    rows = []
    for mp3, bp, idx in sorted(pairs, key=lambda t: t[2]):
        beat = json.loads(bp.read_text(encoding="utf-8"))
        t_ms = beat["time"]
        x = decode(mp3)
        dur = x.size / SR
        env = envelope(x)
        beat_dt = np.diff(np.array(t_ms, dtype=float)) / 1000.0
        bpm = 60.0 / float(np.median(beat_dt)) if beat_dt.size else float("nan")
        head = rms_db(x[: int(6 * SR)])
        tail = rms_db(x[-int(6 * SR):])
        peak = float(np.max(np.abs(x))) or 1e-9
        rows.append(dict(
            mp3=mp3.name, beat=bp.name, order=idx, dur_s=round(dur, 3),
            beat_n=len(t_ms), beat_last_s=round(t_ms[-1] / 1000.0, 3),
            bpm_median=round(bpm, 2),
            beat_dt_cv=round(float(np.std(beat_dt) / np.mean(beat_dt)), 4),
            rms_db=round(rms_db(x), 2), peak_dbfs=round(20 * np.log10(peak), 2),
            head6_db=round(head, 2), tail6_db=round(tail, 2),
            env_q=list(np.round(np.percentile(env, [10, 50, 90]), 2)),
        ))

    for r in rows:
        print(f"[下载顺序 {r['order']}] {r['mp3']}  ←→  {r['beat']}")
        print(f"     时长 {r['dur_s']:7.3f}s | 拍点 {r['beat_n']:4d} 个，到 {r['beat_last_s']:.3f}s | "
              f"BPM≈{r['bpm_median']:.2f} (拍距 CV={r['beat_dt_cv']:.4f})")
        print(f"     整曲 RMS {r['rms_db']:.2f} dBFS | 峰值 {r['peak_dbfs']:.2f} dBFS | "
              f"首 6s {r['head6_db']:.2f} → 尾 6s {r['tail6_db']:.2f} dBFS | "
              f"1s 包络 P10/P50/P90 = {r['env_q']}")

    print("\n注：`.beat` 的 time 单位是毫秒；value 是拍号（1/2/3/4）。")
    print("    RMS 是解码后的相对值，不能当流媒体响度（LUFS）用；只用来比较段落强弱。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
