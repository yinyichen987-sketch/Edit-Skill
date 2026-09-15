"""击杀音效的音频瞬态判据 —— 第 10 轮（本机现在有原始素材了）。

## 为什么重做

第 9 轮只能用入库的**音频摘要**（`analysis2/raw/audio_*.json`：峰表 + 250ms 窗），
结论是「凭摘要做不起来，但摘要回答不了『音频里到底有没有击杀音效』」，
并把「原始波形」列为必须补的输入。

**第 10 轮素材到手**（11 条 mp4，全部 1280x720@30fps + AAC 48kHz 立体声），
所以本工具直接**解码原始音轨**，把第 9 轮做不了的那部分补上。

## 与入库摘要的关键差别（本轮实测口径）

| 项 | 入库摘要（第 9 轮） | 本工具（第 10 轮） |
|---|---|---|
| 输入 | 别人算好的 `peaks_flux` / `windows_250ms` | **原始 PCM**（ffmpeg 解 mono 48kHz） |
| STFT 窗 / 步长 | 未知（推测 21.33ms / 10ms） | 窗 1024（21.33ms = 恰好 1 帧@30fps）/ 步 480（10ms） |
| 出峰抑制 | **固定 200ms 最小距离**（第 9 轮量出来的） | 可调（默认 100ms），并给出**未抑制的**完整 flux 曲线 |
| 全片曲线 | 没有（只有 250ms 摘要） | **有**（10ms 一条，落盘到 JSON） |

## 用法

    .venv\\Scripts\\python.exe projects/game-001/tools/audio_kill_signal.py b61cc53d
    .venv\\Scripts\\python.exe projects/game-001/tools/audio_kill_signal.py b61cc53d --spectrogram
    .venv\\Scripts\\python.exe projects/game-001/tools/audio_kill_signal.py all --spectrogram

输出：
    projects/game-001/verification/audio-signal/<short>_onsets.json   全片 flux/onset 与候选对比
    projects/game-001/verification/audio-signal/<short>_spec.png      声谱图（叠候选/已知负例竖线）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
A2 = ROOT / "projects" / "game-001" / "analysis2"
OUTDIR = ROOT / "projects" / "game-001" / "verification" / "audio-signal"

SR = 48000          # 解码采样率（与素材一致）
N_FFT = 1024        # 21.33ms 窗 = 恰好 1 帧 @30fps
HOP = 480           # 10ms
FPS = 30.0


def pooled_lag_scan(cand_map, pct=95, tol=0.05, max_lag=0.60, n_sim=2000, seed=13):
    """跨素材扫「固定滞后」：音频比视频候选**早/晚**多少？

    这是第 9 轮那条经验的严格版：**不能只看某个滞后的命中数**，
    必须把「在所有滞后里挑最大」这个挑选偏差也纳入零假设 ——
    所以这里对每个模拟同时算 121 个滞后并取最大值，得到 max-statistic 的零分布。
    """
    rng = np.random.default_rng(seed)
    prepared = []
    for f in sorted(OUTDIR.glob("*_series.json")):
        short = f.name.split("_")[0]
        cand = cand_map.get(short) or []
        if not cand:
            continue
        s = json.loads(f.read_text(encoding="utf-8"))
        flux = np.asarray(s["flux"], dtype=float)
        times = np.arange(len(flux)) * (s["hop_ms"] / 1000.0)
        keep, _ = strong_transients(flux, times, pct)
        prepared.append((times[keep], np.asarray(cand, dtype=float), float(times[-1] + 0.01)))
    lags = np.round(np.arange(-max_lag, max_lag + 1e-9, 0.01), 3)

    def curve(shifted):
        return np.array([sum(count_matches(tt, cs + lag, tol) for tt, cs, _ in shifted)
                         for lag in lags])

    obs = curve(prepared)
    best_i = int(np.argmax(obs))
    max_null = np.empty(n_sim, dtype=int)
    for k in range(n_sim):
        shifted = [(tt, (cs + rng.uniform(0, dur)) % dur, dur) for tt, cs, dur in prepared]
        max_null[k] = int(curve(shifted).max())
    return {
        "strength_pct": pct, "tol_s": tol, "max_lag_s": max_lag,
        "n_candidates": int(sum(len(cs) for _, cs, _ in prepared)),
        "best_lag_s": float(lags[best_i]), "best_matches": int(obs[best_i]),
        "matches_at_lag0": int(obs[len(lags) // 2]),
        "null_max_mean": float(max_null.mean()),
        "null_max_p95": float(np.percentile(max_null, 95)),
        "p_best_lag_maxstat": round(float((max_null >= obs[best_i]).sum() + 1) / (n_sim + 1), 5),
        "top5": [{"lag_s": float(lags[i]), "matches": int(obs[i])}
                 for i in np.argsort(-obs)[:5]],
        "curve": [{"lag_s": float(l), "matches": int(v)} for l, v in zip(lags, obs)],
    }


def count_matches(tt_sorted, cs, tol):
    """cs 里有多少个点落在「某个瞬态 ±tol」内（排序 + searchsorted，向量化）。"""
    lo = np.searchsorted(tt_sorted, cs - tol, side="left")
    hi = np.searchsorted(tt_sorted, cs + tol, side="right")
    return int((hi > lo).sum())


def pooled_test(cand_map, pcts=(95, 99), tols=(0.03, 0.05, 0.10, 0.25), n_sim=2000, seed=11):
    """跨 11 条素材汇总：音频强瞬态 vs `kills.json/kills` 候选（含已知误报）。

    每条素材有自己的瞬态密度 ⇒ 机会基线按素材各算各的再加权汇总；
    循环平移零假设也按素材各自独立平移（保留每条素材内候选的间距结构）。
    """
    rng = np.random.default_rng(seed)
    data = []
    for f in sorted(OUTDIR.glob("*_series.json")):
        short = f.name.split("_")[0]
        cand = cand_map.get(short) or []
        if not cand:
            continue
        s = json.loads(f.read_text(encoding="utf-8"))
        flux = np.asarray(s["flux"], dtype=float)
        times = np.arange(len(flux)) * (s["hop_ms"] / 1000.0)
        data.append((short, flux, times, np.asarray(cand, dtype=float)))
    rows = []
    for pct in pcts:
        prepared = []
        for short, flux, times, cand in data:
            keep, thr = strong_transients(flux, times, pct)
            tt = times[keep]
            dur = float(times[-1] + 0.01)
            prepared.append((short, tt, cand, dur))
        for tol in tols:
            obs = n = 0
            exp = 0.0
            per = []
            grid_cache = {}
            for short, tt, cand, dur in prepared:
                if short not in grid_cache:
                    grid = np.arange(0.0, dur, 0.001)
                    hit = np.zeros(len(grid), dtype=bool)
                    for x in tt:
                        hit |= np.abs(grid - x) <= tol
                    grid_cache[short] = float(hit.mean())
                p = grid_cache[short]
                o = count_matches(tt, cand, tol) if len(tt) else 0
                obs += o
                n += len(cand)
                exp += len(cand) * p
                per.append({"clip": short, "n_candidates": int(len(cand)),
                            "n_transients": int(len(tt)),
                            "observed": o, "chance_level": round(p, 4)})
            pbar = exp / n if n else 0.0
            sims = np.empty(n_sim, dtype=int)
            for k in range(n_sim):
                tot = 0
                for short, tt, cand, dur in prepared:
                    if not len(tt):
                        continue
                    cs = (cand + rng.uniform(0, dur)) % dur
                    tot += count_matches(tt, cs, tol)
                sims[k] = tot
            rows.append({
                "strength_pct": pct, "tol_s": tol, "tol_frames": round(tol * FPS, 2),
                "n_candidates": n, "observed_matches": obs,
                "expected_by_chance": round(exp, 2),
                "pooled_chance_level": round(pbar, 4),
                "hit_rate": round(obs / n, 4) if n else None,
                "binom_p_one_sided": round(binom_sf(obs, n, pbar), 6) if n else None,
                "shift_null_mean": round(float(sims.mean()), 3),
                "shift_null_p95": float(np.percentile(sims, 95)),
                "shift_null_p_one_sided": round(float((sims >= obs).sum() + 1) / (n_sim + 1), 5),
                "per_clip": per,
            })
    return rows


def strong_transients(flux, times, pct, min_gap_s=0.10, top_n=None):
    """取「强瞬态」：flux >= 全片第 pct 分位，且是局部极大，再做最小距离抑制。

    第 9 轮的教训是**密度决定一切**：峰太密时「±tol 内有峰」会退化成恒真命题。
    所以这里把「强度」和「密度」分开给：既能按分位卡强度，也能只取最强的前 N 个。
    """
    thr = float(np.percentile(flux, pct))
    ispeak = (flux >= thr) & (flux >= np.roll(flux, 1)) & (flux > np.roll(flux, -1))
    idx = np.where(ispeak)[0]
    keep = []
    for i in idx[np.argsort(-flux[idx])]:
        if all(abs(times[i] - times[j]) >= min_gap_s for j in keep):
            keep.append(int(i))
    keep.sort(key=lambda i: times[i])
    if top_n:
        keep = sorted(sorted(keep, key=lambda i: -flux[i])[:top_n], key=lambda i: times[i])
    return keep, thr


def significance_test(flux, times, candidates, fps=FPS, n_sim=2000, seed=7):
    """候选时刻 vs 音频强瞬态：**带零假设**的一致性检验。

    三个口径同时给，缺一个都不足以下结论：
      1. `chance_level`：一个随机时刻落进「某瞬态 ±tol」的概率（1ms 打点实测）
         —— 密度一高这个值就接近 1，命中也就不说明任何事；
      2. `binom_p`：把候选当独立抽样、用 chance_level 做的精确二项检验；
      3. `shift_null_p`：把全部候选**整体循环平移**一个随机量再数命中，
         重复 n_sim 次得到零分布 —— 这个保留候选之间的间距结构，
         是比前两个更可靠的参照（点过程的标准随机化检验）。
    """
    rng = np.random.default_rng(seed)
    dur = float(times[-1] + 0.01)
    rows = []
    cand = np.asarray(candidates, dtype=float)
    for pct, top_n in ((95, None), (99, None), (99.9, None), (95, 10), (95, 20)):
        keep, thr = strong_transients(flux, times, pct, top_n=top_n)
        tt = times[keep]
        if len(tt) == 0:
            continue
        for tol in (0.03, 0.05, 0.10, 0.25):
            grid = np.arange(0.0, dur, 0.001)
            # chance level：1ms 网格上落进任一瞬态 ±tol 的比例
            hit = np.zeros(len(grid), dtype=bool)
            for x in tt:
                hit |= np.abs(grid - x) <= tol
            p = float(hit.mean())
            obs = int(sum(1 for c in cand if np.min(np.abs(tt - c)) <= tol))
            n = len(cand)
            pval = binom_sf(obs, n, p) if n else None
            # 循环平移零分布
            sims = []
            for _ in range(n_sim):
                shift = rng.uniform(0, dur)
                cs = (cand + shift) % dur
                sims.append(sum(1 for c in cs if np.min(np.abs(tt - c)) <= tol))
            sims = np.asarray(sims)
            shift_p = float(((sims >= obs).sum() + 1) / (n_sim + 1))
            rows.append({
                "strength_pct": pct, "top_n": top_n, "n_transients": int(len(tt)),
                "transients_per_s": round(len(tt) / dur, 3),
                "flux_threshold": round(thr, 2),
                "tol_s": tol, "tol_frames": round(tol * fps, 2),
                "n_candidates": n, "observed_matches": obs,
                "chance_level": round(p, 4),
                "expected_by_chance": round(n * p, 2),
                "binom_p_one_sided": (round(pval, 5) if pval is not None else None),
                "shift_null_mean": round(float(sims.mean()), 3),
                "shift_null_p95": float(np.percentile(sims, 95)),
                "shift_null_p_one_sided": round(shift_p, 5),
            })
    return rows


def binom_sf(k, n, p):
    import math
    if k <= 0:
        return 1.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    return min(1.0, sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def decode_mono(path):
    cmd = [ffmpeg_exe(), "-v", "error", "-i", str(path), "-vn",
           "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def stft_features(x):
    """逐 10ms 的（RMS dB, 频谱通量 flux, 低频/中频/高频能量 dB）。"""
    win = np.hanning(N_FFT).astype(np.float32)
    n = 1 + max(0, (len(x) - N_FFT) // HOP)
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    frames = x[idx] * win
    spec = np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32)
    mag_db = 20.0 * np.log10(spec + 1e-6)
    # 半波整流谱通量（正的变化量之和），与「瞬态/起音」相关
    diff = np.diff(mag_db, axis=0, prepend=mag_db[:1])
    flux = np.maximum(diff, 0.0).sum(axis=1)
    rms_db = 20.0 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / SR)
    def band_db(lo, hi):
        m = (freqs >= lo) & (freqs < hi)
        e = (spec[:, m] ** 2).sum(axis=1)
        return 10.0 * np.log10(e + 1e-9)
    return {
        "times": (np.arange(n) * HOP / SR),
        "flux": flux,
        "rms_db": rms_db,
        "low_db": band_db(0, 300),
        "mid_db": band_db(300, 2000),
        "high_db": band_db(2000, 16000),
    }


def detect_onsets(f, k=6.0, min_gap_s=0.10, win_s=0.5):
    """自适应门限出峰：门限 = 局部中位 + k×(1.4826×MAD)，再做最小距离抑制。"""
    flux = f["flux"]
    n = len(flux)
    half = max(1, int(win_s * SR / HOP / 2))
    med = np.empty(n)
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        med[i] = np.median(flux[lo:hi])
    mad = np.median(np.abs(flux - np.median(flux))) * 1.4826
    thr = med + k * mad
    cand = np.where((flux > thr) & (flux >= np.roll(flux, 1)) & (flux > np.roll(flux, -1)))[0]
    keep, last = [], -1e9
    order = cand[np.argsort(-flux[cand])]
    for i in order:
        t = f["times"][i]
        if all(abs(t - f["times"][j]) >= min_gap_s for j in keep):
            keep.append(i)
    keep.sort()
    onsets = [{
        "t_s": round(float(f["times"][i]), 4),
        "frame30": round(float(f["times"][i]) * FPS, 2),
        "flux": round(float(flux[i]), 3),
        "rms_db": round(float(f["rms_db"][i]), 2),
        "high_db": round(float(f["high_db"][i]), 2),
        "prominence": round(float(flux[i] - thr[i]), 3),
    } for i in keep]
    return onsets, thr, mad


def load_candidates(short):
    """候选来源：groundtruth（仅 b61cc53d）与旧检测器，均标注来源与可信度。"""
    out = []
    gt = A2 / "kills_groundtruth.json"
    if gt.exists():
        d = json.loads(gt.read_text(encoding="utf-8"))
        if pathlib.Path(d["source"]).stem[:8] == short:
            for e in d["events"]:
                out.append({"t_s": e["kill_time_candidate_s"], "src": "kills_groundtruth(未人工确认)",
                            "confidence": e.get("confidence")})
            for t in (d.get("comparison_with_old_detector") or {}).get("old_false_positives_s") or []:
                out.append({"t_s": t, "src": "已知负例(人工确认非击杀)", "confidence": "human-negative"})
    km = A2 / "kills_mine.json"
    if km.exists():
        d = json.loads(km.read_text(encoding="utf-8"))
        for t in (d.get(short) or {}).get("topright_edges") or []:
            if not any(abs(t - o["t_s"]) < 1e-6 for o in out):
                out.append({"t_s": t, "src": "kills_mine/topright_edges(旧检测器)",
                            "confidence": "legacy-candidate"})
    return sorted(out, key=lambda o: o["t_s"])


def nearest(ts, t):
    if not len(ts):
        return None
    a = np.asarray(ts)
    i = int(np.argmin(np.abs(a - t)))
    return float(a[i])


def analyse(short, k, min_gap, want_spec):
    path = SRC / f"{short}"
    cands = [p for p in SRC.glob(f"{short}*.mp4")]
    if not cands:
        print(f"[FAIL] 找不到素材 {short}*.mp4")
        return None
    src = cands[0]
    x = decode_mono(src)
    f = stft_features(x)
    onsets, thr, mad = detect_onsets(f, k=k, min_gap_s=min_gap)
    times = f["times"]
    rows = []
    for c in load_candidates(short):
        t = c["t_s"]
        near = nearest(times, t)
        i = None if near is None else int(np.argmin(np.abs(times - t)))
        on = [o for o in onsets if abs(o["t_s"] - t) <= 0.25]
        on_05 = [o for o in onsets if abs(o["t_s"] - t) <= 0.05]
        # 局部峰（不做出峰抑制）
        lo = max(0, i - 5); hi = min(len(times), i + 6)
        loc = float(f["flux"][lo:hi].max()) if i is not None else None
        rows.append({
            **c,
            "flux_at_t": round(float(f["flux"][i]), 3) if i is not None else None,
            "flux_local_max_pm50ms": round(loc, 3) if loc is not None else None,
            "rms_db_at_t": round(float(f["rms_db"][i]), 2) if i is not None else None,
            "onsets_within_250ms": [o["t_s"] for o in on],
            "onsets_within_50ms": [o["t_s"] for o in on_05],
            "nearest_onset": (min((o["t_s"] for o in onsets), key=lambda s: abs(s - t)) if onsets else None),
        })
    res = {
        "short": short,
        "file": src.name,
        "duration_s": round(len(x) / SR, 4),
        "sample_rate": SR, "n_fft": N_FFT, "hop_ms": round(1000 * HOP / SR, 3),
        "evidence_level": "L1（本机解码原始音轨实测）",
        "detector": {"adaptive_k": k, "min_gap_s": min_gap, "mad": round(float(mad), 4),
                     "n_onsets": len(onsets), "onsets_per_s": round(len(onsets) / (len(x) / SR), 3)},
        "onsets": onsets,
        "candidates": rows,
    }
    gt_times = [c["t_s"] for c in rows if c["src"].startswith("kills_groundtruth")]
    if gt_times:
        sig = significance_test(f["flux"], f["times"], gt_times, n_sim=2000)
        res["significance_vs_groundtruth_candidates"] = {
            "note": "候选=第 7 轮的未确认候选（confidence=medium）；三个口径都必须看",
            "n_candidates": len(gt_times),
            "candidate_times_s": gt_times,
            "rows": sig,
        }
        print("  == 显著性检验（%d 个未确认候选 vs 音频强瞬态）==" % len(gt_times))
        print("  %5s %5s %5s %6s %6s %7s %7s %8s %8s %8s" % (
            "分位", "topN", "瞬态数", "容差", "±帧", "预期", "实测", "二项p", "平移p", "平移均值"))
        for r in sig:
            print("  %5s %5s %6d %6.2f %6.1f %7.2f %7d %8s %8s %8s" % (
                r["strength_pct"], r["top_n"] or "-", r["n_transients"], r["tol_s"], r["tol_frames"],
                r["expected_by_chance"], r["observed_matches"], r["binom_p_one_sided"],
                r["shift_null_p_one_sided"], r["shift_null_mean"]))
    OUTDIR.mkdir(parents=True, exist_ok=True)
    dst = OUTDIR / f"{short}_onsets.json"
    series = {
        "hop_ms": 10,
        "flux": [round(float(v), 3) for v in f["flux"]],
        "rms_db": [round(float(v), 2) for v in f["rms_db"]],
    }
    (OUTDIR / f"{short}_series.json").write_text(
        json.dumps(series, ensure_ascii=False), encoding="utf-8", newline="\n")
    dst.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"[OK] {dst.relative_to(ROOT)}  （{len(onsets)} 个 onset，"
          f"{len(onsets)/(len(x)/SR):.2f} 个/秒）")
    if want_spec:
        draw_spectrogram(short, x, f)
    return res


def draw_spectrogram(short, x, f):
    from PIL import Image, ImageDraw
    win = np.hanning(N_FFT).astype(np.float32)
    n = 1 + max(0, (len(x) - N_FFT) // HOP)
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    mag = np.abs(np.fft.rfft(x[idx] * win, axis=1)).astype(np.float32)
    db = 20.0 * np.log10(mag + 1e-6)
    db = db[:, :400]                      # 0~18.75kHz，取前 400 个 bin（约 0~9.4kHz）
    lo, hi = np.percentile(db, 5), np.percentile(db, 99.5)
    img = np.clip((db - lo) / max(1e-6, hi - lo), 0, 1)
    img = (img * 255).astype(np.uint8)
    img = img[:, ::-1]                    # 低频在上
    im = Image.fromarray(img, mode="L").resize((max(600, n // 2), 320), Image.BILINEAR).convert("RGB")
    d = ImageDraw.Draw(im)
    W, H = im.size
    dur = len(x) / SR
    def xat(t):
        return int(round(W * t / dur))
    for c in load_candidates(short):
        t = c["t_s"]
        col = (255, 60, 60) if "负例" in c["src"] else (60, 200, 255)
        if c["src"].startswith("kills_mine"):
            col = (255, 220, 0)
        d.line([(xat(t), 0), (xat(t), H)], fill=col, width=1)
    out = OUTDIR / f"{short}_spec.png"
    im.save(out)
    print(f"[OK] {out.relative_to(ROOT)}  竖线=红:已知非击杀  青:groundtruth候选  黄:旧检测器候选")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("short", help="素材短 id（8 位）或 all")
    ap.add_argument("--k", type=float, default=6.0, help="自适应门限的 MAD 倍数")
    ap.add_argument("--min-gap", type=float, default=0.10)
    ap.add_argument("--spectrogram", action="store_true")
    ap.add_argument("--pooled", action="store_true",
                    help="跨 11 条素材汇总检验（候选取 kills.json/kills）")
    args = ap.parse_args()

    if args.pooled:
        km = A2 / "kills.json"
        cand_map = json.loads(km.read_text(encoding="utf-8"))
        cand_map = {k: (v.get("kills") or []) for k, v in cand_map.items()}
        rows = pooled_test(cand_map)
        out = {
            "generated_by": "projects/game-001/tools/audio_kill_signal.py --pooled",
            "evidence_level": "L1（本机解码原始音轨；候选来自仓库内 kills.json，含已知误报）",
            "label_note": "候选是旧检测器的，不是人工真值 ⇒ 本检验只能说明「音频与视频候选对不对齐」，不能当准确率",
            "rows": rows,
        }
        dst = OUTDIR / "pooled-test.json"
        print("== 固定滞后扫描（含「挑最大值」偏差的零分布）==")
        lag_rows = []
        for pct in (95, 99):
            lr = pooled_lag_scan(cand_map, pct=pct, tol=0.05)
            lag_rows.append(lr)
            print("  分位 %s ±0.05s：lag=0 命中 %d；最佳 lag=%+.2fs 命中 %d；"
                  "零分布 max 均值 %.1f / p95 %.1f ⇒ p=%s" % (
                      pct, lr["matches_at_lag0"], lr["best_lag_s"], lr["best_matches"],
                      lr["null_max_mean"], lr["null_max_p95"], lr["p_best_lag_maxstat"]))
            print("     前 5：%s" % ", ".join("lag=%+.2fs→%d" % (t["lag_s"], t["matches"]) for t in lr["top5"]))
        out["lag_scan"] = lag_rows
        dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        print("== 跨 11 条素材汇总（音频强瞬态 vs kills.json 候选 %d 个）==" % rows[0]["n_candidates"])
        print("%5s %6s %6s %8s %8s %8s %9s %9s %9s" % (
            "分位", "容差", "±帧", "标签数", "预期", "实测", "命中率", "二项p", "平移p"))
        for r in rows:
            print("%5s %6.2f %6.1f %8d %8.2f %8d %9s %9s %9s" % (
                r["strength_pct"], r["tol_s"], r["tol_frames"], r["n_candidates"],
                r["expected_by_chance"], r["observed_matches"], r["hit_rate"],
                r["binom_p_one_sided"], r["shift_null_p_one_sided"]))
        print("[OK] %s" % dst.relative_to(ROOT))
        return 0

    shorts = ([p.name[:8] for p in sorted(SRC.glob("*.mp4"))]
              if args.short == "all" else [args.short])
    for s in shorts:
        analyse(s, args.k, args.min_gap, args.spectrogram)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
