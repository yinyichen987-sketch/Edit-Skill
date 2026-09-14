"""合成 3 个转场/重音音效：whoosh（镜头移动）、riser（推进）、sub_drop（落点）。

## 为什么自己做

调研结论里音效是**一等公民**（whoosh/impact/riser/sparkle 是标准词汇表，且要求
"每个 payoff 至少一个 impact"）。但：

  · **剪映音效库无法程序化引用** —— `AudioSegment` 只收本地文件路径（已核实）。
  · 现成音效包有版权与来源不可控的问题。

而 whoosh/riser/sub-drop 都是**合成起来很直接**的东西（噪声 + 滤波 + 包络），
所以自己做，配合已有的从原素材裁出的枪声（`sfx/impact_*.wav`）。

## 产出

    sfx/whoosh.wav     0.35 s   带通噪声，频率从高扫到低 —— 给快速切镜镶边
    sfx/riser.wav      1.80 s   噪声带通扫频上行 + 音量渐强 —— 铺垫 drop
    sfx/sub_drop.wav   0.90 s   低频正弦下坠 + 短冲击 —— drop 落点

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\make_sfx.py
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "projects" / "game-001" / "sfx"
SR = 48000


def bandpass(x: np.ndarray, lo: float, hi: float, soft: float = 0.4) -> np.ndarray:
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    m = np.clip((f - lo * (1 - soft)) / (lo * soft + 1e-9), 0.0, 1.0) * \
        np.clip((hi * (1 + soft) - f) / (hi * soft + 1e-9), 0.0, 1.0)
    return np.fft.irfft(X * m, len(x))


def sweep_noise(dur: float, f_start: float, f_end: float, segs: int = 24,
                seed: int = 11) -> np.ndarray:
    """分段带通拼接近似扫频（无 scipy，故不用 IIR 扫频滤波器）。"""
    n = int(dur * SR)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, n)
    out = np.zeros(n)
    for k in range(segs):
        a, b = k * n // segs, (k + 1) * n // segs
        f = f_start * (f_end / f_start) ** (k / max(segs - 1, 1))
        out[a:b] = bandpass(noise[a:b], f / 1.5, f * 1.5)
    return out


def whoosh() -> np.ndarray:
    dur = 0.35
    n = int(dur * SR)
    x = sweep_noise(dur, 6000.0, 500.0)
    t = np.arange(n) / SR
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.4      # 中间最响
    x = x * env
    # 轻微立体声错位，听起来"从一侧扫过"
    return x


def riser() -> np.ndarray:
    dur = 1.8
    n = int(dur * SR)
    x = sweep_noise(dur, 300.0, 7000.0, segs=30, seed=12)
    t = np.arange(n) / SR
    x = x * (t / dur) ** 1.8                                  # 渐强
    # 末尾叠一层高频"嗖"
    tail = int(0.25 * SR)
    x[-tail:] += sweep_noise(0.25, 9000.0, 4000.0, segs=8, seed=13) * \
        np.linspace(0.0, 0.6, tail)
    return x


def sub_drop() -> np.ndarray:
    dur = 0.9
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 42.0 + 26.0 * np.exp(-t / 0.12)                       # 下坠
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.34)
    click = np.random.default_rng(14).normal(0, 1, n) * np.exp(-t / 0.006) * 0.35
    return np.tanh((tone + click) * 1.4)


def write(path: Path, x: np.ndarray) -> float:
    peak = float(np.max(np.abs(x))) or 1.0
    x = x / peak * 0.80                                       # 留 ~2 dB 余量
    pcm = np.stack([x, x], axis=1)
    pcm = (np.clip(pcm, -1, 1) * 32767.0).astype("<i2")
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return 20 * np.log10(float(np.max(np.abs(x))))


def main() -> int:
    print("=== 合成音效 ===")
    specs = [("whoosh.wav", whoosh(), 0.35, "快速切镜镶边"),
             ("riser.wav", riser(), 1.80, "drop 前铺垫"),
             ("sub_drop.wav", sub_drop(), 0.90, "drop 落点")]
    for name, sig, dur, why in specs:
        p = OUT / name
        peak = write(p, sig)
        print(f"  [OK] {name:14} {dur:>4.2f}s  峰值 {peak:5.1f} dBFS  "
              f"{p.stat().st_size/1024:5.0f} KB   {why}")
    print("\n已有（从原素材裁出，枪声即 impact）：impact_a.wav / impact_b.wav / win.wav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
