"""合成一条**与剪切点同格**的电子 BGM（128 BPM，刚好 15.000 s = 32 拍 = 8 小节）。

## 为什么自己做而不是找现成曲子

用户要「卡点集锦」。卡点的前提是**剪切点落在音乐节拍上**，而现成曲子的
BPM/相位未知，要先对齐再切；自己合成则**先把拍子钉死**，剪切点直接按拍号排。

选 128 BPM 的理由是算术干净：

    1 拍 = 60/128 = 0.46875 s
    1 小节 = 4 拍 = 1.875 s
    15.000 s / 0.46875 = **32 拍整 = 8 小节整**

即 15 秒的片子**天然是 8 小节**，每个剪切点都能落在拍上，不需要变速凑整。

## 音乐设计（A 小调，电竞四踩底鼓）

    小节 1-2  Am    小节 3-4  F     小节 5-6  C     小节 7-8  G
    底鼓：每拍（四踩）        拍手：每小节 2、4 拍
    闭镲：八分（后四小节加密到十六分，做推进）
    贝斯：八分切分，跟和弦根音
    铺底：第 3 小节后半起做 riser，第 5 小节落 crash + 低频冲击（"drop"）
    琶音：第 5-8 小节加一层十六分琶音，抬高后半段

## 用法

    .venv\\Scripts\\python.exe projects\\game-001\\tools\\make_bgm.py
输出：projects/game-001/bgm/bgm_128_15s.wav
      projects/game-001/bgm/beat-grid.json   （剪切点对齐用）

**换曲须知**：想换成剪映曲库里的热门曲（会员可用）时，只要新曲的 BPM 相近，
把 `beat-grid.json` 里的拍点按新 BPM 重算即可；`edl_to_draft.py` 不关心 BGM 内容，
只按 EDL 的时间码摆位置。
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "projects" / "game-001" / "bgm"

SR = 48000
BPM = 128.0
BEAT = 60.0 / BPM              # 0.46875 s
BAR = 4 * BEAT                 # 1.875 s
BARS = 8
DURATION = BARS * BAR          # 15.0 s
N = int(round(DURATION * SR))

# 和弦根音（Hz）：Am / F / C / G，每个和弦占 2 小节
CHORDS = [
    ("Am", [220.00, 261.63, 329.63]),   # A3 C4 E4
    ("F",  [174.61, 220.00, 261.63]),   # F3 A3 C4
    ("C",  [196.00, 261.63, 329.63]),   # G3 C4 E4
    ("G",  [196.00, 246.94, 293.66]),   # G3 B3 D4
]
ROOTS = {"Am": 110.00, "F": 87.31, "C": 130.81, "G": 98.00}
# 低八度根音（贝斯）
BASS = {"Am": 55.00, "F": 43.65, "C": 65.41, "G": 49.00}


def chord_at(bar: int) -> str:
    return CHORDS[min(bar, BARS - 1) // 2][0]


# --------------------------------------------------------------------------
# 滤波（无 scipy，用 rfft + 余弦边缘掩码；砖墙掩码会有振铃，故两端做渐变）
# --------------------------------------------------------------------------
def _mask(x: np.ndarray, lo: float, hi: float, soft: float = 0.35) -> np.ndarray:
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    m = np.ones_like(f)
    if lo > 0:
        m *= np.clip((f - lo * (1 - soft)) / (lo * soft + 1e-9), 0.0, 1.0)
    if hi < SR / 2:
        m *= np.clip((hi * (1 + soft) - f) / (hi * soft + 1e-9), 0.0, 1.0)
    return np.fft.irfft(X * m, len(x))


def highpass(x, f0, soft=0.35):
    return _mask(x, f0, SR / 2 + 1, soft)


def bandpass(x, f0, f1, soft=0.35):
    return _mask(x, f0, f1, soft)


def lowpass(x, f0, soft=0.35):
    return _mask(x, 0.0, f0, soft)


# --------------------------------------------------------------------------
# 音色
# --------------------------------------------------------------------------
def add(buf: np.ndarray, t0: float, sig: np.ndarray, gain: float = 1.0) -> None:
    i = int(round(t0 * SR))
    if i >= len(buf):
        return
    seg = sig[: len(buf) - i]
    buf[i:i + len(seg)] += gain * seg


def env_exp(n: int, decay: float, attack: float = 0.002) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-6), 0.0, 1.0)
    return a * np.exp(-t / decay)


def kick() -> np.ndarray:
    n = int(0.34 * SR)
    t = np.arange(n) / SR
    f = 45.0 + 120.0 * np.exp(-t / 0.026)          # 音高快速下坠 = "砰"
    phase = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(phase) * env_exp(n, 0.085, 0.001)
    click = np.random.default_rng(1).normal(0, 1, n) * env_exp(n, 0.004, 0.0005) * 0.28
    return np.tanh((body + click) * 1.6) * 0.92


def clap() -> np.ndarray:
    n = int(0.22 * SR)
    rng = np.random.default_rng(2)
    noise = rng.normal(0, 1, n)
    out = np.zeros(n)
    # 拍手是几个错开 10ms 的短噪声簇
    for k, off in enumerate((0.0, 0.009, 0.018, 0.027)):
        i = int(off * SR)
        e = env_exp(n - i, 0.030, 0.0008) * (1.0 if k == 0 else 0.7)
        out[i:] += noise[: n - i] * e
    return bandpass(out, 900.0, 5200.0) * 0.5


def hat(open_: bool = False) -> np.ndarray:
    n = int((0.11 if open_ else 0.035) * SR)
    rng = np.random.default_rng(3)
    noise = rng.normal(0, 1, n)
    return highpass(noise, 7000.0) * env_exp(n, 0.030 if open_ else 0.008, 0.0004) * 0.22


def saw(freq: float, n: int) -> np.ndarray:
    t = np.arange(n) / SR
    ph = (freq * t) % 1.0
    return 2.0 * ph - 1.0


def bass_note(freq: float, dur: float) -> np.ndarray:
    n = int(dur * SR)
    body = 0.7 * saw(freq, n) + 0.5 * np.sin(2 * np.pi * freq * np.arange(n) / SR)
    body = lowpass(body, 200.0)
    return body * env_exp(n, dur * 0.55, 0.004) * 0.55


def square(freq: float, n: int) -> np.ndarray:
    t = np.arange(n) / SR
    return np.sign(np.sin(2 * np.pi * freq * t))


def riser(dur: float) -> np.ndarray:
    n = int(dur * SR)
    rng = np.random.default_rng(4)
    noise = rng.normal(0, 1, n)
    t = np.arange(n) / SR
    # 用扫描带通近似"上升噪声"：分段滤波后拼接，避免 scipy
    seg = 12
    out = np.zeros(n)
    for k in range(seg):
        a, b = k * n // seg, (k + 1) * n // seg
        f0 = 300.0 * (2.0 ** (4.0 * k / seg))
        out[a:b] = bandpass(noise[a:b], f0 * 0.7, f0 * 1.6)
    ramp = (t / max(t[-1], 1e-6)) ** 1.6
    return out * ramp * 0.17


def crash() -> np.ndarray:
    n = int(1.1 * SR)
    rng = np.random.default_rng(5)
    return highpass(rng.normal(0, 1, n), 4000.0) * env_exp(n, 0.36, 0.001) * 0.30


def sub_impact() -> np.ndarray:
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    f = 38.0 + 30.0 * np.exp(-t / 0.09)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.26, 0.002) * 0.7


# --------------------------------------------------------------------------
def build() -> tuple[np.ndarray, np.ndarray]:
    L = np.zeros(N)
    R = np.zeros(N)

    # ---- 节奏组 ----
    for bar in range(BARS):
        for beat in range(4):
            t0 = bar * BAR + beat * BEAT
            k = kick()
            add(L, t0, k, 0.98)
            add(R, t0, k, 0.98)
            if beat in (1, 3):                       # 拍手落在 2、4 拍
                c = clap()
                add(L, t0, c, 0.9)
                add(R, t0, c, 0.9)
        # 闭镲：前四小节八分，后四小节十六分（推进感）
        div = 2 if bar < 4 else 4
        for s in range(4 * div):
            t0 = bar * BAR + s * BEAT / div
            h = hat(open_=(s % 4 == 3 and bar >= 4))
            pan = 0.5 + 0.25 * (1 if s % 2 else -1)
            add(L, t0, h, 1.4 * (1 - pan))
            add(R, t0, h, 1.4 * pan)

    # ---- 贝斯：八分切分 ----
    for bar in range(BARS):
        r = BASS[chord_at(bar)]
        for s, (off, dur, oct_) in enumerate((
                (0.0, 0.5, 1.0), (0.5, 0.25, 1.0), (1.0, 0.5, 1.0),
                (1.5, 0.5, 2.0), (2.5, 0.5, 1.0), (3.0, 0.5, 1.0), (3.5, 0.5, 1.5))):
            if bar < 2 and s > 4:
                continue                              # 前两小节留白，别一上来就满
            add(L, bar * BAR + off * BEAT, bass_note(r * oct_, dur * BEAT), 1.0)
            add(R, bar * BAR + off * BEAT, bass_note(r * oct_, dur * BEAT), 1.0)

    # ---- 琶音：第 5-8 小节 ----
    for bar in range(4, BARS):
        notes = CHORDS[bar // 2][1]
        for s in range(16):
            t0 = bar * BAR + s * BEAT / 4
            f = notes[s % len(notes)] * (2.0 if s >= 8 else 1.0)
            n = int(0.16 * BEAT * SR)
            sig = square(f, n) * env_exp(n, 0.05, 0.002) * 0.16
            pan = 0.5 + 0.35 * (1 if s % 2 else -1)
            add(L, t0, lowpass(sig, 4200.0), 1.0 * pan * 2)
            add(R, t0, lowpass(sig, 4200.0), 1.0 * (1 - pan) * 2)

    # ---- 过渡与重音 ----
    add(L, 2 * BAR, riser(BAR), 1.0)                  # 第 3 小节起 riser
    add(R, 2 * BAR, riser(BAR), 1.0)
    for t0 in (4 * BAR, 6 * BAR):                     # 第 5、7 小节落 crash
        c = crash()
        add(L, t0, c, 0.9)
        add(R, t0, c, 0.9)
    si = sub_impact()                                 # 第 5 小节低频冲击
    add(L, 4 * BAR, si, 1.0)
    add(R, 4 * BAR, si, 1.0)

    # ---- 总线：软削 + 收尾淡出（避免硬切尾巴）----
    def finish(x: np.ndarray) -> np.ndarray:
        fade = int(0.12 * SR)
        x[-fade:] *= np.linspace(1.0, 0.0, fade)
        x[: int(0.01 * SR)] *= np.linspace(0.0, 1.0, int(0.01 * SR))
        x = np.tanh(x * 1.15)
        peak = float(np.max(np.abs(x))) or 1.0
        return x / peak * 0.70                        # 留 ~3 dB 余量给后续混音

    return finish(L), finish(R)


def write_wav(path: Path, L: np.ndarray, R: np.ndarray) -> None:
    data = np.stack([L, R], axis=1)
    pcm = np.clip(data, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main() -> int:
    print(f"=== 合成 BGM：{BPM:.0f} BPM / {BARS} 小节 / {DURATION:.3f} s ===")
    print(f"    1 拍 = {BEAT:.5f} s   1 小节 = {BAR:.4f} s   "
          f"{DURATION:.3f} / {BEAT:.5f} = {DURATION/BEAT:.1f} 拍")
    L, R = build()
    out = OUT_DIR / "bgm_128_15s.wav"
    write_wav(out, L, R)
    peak_db = 20 * np.log10(max(float(np.max(np.abs(L))), 1e-9))
    print(f"[OK] 已写出 {out.relative_to(ROOT)}  "
          f"({out.stat().st_size/1024:.0f} KB, 峰值 {peak_db:.1f} dBFS)")

    grid = {
        "bpm": BPM,
        "beat_s": BEAT,
        "bar_s": BAR,
        "bars": BARS,
        "duration_s": DURATION,
        "beats": [round(i * BEAT, 6) for i in range(int(DURATION / BEAT) + 1)],
        "downbeats": [round(b * BAR, 6) for b in range(BARS + 1)],
        "chords_per_2bars": [c[0] for c in CHORDS],
        "note": ("剪切点应落在 beats 上；重音（crash / drop）在 "
                 "downbeats[4]=7.5s 与 downbeats[6]=11.25s。"),
    }
    gp = OUT_DIR / "beat-grid.json"
    gp.write_text(json.dumps(grid, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 已写出 {gp.relative_to(ROOT)}（拍点表，供剪切点对齐）")
    print(f"     拍点: {grid['beats'][:8]} ...")
    print(f"     重音: 7.500s（drop）、11.250s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
