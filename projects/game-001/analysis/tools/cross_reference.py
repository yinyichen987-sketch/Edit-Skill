"""把音频峰值与视觉帧对齐，输出高光候选表（供人工/下游复核）。

输入：raw/audio_{a,b,c}.json（逐帧特征）与 raw/{a,b,c}_*.json（镜头结构）
输出：raw/candidates_{a,b,c}.json + 控制台摘要

判定口径（全部是相对量，可复现）：
  band   2–8kHz 带能量，高于全局中位数 >= 8dB 视为"瞬态显著"
  rms    整段能量，高于全局中位数 >= 5dB 视为"响度显著"
  交火   同一 1.0s 窗内 band 与 rms 同时显著，且 band 先于/同步于 rms
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def window_lookup(windows: list[dict], t: float) -> dict | None:
    for w in windows:
        if w["start"] <= t < w["end"]:
            return w
    return None


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号会在打印中途抛 UnicodeEncodeError 而退出；
    # 崩溃退出码可能与脚本自身的失败码相同，导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="projects/game-001/analysis/raw")
    ap.add_argument("--out", default="projects/game-001/analysis/raw")
    args = ap.parse_args()

    clips = {"a": "4b0460c400bbb5320acb6063b4f59358",
             "b": "6b2eea343eee7595c3c0ede10d21d028",
             "c": "dcc871b1791e7796fadac842593f10f7"}

    all_out: dict[str, dict] = {}
    for k, srcname in clips.items():
        aud = load(os.path.join(args.raw, f"audio_{k}.json"))
        struct = load(os.path.join(args.raw, f"{k}_{srcname[:8]}.json"))
        wins = aud["windows_250ms"]

        band_med = aud["stats"]["band_db_median"]
        rms_med = aud["stats"]["rms_db_median"]
        band_thr = band_med + 8.0
        rms_thr = rms_med + 5.0

        # 1) 挑 band（瞬态）显著且为局部极大的 250ms 窗
        transients = []
        for i, w in enumerate(wins):
            if w["band_db"] < band_thr:
                continue
            prev = wins[i - 1]["band_db"] if i > 0 else w["band_db"]
            nxt = wins[i + 1]["band_db"] if i + 1 < len(wins) else w["band_db"]
            if w["band_db"] < prev or w["band_db"] < nxt:
                continue
            transients.append(w)

        # 2) 合并相邻窗为事件段
        events = []
        for w in transients:
            if events and w["start"] - events[-1]["end"] <= 0.5:
                e = events[-1]
                e["end"] = w["end"]
                e["band_db"] = max(e["band_db"], w["band_db"])
                e["rms_db"] = max(e["rms_db"], w["rms_db"])
                e["flux"] = max(e["flux"], w["flux"])
                e["n"] += 1
            else:
                events.append({"start": w["start"], "end": w["end"],
                               "band_db": w["band_db"], "rms_db": w["rms_db"],
                               "flux": w["flux"], "n": 1})

        # 3) 标注每个事件相对基线的强度
        for e in events:
            e["band_over_median_db"] = round(e["band_db"] - band_med, 2)
            e["rms_over_median_db"] = round(e["rms_db"] - rms_med, 2)
            e["has_rms_spike"] = e["rms_db"] >= rms_thr
            e["duration_s"] = round(e["end"] - e["start"], 3)

        # 4) 把事件对到镜头，便于按镜切片
        shots = struct["shots"]
        for e in events:
            mid = (e["start"] + e["end"]) / 2
            hit = [s for s in shots if s["start"] <= mid < s["end"]]
            e["shot_index"] = hit[0]["index"] if hit else None
            e["shot_start"] = hit[0]["start"] if hit else None
            e["shot_end"] = hit[0]["end"] if hit else None

        all_out[k] = {
            "source_name": srcname + ".mp4",
            "duration_s": aud["duration_s"],
            "thresholds": {"band_median_db": band_med, "band_threshold_db": round(band_thr, 2),
                           "rms_median_db": rms_med, "rms_threshold_db": round(rms_thr, 2)},
            "transient_events": events,
            "peak_count": len(events),
            "total_transient_s": round(sum(min(e["duration_s"], 1.0) for e in events), 2),
        }
        with open(os.path.join(args.out, f"candidates_{k}.json"), "w", encoding="utf-8") as fh:
            json.dump(all_out[k], fh, ensure_ascii=False, indent=2)

        print("=" * 74)
        print(f"clip {k}  {srcname}.mp4  dur={aud['duration_s']}s  "
              f"band 中位 {band_med}dB 阈值 {round(band_thr,2)}dB")
        for e in events:
            st = e["start"]; en = e["end"]
            mark = "R" if e["has_rms_spike"] else " "
            print(f"  {st:6.2f}-{en:6.2f}s  band {e['band_db']:7.2f} "
                  f"(+{e['band_over_median_db']:5.2f})  rms {e['rms_db']:7.2f} "
                  f"(+{e['rms_over_median_db']:5.2f}) {mark}  flux {e['flux']:8.3f}  "
                  f"shot#{e['shot_index']}")

    print("=" * 74)
    print("总计 3 段:", round(sum(v["duration_s"] for v in all_out.values()), 2), "s")
    print("瞬态事件总数:", sum(v["peak_count"] for v in all_out.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
