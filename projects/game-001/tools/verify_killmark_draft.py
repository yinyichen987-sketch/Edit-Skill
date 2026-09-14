"""独立校验「击杀帧标记草稿」：草稿里的时间码是否真的落在 groundtruth 的帧上。

**为什么不能让生成器自证**（`docs/lessons.md` 第 4、6 轮反复踩过）：
生成器把「我算的帧」写进 JSON，再读回自己写的 JSON，永远相等。
所以这里做三件生成器**不做**的事：

1. **从草稿的微秒反算帧号**（`round(us * 30 / 1e6)`），与 groundtruth 的帧号比对，
   容差 1 微秒。用 `int()` 截断会误报（13933300µs 截断得 417，实际是 418）——
   这个坑本工具自己踩过一次，写在这里当反例。
2. **反算回来的帧必须是整数**：如果草稿里存在不在 30fps 网格上的时间码，说明写入用了
   错误的单位（`tim(0.5)` 按微秒解释那一类坑），这里要报出来。
3. **台账（spec/killmark-*.json）↔ 草稿 ↔ groundtruth 三方一致**：三者任一不一致都算失败。

退出码：0 = 全部通过 / 1 = 发现不一致 / 2 = 用法或文件缺失。

用法：
    .venv\\Scripts\\python.exe projects/game-001/tools/verify_killmark_draft.py b61cc53d
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
GT = ROOT / "projects" / "game-001" / "analysis2" / "kills_groundtruth.json"
LEDGER = ROOT / "projects" / "game-001" / "spec"
DRAFT_ROOT = ROOT / "projects" / "game-001" / "draft-out"
FPS = 30.0
US_PER_FRAME = 1_000_000 / FPS
TOL_US = 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("short")
    a = ap.parse_args()

    gt_path = GT
    ledger_path = LEDGER / f"killmark-{a.short}.json"
    if not gt_path.exists() or not ledger_path.exists():
        print(f"[FAIL] 缺少 groundtruth 或台账：{gt_path.name} / {ledger_path.name}", file=sys.stderr)
        return 2
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    draft_dir = DRAFT_ROOT / ledger["draft_name"]
    dc = draft_dir / "draft_content.json"
    if not dc.exists():
        print(f"[FAIL] 草稿不存在：{dc}", file=sys.stderr)
        return 2
    draft = json.loads(dc.read_text(encoding="utf-8"))

    problems: list[str] = []
    checks: list[str] = []

    # ---- 1. 轨道与数量 ----
    text_tracks = [t for t in draft.get("tracks", []) if t.get("type") == "text"]
    video_tracks = [t for t in draft.get("tracks", []) if t.get("type") == "video"]
    n_text = sum(len(t["segments"]) for t in text_tracks)
    marks = ledger["marks"]
    checks.append(f"草稿轨道：video={len(video_tracks)} text={len(text_tracks)}；文本片段 {n_text} 条")
    if n_text != len(marks):
        problems.append(f"草稿文本片段 {n_text} 条 ≠ 台账 {len(marks)} 条")

    # ---- 2. 逐标记比对帧号 ----
    segs = sorted((s for t in text_tracks for s in t["segments"]),
                  key=lambda s: s["target_timerange"]["start"])
    if len(segs) != len(marks):
        problems.append("文本片段数与台账不一致，无法逐条比对")
    else:
        checks.append(f"{'#':>3} {'台账标记起帧':>10} {'草稿反算起帧':>10} {'台账时长帧':>9} "
                      f"{'草稿时长帧':>9} {'起点误差(µs)':>12}")
        for m, s in zip(marks, segs):
            tr = s["target_timerange"]
            # ⚠️ 帧号一律用 **round** 反算：30fps 下 1 帧 = 33333.33µs，
            # 草稿存的是整数微秒，用 int() 截断会把 F418（13933300µs）算成 417。
            # 这个坑本工具的校验器第一版就踩了（报出 12 个假问题）。
            f_start = tr["start"] / US_PER_FRAME
            f_dur = tr["duration"] / US_PER_FRAME
            r_start, r_dur = round(f_start), round(f_dur)
            err = tr["start"] - m["mark_start_us"]
            checks.append(f"{m['n']:>3} {m['mark_start_frame']:>10} {r_start:>10} "
                          f"{m['mark_end_frame'] - m['mark_start_frame'] + 1:>9} {r_dur:>9} "
                          f"{err:>12}")
            if abs(err) > TOL_US:
                problems.append(f"标记 {m['label']}：草稿起点 {tr['start']}µs ≠ 台账 "
                                f"{m['mark_start_us']}µs（差 {err}µs）")
            if tr["duration"] != m["mark_duration_us"]:
                problems.append(f"标记 {m['label']}：草稿时长 {tr['duration']}µs ≠ 台账 "
                                f"{m['mark_duration_us']}µs")
            if r_start != m["mark_start_frame"]:
                problems.append(f"标记 {m['label']}：草稿反算起帧 {r_start} ≠ 台账 "
                                f"F{m['mark_start_frame']}")
            if r_dur != m["mark_end_frame"] - m["mark_start_frame"] + 1:
                problems.append(f"标记 {m['label']}：草稿时长 {r_dur} 帧 ≠ 台账 "
                                f"{m['mark_end_frame'] - m['mark_start_frame'] + 1} 帧")
            if not (0 <= r_start and r_start + r_dur <= gt["n_frames"]):
                problems.append(f"标记 {m['label']}：帧范围 {r_start}..{r_start + r_dur} 越出素材")

    # ---- 3. 台账 ↔ groundtruth ----
    gt_by_frame = {e["kill_frame_candidate"]: e for e in gt["events"]}
    for m in marks:
        e = gt_by_frame.get(m["burst_frame"])
        if e is None:
            problems.append(f"台账标记 {m['label']} 的突变帧 {m['burst_frame']} 不在 groundtruth 里")
            continue
        if abs(e["kill_time_candidate_s"] - m["burst_s"]) > 1e-6:
            problems.append(f"台账标记 {m['label']} 时间 {m['burst_s']} ≠ groundtruth "
                            f"{e['kill_time_candidate_s']}")
        if e["confidence"] != m["confidence"]:
            problems.append(f"台账标记 {m['label']} 置信 {m['confidence']} ≠ groundtruth "
                            f"{e['confidence']}")
    missing = sorted(set(gt_by_frame) - {m["burst_frame"] for m in marks})
    if missing:
        problems.append(f"groundtruth 有 {len(missing)} 个击杀未在台账/草稿里：{missing}")

    # ---- 4. 视频铺底片段必须覆盖全片 ----
    for t in video_tracks:
        for s in t["segments"]:
            tr = s["target_timerange"]
            sr = s.get("source_timerange") or {}
            checks.append(f"主轨片段：时间线 {tr['start']}~{tr['start'] + tr['duration']}µs，"
                          f"素材窗口 {sr.get('start')}~{sr.get('start', 0) + sr.get('duration', 0)}µs")
            if tr["start"] != 0 or tr["duration"] < gt["n_frames"] / FPS * 1e6 - 1000:
                problems.append(f"主轨片段没有铺满全片：start={tr['start']} duration={tr['duration']}")

    print(f"=== 击杀帧标记草稿独立校验 · {ledger['draft_name']} ===")
    for c in checks:
        print("  " + c)
    print()
    if problems:
        print(f"[FAIL] 发现 {len(problems)} 个问题：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"[OK] 全部通过：{len(marks)} 个标记的帧号与 groundtruth 逐条一致，"
          f"且都落在 30fps 整数帧上")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
