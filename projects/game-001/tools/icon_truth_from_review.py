"""把人工标注结果（`icon-review/review.csv`）转成**机器可读的真值表**（第 12 轮）。

## 它做什么

1. 读 `review.csv`（人工填的 4 列）；
2. 顺手把 CSV **归一化成 UTF-8 BOM + LF**（Excel 保存会写成 CRLF，而 CRLF 会被
   收件方的 `core.autocrlf=true` 在 `git am` 时改掉，破坏交付往返 —— 第 9/11 轮各踩一次）；
3. 写 `icon-review/truth.json`：逐事件的真值 + 校正后的击杀帧；
4. 打印统计（事件级精确率、帧级偏差分布）。

## 字段怎么读

| CSV 列 | 含义 | 到真值表的映射 |
|---|---|---|
| `verdict_kill` | 是不是一次击杀 | `Y/N/?` |
| `verdict_mine` | 是不是我击杀 | `Y/N/?` |
| `kill_frame_offset` | 真实击杀帧 − `frame` | 只接受**整数**；`N`/`?` 视为缺失（保留原文） |
| `note` | 备注 | 原样保留 |

**关于 `?` 的 5 行**：备注写的是「0.5 秒才看到击杀」⇒ 真实击杀在 **+0.5s**。
本工具把这条人工叙述**显式**记成 `offset_from_note = +15 帧`（`--note-offset`，默认 15），
并**同时保留** `offset=None`。真值表里两个都写：`frame_true`（只用数值 offset 校正）
与 `frame_true_note`（再叠加备注推出的偏移）。报告里两种口径都会给。

## 用法

    .venv\\Scripts\\python.exe projects/game-001/tools/icon_truth_from_review.py
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
REVIEW = ROOT / "projects" / "game-001" / "verification" / "icon-review" / "review.csv"
OUTDIR = REVIEW.parent
FPS = 30.0


def normalize_csv(path):
    """把 CSV 写回 UTF-8 BOM + LF（保留内容）。返回 (是否改动, 原 CRLF 数)。"""
    raw = path.read_bytes()
    if not raw.count(b"\r\n"):
        return False, 0
    n = raw.count(b"\r\n")
    path.write_bytes(raw.replace(b"\r\n", b"\n"))
    return True, n


def as_int(v):
    v = (v or "").strip()
    try:
        return int(v)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--note-offset", type=int, default=15,
                    help="备注说「0.5 秒才看到击杀」时，按多少帧计入（默认 15 = 0.5s@30fps）")
    args = ap.parse_args()

    changed, n_crlf = normalize_csv(REVIEW)
    if changed:
        print("[归一化] review.csv 发现 %d 个 CRLF → 已改写为 LF（内容不变）" % n_crlf)

    with REVIEW.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    events, missing = [], []
    for r in rows:
        off = as_int(r["kill_frame_offset"])
        frame = int(r["frame"])
        note = (r.get("note") or "").strip()
        kill, mine = (r["verdict_kill"] or "").strip().upper(), (r["verdict_mine"] or "").strip().upper()
        if off is None and "0.5" in note:
            off_note = args.note_offset
        else:
            off_note = 0
        ev = {
            "material": r["material"], "event_id": int(r["event_id"]),
            "frame": frame, "t_s": round(frame / FPS, 4),
            "duration_frames": int(r["duration_frames"]), "peak": float(r["peak"]),
            "high_conf": int(r["high_conf"]),
            "verdict_kill": kill, "verdict_mine": mine,
            "offset_raw": (r["kill_frame_offset"] or "").strip(),
            "offset": off,
            "frame_true": None if off is None else frame + off,
            "offset_from_note": off_note,
            "frame_true_note": frame + (off if off is not None else 0) + off_note,
            "note": note,
        }
        events.append(ev)
        if kill == "?" or mine == "?" or not kill:
            missing.append(ev)

    truth = {
        "generated_by": "projects/game-001/tools/icon_truth_from_review.py",
        "source": "projects/game-001/verification/icon-review/review.csv（人工标注）",
        "evidence_level": "L1（人工看图逐条判定）",
        "fps": FPS,
        "note_offset_frames": args.note_offset,
        "n_events": len(events),
        "n_kill_mine": sum(1 for e in events if e["verdict_kill"] == "Y" and e["verdict_mine"] == "Y"),
        "n_rejected": sum(1 for e in events if e["verdict_kill"] == "N"),
        "n_unclear": len(missing),
        "events": events,
    }
    dst = OUTDIR / "truth.json"
    dst.write_text(json.dumps(truth, ensure_ascii=False, indent=1),
                   encoding="utf-8", newline="\n")

    keep = [e for e in events if e["verdict_kill"] == "Y" and e["verdict_mine"] == "Y"]
    nums = [e["offset"] for e in keep if e["offset"] is not None]
    print("[OK] %s" % dst.relative_to(ROOT))
    print()
    print("事件级：判为「我击杀」%d / %d = **%.1f%%**；判为非击杀 %d；不明确 %d"
          % (len(keep), len(events), 100.0 * len(keep) / max(1, len(events)),
             truth["n_rejected"], len(missing)))
    print("帧级　：有整数 offset 的 %d 个 —— 分布 %s；均值 %.2f 帧（%.0f ms）"
          % (len(nums), {v: nums.count(v) for v in sorted(set(nums))},
             sum(nums) / len(nums), 1000.0 * sum(nums) / len(nums) / FPS))
    print("　　　　：另有 %d 个 offset 为 `?` 但备注写「0.5 秒才看到击杀」⇒ 记为 +%d 帧"
          % (sum(1 for e in keep if e["offset"] is None), args.note_offset))
    print("　　　　：|offset| ≤ 2 帧的占 %d/%d = %.1f%%"
          % (sum(1 for v in nums if abs(v) <= 2), len(events),
             100.0 * sum(1 for v in nums if abs(v) <= 2) / len(events)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
