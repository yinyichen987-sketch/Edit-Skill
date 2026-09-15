"""音频瞬态判据能不能用？—— 只读入库数据做的可行性预研（第 9 轮）。

## 背景

第 7 轮 §7-3 留了一条待办：「换不依赖 HUD 的信号：击杀音效的音频瞬态」。

本机**没有素材、没有剪映、没联网**，但有朋友前几轮入库的 11 个
`analysis2/raw/audio_*.json`。本工具只吃这些 JSON，回答一个很窄的问题：

> **就凭入库的这些音频摘要，音频瞬态判据做不做得起来？**

## 入库的音频数据是什么（先看口径，再看结论）

| 字段 | 内容 | 时间分辨率 |
|---|---|---|
| `peaks_flux` | 频谱通量局部极大值 `{time, value}` | `hop_ms=10`（0.01s） |
| `peaks_band` / `peaks_rms` | 带限能量 / RMS 的峰值 | 同上 |
| `windows_250ms` | 全片 250ms 窗摘要（rms / band / sub / flux / centroid） | **250ms（≈7.5 帧 @30fps）** |

两条硬约束（本轮从数据里量出来的，跑 `--check` 看表）：
1. `peaks_flux` 相邻时间**最小间隔恰好 0.2s** ⇒ 出峰前做了 200ms 最小距离抑制，
   **200ms 内的两次事件会被合并成一次**（上限 5 个/秒）。
2. 250ms 窗摘要的量化误差是 **±125ms ≈ ±3.75 帧 @30fps**，而击杀帧要求 ±1 帧。

## 判据的关键陷阱：容差 vs 峰的密度

本片 `peaks_flux` 密度约 **2.6 个/秒**。如果沿用「±0.25s 内有峰就算命中」，
**命中率会直接顶到 100%，但这个 100% 毫无信息量**：随机挑一个时刻，也有很高的概率
落进某条带里。所以本工具对每个容差同时给出**机会基线**（chance level）：把该片时间轴
按 1ms 打点，量「一个随机时刻落在某个峰 ±tol 内」的比例 `p_chance`，再用**精确二项检验**
问「观测命中数显著高于随机吗」。

> **不看基线只看命中率的结论，一律不采纳。**

## 用法

    .venv\\Scripts\\python.exe projects/game-001/tools/audio_transient_feasibility.py
    ... --tol 0.03 0.05 --check

不需要 numpy / 素材 / 剪映 / 网络（纯标准库）。
输出：projects/game-001/verification/audio-transient/audio-feasibility.json
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from statistics import median

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
A2 = ROOT / "projects" / "game-001" / "analysis2"
RAW = A2 / "raw"
OUTDIR = ROOT / "projects" / "game-001" / "verification" / "audio-transient"
GT = A2 / "kills_groundtruth.json"
LEGACY_MINE = A2 / "kills_mine.json"
LEGACY_KILLS = A2 / "kills.json"
LEGACY_MEASURED = A2 / "kills_mine_measured.json"
DEFAULT_TOLS = (0.03, 0.05, 0.10, 0.25)


def binom_sf(k, n, p):
    """P(X >= k), X ~ Binomial(n, p)，精确计算（n 很小）。"""
    if k <= 0:
        return 1.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return min(1.0, total)


def load_audio():
    out = {}
    for p in sorted(RAW.glob("audio_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        short = p.stem.split("_", 1)[1]
        peaks = sorted((float(x["time"]), float(x["value"])) for x in (d.get("peaks_flux") or []))
        band = sorted((float(x["time"]), float(x["value"])) for x in (d.get("peaks_band") or []))
        wins = d.get("windows_250ms") or []
        out[short] = {
            "file": p.name,
            "source": d.get("source"),
            "duration_s": float(d.get("duration_s") or 0.0),
            "hop_ms": d.get("hop_ms"),
            "stats": d.get("stats") or {},
            "peaks_flux": peaks,
            "peaks_band": band,
            "series": [
                (round((float(w["start"]) + float(w["end"])) / 2, 4),
                 float(w.get("flux", 0.0)), float(w.get("band_db", 0.0)), float(w.get("rms_db", 0.0)))
                for w in wins
            ],
            "n_windows": len(wins),
            "window_len": round(median([float(w["end"]) - float(w["start"]) for w in wins]), 4) if wins else None,
        }
    return out


def chance_level(peak_times, dur, tol, step=0.001):
    """把一个「随机时刻」落进任一峰 ±tol 内的概率量出来（1ms 打点）。"""
    if not peak_times or dur <= 0:
        return 0.0
    n = int(dur / step)
    hits = 0
    j0 = 0
    for i in range(n):
        t = i * step
        while j0 < len(peak_times) and peak_times[j0] < t - tol:
            j0 += 1
        if j0 < len(peak_times) and abs(peak_times[j0] - t) <= tol:
            hits += 1
    return hits / n


def nearest(peak_times, t):
    if not peak_times:
        return None
    return min(peak_times, key=lambda x: abs(x - t))


def analyse_clip(short, clip, labels, tols, label_kind):
    peaks = clip["peaks_flux"]
    times = [t for t, _ in peaks]
    values = [v for _, v in peaks]
    value_of = dict(peaks)
    dur = clip["duration_s"]
    res = {
        "clip": short,
        "label_kind": label_kind,
        "n_labels": len(labels),
        "n_peaks": len(peaks),
        "duration_s": round(dur, 3),
        "peaks_per_s": round(len(peaks) / dur, 3) if dur else None,
        "flux_value_median": round(median(values), 3) if values else None,
        "by_tol": {},
    }
    for tol in tols:
        p = chance_level(times, dur, tol)
        matched, offsets, pct_ranks = 0, [], []
        for t in labels:
            near = nearest(times, t)
            if near is None:
                continue
            if abs(near - t) <= tol:
                matched += 1
                offsets.append(round(near - t, 4))
                v = value_of[near]
                pct_ranks.append(round(100 * sum(1 for x in values if x <= v) / len(values), 1))
        n = len(labels)
        pval = binom_sf(matched, n, p) if n else None
        res["by_tol"]["%g" % tol] = {
            "tol_s": tol,
            "tol_frames_30fps": round(tol * 30, 2),
            "chance_level": round(p, 4),
            "expected_matches_by_chance": round(n * p, 2),
            "observed_matches": matched,
            "hit_rate": round(matched / n, 3) if n else None,
            "binom_p_one_sided": (round(pval, 5) if pval is not None else None),
            "median_offset_s": (round(median(offsets), 4) if offsets else None),
            "peak_value_percentile_median": (round(median(pct_ranks), 1) if pct_ranks else None),
        }
    return res


def duration_check(audio, legacy):
    """音频 JSON 的时长 vs 视频侧 signal_seconds —— 确认两者是同一段素材、同一时间基准。"""
    rows = []
    for short in sorted(audio):
        vid = (legacy.get(short) or {}).get("signal_seconds")
        aud = audio[short]["duration_s"]
        rows.append({
            "clip": short,
            "video_signal_s": vid,
            "audio_duration_s": round(aud, 3),
            "delta_s": (round(aud - vid, 3) if vid is not None else None),
            "file_match": (audio[short]["source"] or "").endswith(((legacy.get(short) or {}).get("file") or "\u0000")),
        })
    return rows


def window_value(clip, t, idx):
    """取覆盖时刻 t 的那个 250ms 窗的第 idx 个量（0=flux, 1=band_db, 2=rms_db）。"""
    series = clip.get("series") or []
    if not series:
        return None
    step = series[1][0] - series[0][0] if len(series) > 1 else 0.25
    i = int(round((t - series[0][0]) / step))
    if i < 0 or i >= len(series):
        return None
    return series[i][idx]


def energy_test(audio, label_map, tol, idx, key_name, n_ctrl=400, seed=0):
    """击杀候选时刻的音频能量，是否显著高于随机时刻？（置换检验）

    为什么要这一步：`peaks_flux` 太密（约 2.6 个/秒），「±tol 内有峰」在随机时刻
    本来就大量成立 ⇒ 命中率这个统计量的分辨力接近 0。改用**连续无空隙的
    250ms 窗序列**比「候选时刻 vs 随机时刻」的能量，绕开峰密度这个混杂因素。
    """
    import random
    rng = random.Random(seed)
    lab_vals, ctrl_vals, per_clip = [], [], []
    for short in sorted(audio):
        labels = label_map.get(short) or []
        clip = audio[short]
        if not labels or not clip.get("series"):
            continue
        lv = [v for v in (window_value(clip, t, idx) for t in labels) if v is not None]
        dur = clip["duration_s"]
        cv = [v for v in (window_value(clip, rng.uniform(0, dur), idx) for _ in range(n_ctrl)) if v is not None]
        if not lv or not cv:
            continue
        lab_vals += lv
        ctrl_vals += cv
        per_clip.append({
            "clip": short,
            "n_labels": len(lv),
            "label_median": round(median(lv), 3),
            "control_median": round(median(cv), 3),
            "delta_median": round(median(lv) - median(cv), 3),
        })
    if not lab_vals or not ctrl_vals:
        return None
    obs = median(lab_vals) - median(ctrl_vals)
    pool = lab_vals + ctrl_vals
    nl = len(lab_vals)
    ge = 0
    N = 2000
    for _ in range(N):
        rng.shuffle(pool)
        if abs(median(pool[:nl]) - median(pool[nl:])) >= abs(obs) - 1e-12:
            ge += 1
    return {
        "quantity": key_name,
        "tol_note": "本检验不看 tol，用的是覆盖时刻 t 的 250ms 窗（量化误差 ±125ms）",
        "n_labels": nl,
        "n_controls": len(ctrl_vals),
        "label_median": round(median(lab_vals), 3),
        "control_median": round(median(ctrl_vals), 3),
        "delta_median": round(obs, 3),
        "perm_p_two_sided": round((ge + 1) / (N + 1), 4),
        "per_clip": per_clip,
    }


def lag_scan(clip, labels, tol, max_lag=1.5, step=0.01):
    """把音频峰整体平移 lag，看某个固定滞后能不能让视频候选全部落进峰带。

    这一步是**诊断**，不是拟合：如果两个信号真的在同一条时间轴上，lag=0 就该是最好的；
    如果最佳 lag 落在别处，那说明「音频 JSON 与视频候选的时间基准不一致」
    （另一条素材、另一段截取、或另一套 0 点），而不是「音频里没有击杀音效」。
    """
    times = [t for t, _ in clip["peaks_flux"]]
    dur = clip["duration_s"]
    if not times or not labels:
        return None
    p = chance_level(times, dur, tol)
    curve = []
    lag = -max_lag
    while lag <= max_lag + 1e-9:
        lv = round(lag, 3) + 0.0
        if abs(lv) < 1e-9:
            lv = 0.0
        m = sum(1 for t in labels if any(abs(x - (t + lag)) <= tol for x in times))
        curve.append((lv, m))
        lag += step
    best = max(curve, key=lambda kv: (kv[1], -abs(kv[0])))
    return {
        "tol_s": tol,
        "max_lag_s": max_lag,
        "step_s": step,
        "n_labels": len(labels),
        "chance_level": round(p, 4),
        "expected_by_chance": round(len(labels) * p, 2),
        "matches_at_lag0": next(m for l, m in curve if l == 0.0),
        "best_lag_s": best[0],
        "best_matches": best[1],
        "curve": curve,
    }


def resolution_check(audio):
    rows = []
    for short, clip in sorted(audio.items()):
        times = [t for t, _ in clip["peaks_flux"]]
        gaps = [round(b - a, 3) for a, b in zip(times, times[1:])]
        rows.append({
            "clip": short,
            "n_peaks": len(times),
            "min_gap_s": min(gaps) if gaps else None,
            "median_gap_s": round(median(gaps), 3) if gaps else None,
            "max_gap_s": max(gaps) if gaps else None,
            "window_len_s": clip["window_len"],
            "window_quant_error_ms": round(1000 * clip["window_len"] / 2, 1) if clip["window_len"] else None,
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", nargs="*", type=float, default=list(DEFAULT_TOLS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", action="store_true", help="只打印口径体检表，不写文件")
    args = ap.parse_args()

    audio = load_audio()
    if not audio:
        print("[FAIL] analysis2/raw/audio_*.json 一个都没找到")
        return 1

    res_table = resolution_check(audio)
    print("== 口径体检（本轮从数据里量出来的）==")
    print("%-10s %7s %8s %8s %8s %9s" % ("clip", "n_peaks", "min_gap", "med_gap", "win_len", "win量化"))
    for r in res_table:
        print("%-10s %7d %8s %8s %8s %9s" % (
            r["clip"], r["n_peaks"], r["min_gap_s"], r["median_gap_s"], r["window_len_s"],
            str(r["window_quant_error_ms"]) + "ms"))

    gt = json.loads(GT.read_text(encoding="utf-8"))
    gt_short = pathlib.Path(gt["source"]).stem[:8]
    gt_labels = [e["kill_time_candidate_s"] for e in gt["events"]]

    mine = json.loads(LEGACY_MINE.read_text(encoding="utf-8"))
    legacy = json.loads(LEGACY_KILLS.read_text(encoding="utf-8"))
    dur_rows = duration_check(audio, legacy)
    print("\n== 时间基准体检：音频 JSON 时长 vs 视频侧 signal_seconds ==")
    print("%-10s %14s %12s %10s %8s" % ("clip", "video_signal_s", "audio_dur_s", "delta", "同名文件"))
    for r in dur_rows:
        print("%-10s %14s %12s %10s %8s" % (
            r["clip"], r["video_signal_s"], r["audio_duration_s"], r["delta_s"], r["file_match"]))

    report = {
        "generated_by": "projects/game-001/tools/audio_transient_feasibility.py",
        "evidence_level": "L1（数值出自入库的 analysis2/raw/audio_*.json；本工具在库内复算，未接触素材）",
        "inputs": {"audio_json": len(audio), "clips": sorted(audio)},
        "resolution": res_table,
        "duration_check": dur_rows,
        "tolerance_note": "命中率必须与 chance_level 对比才有意义；单看命中率会得到假的 100%。",
    }

    print("\n== 主实验：%s 的 %d 个候选（第 7 轮，全部 confidence=medium、未经人工确认）==" % (gt_short, len(gt_labels)))
    main_res = analyse_clip(gt_short, audio[gt_short], gt_labels, args.tol, "kills_groundtruth(未确认)")
    print("%6s %6s %9s %9s %9s %7s %9s %9s %9s" % ("tol", "±帧", "机会基线", "预期命中", "实测命中", "命中率", "p(单边)", "偏移中位", "峰值分位"))
    for k in sorted(main_res["by_tol"], key=float):
        v = main_res["by_tol"][k]
        print("%6s %6s %9s %9s %9s %7s %9s %9s %9s" % (
            v["tol_s"], v["tol_frames_30fps"], v["chance_level"], v["expected_matches_by_chance"],
            v["observed_matches"], v["hit_rate"], v["binom_p_one_sided"], v["median_offset_s"],
            v["peak_value_percentile_median"]))
    report["main_experiment"] = main_res

    print("\n== 交叉：音频瞬态 vs 旧视频检测器候选（全 %d 条素材）==" % len(audio))
    report["multi_clip_vs_legacy"] = {}
    for tag, src, key in (
        ("kills.json/kills（旧检测器全集，含已知误报）", legacy, "kills"),
        ("kills_mine.json/mine（旧检测器核心集）", mine, "mine"),
    ):
        multi = []
        for short in sorted(audio):
            labels = (src.get(short) or {}).get(key) or []
            if not labels:
                continue
            multi.append(analyse_clip(short, audio[short], labels, args.tol, "legacy:" + key))
        tot = {}
        print("  -- %s --" % tag)
        for tol in args.tol:
            tk = "%g" % tol
            obs = sum(r["by_tol"][tk]["observed_matches"] for r in multi)
            n = sum(r["n_labels"] for r in multi)
            exp = sum(r["by_tol"][tk]["expected_matches_by_chance"] for r in multi)
            p_bar = exp / n if n else 0.0
            tot[tk] = {
                "tol_s": tol,
                "n_labels": n,
                "observed_matches": obs,
                "expected_matches_by_chance": round(exp, 2),
                "hit_rate": round(obs / n, 3) if n else None,
                "pooled_chance_level": round(p_bar, 4),
                "binom_p_one_sided": round(binom_sf(obs, n, p_bar), 6) if n else None,
            }
            print("  tol=±%gs  标签 %d  预期 %6.2f  实测 %4d  命中率 %s  p=%s" % (
                tol, n, exp, obs, tot[tk]["hit_rate"], tot[tk]["binom_p_one_sided"]))
        report["multi_clip_vs_legacy"][tag] = {"pooled": tot, "per_clip": multi}

    print("\n== 时间基准对账：把音频峰整体平移，看有没有某个滞后能对齐（tol=±0.05s）==")
    lag_rows, pooled_curve = [], {}
    for short in sorted(audio):
        labels = (legacy.get(short) or {}).get("kills") or []
        if not labels:
            continue
        r = lag_scan(audio[short], labels, 0.05)
        lag_rows.append({"clip": short, **{k: v for k, v in r.items() if k != "curve"}})
        for lv, m in r["curve"]:
            pooled_curve[lv] = pooled_curve.get(lv, 0) + m
        print("  %s  标签 %2d  lag=0 命中 %2d  最佳 lag=%+0.2fs 命中 %2d（随机预期 %.2f）" % (
            short, r["n_labels"], r["matches_at_lag0"], r["best_lag_s"], r["best_matches"], r["expected_by_chance"]))
    top = sorted(pooled_curve.items(), key=lambda kv: (-kv[1], abs(kv[0])))[:5]
    n_all = sum(r["n_labels"] for r in lag_rows)
    print("  合计：标签 %d  lag=0 命中 %d（随机预期 %.1f）" % (
        n_all, pooled_curve.get(0.0, 0), sum(r["expected_by_chance"] for r in lag_rows)))
    print("  合并曲线前 5：%s" % ", ".join("lag=%+.2fs→%d" % (k, v) for k, v in top))
    report["lag_scan"] = {
        "tol_s": 0.05,
        "note": "诊断用：若两个信号同轴，lag=0 就该是峰；最佳 lag 偏移 ⇒ 时间基准不一致，而不是『音频里没有击杀音效』",
        "per_clip": lag_rows,
        "pooled_curve": pooled_curve,
        "pooled_top5": [{"lag_s": k, "matches": v} for k, v in top],
    }

    label_map = {s: ((legacy.get(s) or {}).get("kills") or []) for s in audio}
    print("\n== 能量检验（置换检验，2000 次）：击杀候选时刻的音频能量 vs 随机时刻 ==")
    print("   用的是 250ms 连续窗序列（绕开 flux 峰密度这个混杂因素）")
    energy = []
    for idx, name in ((0, "flux（频谱通量）"), (1, "band_db（带限能量）"), (2, "rms_db（总能量）")):
        e = energy_test(audio, label_map, 0.05, idx, name)
        if not e:
            continue
        energy.append(e)
        print("   %-16s 标签 %d  中位 %s  随机 %s  差 %+0.3f  置换 p=%s" % (
            e["quantity"], e["n_labels"], e["label_median"], e["control_median"],
            e["delta_median"], e["perm_p_two_sided"]))
    e_gt = energy_test(audio, {gt_short: gt_labels}, 0.05, 0, "flux（仅 b61cc53d 的 10 个未确认候选）")
    if e_gt:
        print("   [b61cc53d 单素材] 标签 %d  中位 %s  随机 %s  差 %+0.3f  置换 p=%s" % (
            e_gt["n_labels"], e_gt["label_median"], e_gt["control_median"],
            e_gt["delta_median"], e_gt["perm_p_two_sided"]))
    report["energy_test"] = {"pooled": energy, "gt_single_clip": e_gt}

    known_neg = (gt.get("comparison_with_old_detector") or {}).get("old_false_positives_s") or []
    print("\n== 已知负例（第 7 轮人工确认「不是击杀」的时刻 %s）==" % known_neg)
    neg_rows = []
    for t in known_neg:
        near = nearest([x for x, _ in audio[gt_short]["peaks_flux"]], t)
        row = {"t_s": t, "nearest_flux_peak_s": near, "offset_s": round(near - t, 4) if near is not None else None}
        for tol in args.tol:
            row["hit_within_%gs" % tol] = bool(near is not None and abs(near - t) <= tol)
        neg_rows.append(row)
        print("  t=%ss  最近峰=%s  偏移=%s  命中(±%gs)=%s" % (
            t, near, row["offset_s"], max(args.tol), row["hit_within_%gs" % max(args.tol)]))
    report["known_negatives"] = {
        "note": "音频瞬态在这两个『已确认非击杀』时刻的表现，是判断该信号是否击杀专有的关键",
        "rows": neg_rows,
    }

    if args.check:
        return 0

    dst = pathlib.Path(args.out) if args.out else OUTDIR / "audio-feasibility.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n[OK] %s" % dst.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
