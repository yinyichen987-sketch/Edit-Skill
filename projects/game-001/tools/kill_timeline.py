"""逐帧量「击杀横幅 / 右上播报 / 顶部敌人头像 / 击杀音效」的相对时序（L1 本机实测）。

为什么需要它：`kill-extraction.md` 只标定了「横幅在哪」（y522~613），
但**没有任何一条带绝对时刻的击杀台账**。本工具不判断"哪一帧是击杀"，
它只输出**可目视核对的候选时刻 + 各 HUD 通道的上升沿**，
用来回答「播报相对横幅/音效滞后多少」。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\kill_timeline.py b61cc53d --t0 4 --t1 20
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\kill_timeline.py b61cc53d --t0 13.5 --t1 16.5

输出：projects/game-001/verification/kill_timeline/<short>.json 与控制台摘要。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

import imageio_ffmpeg
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
OUT = ROOT / "projects" / "game-001" / "verification" / "kill_timeline"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

W, H = 1280, 720

# 区域标定（1280x720）。横幅来自 kill-extraction.md §1 的逐像素实测；
# 其余三条是**本工具自己按 HUD 位置定的采样区**，注释里写明依据。
REGIONS = {
    # 实测 y522~613，横向 x380~900 → 这里取整条带避免裁掉描边
    "banner": (520, 620, 300, 980),
    # 右上 killfeed：kill-extraction.md §1 说右上带 y18~76 x950~1270（那里没有横幅像素）
    "feed_tr": (10, 90, 930, 1275),
    # 顶部中间敌人头像条（/leaderboard 或顶栏头像）—— 位置按画面观察，未逐像素标定
    "top_mid": (0, 46, 400, 880),
    # 底部 HUD：经济/技能/弹匣（旧 legacy 带子 y600 起）—— 用来验证"会不会被误当击杀"
    "bottom_hud": (620, 720, 0, 1280),
}


def decode_video(short: str, t0: float, t1: float):
    """返回 (frames float32 [N,H,W,3], t0)。"""
    src = next(SRC.glob(f"{short}*.mp4"))
    cmd = [
        FFMPEG, "-v", "error",
        "-ss", f"{t0:.4f}", "-i", str(src), "-t", f"{t1 - t0:.4f}",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype=np.uint8)
    n = a.size // (W * H * 3)
    a = a[: n * W * H * 3].reshape(n, H, W, 3)
    return a.astype(np.float32), t0


def decode_audio(short: str, t0: float, t1: float, sr: int = 16000):
    """单声道 PCM，返回 (samples float32, sr)。"""
    src = next(SRC.glob(f"{short}*.mp4"))
    cmd = [
        FFMPEG, "-v", "error",
        "-ss", f"{t0:.4f}", "-i", str(src), "-t", f"{t1 - t0:.4f}",
        "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-",
    ]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32), sr


def region_stats(frames: np.ndarray) -> dict:
    y0, y1, x0, x1 = 0, 0, 0, 0
    out = {}
    for name, (y0, y1, x0, x1) in REGIONS.items():
        sub = frames[:, y0:y1, x0:x1, :]
        out[name] = sub
    return out


def magenta_score(sub: np.ndarray) -> np.ndarray:
    """洋红/紫色描边代理：R 与 B 都明显高于 G。"""
    r, g, b = sub[..., 0], sub[..., 1], sub[..., 2]
    mask = (r - g > 30) & (b - g > 30)
    return mask.mean(axis=(1, 2))


def sat_score(sub: np.ndarray) -> np.ndarray:
    """饱和度均值 mean(max-min)：用于头像条"存活(彩色)/阵亡(灰)"的分离。"""
    return (sub.max(axis=3) - sub.min(axis=3)).mean(axis=(1, 2))


def changed_pixels(sub: np.ndarray) -> np.ndarray:
    d = np.abs(np.diff(sub, axis=0)).max(axis=3)  # [N-1,h,w]
    return (d > 28).mean(axis=(1, 2))


def audio_onsets(samples: np.ndarray, sr: int, hop_ms: float = 5.0, win_ms: float = 20.0):
    hop = int(sr * hop_ms / 1000)
    win = int(sr * win_ms / 1000)
    n = max(1, (len(samples) - win) // hop)
    e = np.empty(n, dtype=np.float64)
    for i in range(n):
        seg = samples[i * hop: i * hop + win]
        e[i] = float(np.sqrt(np.mean(seg.astype(np.float64) ** 2)))
    t = (np.arange(n) * hop) / sr
    # 半波整流的一阶差分 = 起音强度（attack）
    d = np.diff(e, prepend=e[0])
    return t, e, np.maximum(d, 0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=None)
    a = ap.parse_args()

    src_mp4 = next(SRC.glob(f"{a.short}*.mp4"))
    import imageio.v3 as iio
    meta = iio.immeta(src_mp4, plugin="pyav") if False else None  # 不用 pyav，直接 ffprobe
    # 时长/帧率
    p = subprocess.run([FFMPEG, "-v", "error", "-i", str(src_mp4), "-f", "null", "-"],
                       capture_output=True, text=True)
    dur = None
    for line in p.stderr.splitlines():
        if "time=" in line:
            dur = line
    t1 = a.t1 if a.t1 is not None else 29.0

    frames, t0 = decode_video(a.short, a.t0, t1)
    n = frames.shape[0]
    fps = n / (t1 - a.t0)
    ts = t0 + np.arange(n) / 30.0
    print(f"[{a.short}] frames={n} 窗口={t1 - a.t0:.3f}s  推定fps={fps:.3f}")

    regs = region_stats(frames)
    stats = {
        "t": ts.tolist(),
        "banner_magenta": magenta_score(regs["banner"]).tolist(),
        "feed_magenta": magenta_score(regs["feed_tr"]).tolist(),
        "feed_change": np.concatenate([[0.0], changed_pixels(regs["feed_tr"])]).tolist(),
        "banner_change": np.concatenate([[0.0], changed_pixels(regs["banner"])]).tolist(),
        "top_mid_sat": sat_score(regs["top_mid"]).tolist(),
        "top_mid_change": np.concatenate([[0.0], changed_pixels(regs["top_mid"])]).tolist(),
        "bottom_hud_change": np.concatenate([[0.0], changed_pixels(regs["bottom_hud"])]).tolist(),
        "bottom_hud_magenta": magenta_score(regs["bottom_hud"]).tolist(),
    }

    samples, sr = decode_audio(a.short, a.t0, t1)
    at, ae, aon = audio_onsets(samples, sr)
    stats["audio_t"] = (at + a.t0).tolist()
    stats["audio_rms"] = ae.tolist()
    stats["audio_onset"] = aon.tolist()

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{a.short}_t{a.t0:.2f}-{t1:.2f}.json"
    dst.write_text(json.dumps(stats), encoding="utf-8")
    print(f"[OK] {dst.relative_to(ROOT)}")

    # 摘要：各通道的显著上升沿
    def edges(arr, thr):
        arr = np.asarray(arr)
        hot = arr > thr
        out = []
        for i in range(1, len(hot)):
            if hot[i] and not hot[i - 1]:
                out.append(round(float(ts[i]), 3))
        return out

    print("  横幅洋红>2%      :", edges(stats["banner_magenta"], 0.02))
    print("  右上feed变化>8%  :", edges(stats["feed_change"], 0.08))
    print("  中部横幅变化>8%  :", edges(stats["banner_change"], 0.08))
    print("  顶部头像条变化>8%:", edges(stats["top_mid_change"], 0.08))
    print("  底栏HUD变化>8%   :", edges(stats["bottom_hud_change"], 0.08))
    # 音频起音峰值（局部最大且 > 全局P95）
    on = np.asarray(stats["audio_onset"])
    thr = float(np.percentile(on, 99.0))
    peaks = [round(float(at[i] + a.t0), 3) for i in range(1, len(on) - 1)
             if on[i] > thr and on[i] >= on[i - 1] and on[i] > on[i + 1]]
    print(f"  音频起音 P99={thr:.4f} 峰值:", peaks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
